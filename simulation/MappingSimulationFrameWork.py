# Copyright 2017 Balazs Nemeth, Mark Szalay, Janos Doka
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import Queue
import datetime
import json
import logging
import pprint
import shutil
import subprocess
import sys
import threading

import psutil

try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

import alg1.UnifyExceptionTypes as uet
from simulation.OrchestratorAdaptor import *
from simulation.RequestGenerator import *
from simulation.ResourceGetter import *

log = logging.getLogger(" Simulator")


class SimulationCounters():

    def __init__(self, premapped_request_count):
        """
        Initializes all the counters
        """
        # NOTE: Counters MUST NOT be modified from outside!
        self.sim_iter = 0
        self.dump_iter = 0
        self.mapped_requests = 0
        self.mapped_array = [0]
        self.refused_requests = 0
        self.refused_array = [0]
        self.running_requests = premapped_request_count
        self.running_array = [premapped_request_count]

    def _log_running_refused_mapped_counters(self):
        log.info("Simulation iteration count: "+str(self.sim_iter))
        log.info("Mapped service_requests count: " + str(self.mapped_requests))
        log.info("Running service_requests count: " + str(self.running_requests))
        log.info("Refused service_requests count: " + str(self.refused_requests))

    def successful_mapping_happened(self):
        self.sim_iter += 1
        self.dump_iter += 1
        self.mapped_requests += 1
        self.mapped_array.append(self.mapped_requests)
        self.running_requests += 1
        self.running_array.append(self.running_requests)
        self._log_running_refused_mapped_counters()

    def unsuccessful_mapping_happened(self):
        self.sim_iter += 1
        self.refused_requests += 1
        self.refused_array.append(self.refused_requests)
        self._log_running_refused_mapped_counters()

    def purging_all_expired_requests(self):
        self.dump_iter += 1

    def deleting_one_expired_service(self):
        self.running_requests -= 1
        self.running_array.append(self.running_requests)

    def incoming_request_buffer_overflow_happened(self):
        # meaning this mapping iteration was handled very fast, the request
        # was discarded!
        # NOTE: currently handled the same as unsuccessful mapping!
        self.sim_iter += 1
        self.refused_requests += 1
        self.refused_array.append(self.refused_requests)
        self._log_running_refused_mapped_counters()


class MappingSolutionFramework():

    def __init__(self, config_file_path):
        config = ConfigObj(config_file_path)

        self.sim_number = int(config['simulation_number'])
        self.orchestrator_type = config['orchestrator']

        if not os.path.exists('test' + str(self.sim_number) +
                                      self.orchestrator_type):
            os.mkdir('test' + str(self.sim_number) + self.orchestrator_type)
        self.path = os.path.abspath(
                'test' + str(self.sim_number) + self.orchestrator_type)
        self.full_log_path = self.path + '/log_file' + str (time.ctime()).\
            replace(' ', '_').replace(':', '-') +'.log'

        formatter = logging.Formatter(
            '%(asctime)s |   Simulator   | %(levelname)s | \t%(message)s')
        hdlr = logging.FileHandler(self.full_log_path)
        hdlr.setFormatter(formatter)
        log.addHandler(hdlr)
        log.setLevel(logging.DEBUG)
        git_commit = subprocess.check_output(['git', 'show', '--oneline', '-s'])
        git_branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        log.info("Configuration file: " + str(config_file_path))
        log.info("Git current commit: " + str(git_commit))
        log.info("Git current branch: " + str(str(git_branch)))
        log.info(" | Full configuration object dumped: \n" + str(
            pprint.pformat(dict(config))))
        log.info(" ----------------------------------------")
        log.info(" Start simulation")
        log.info(" ------ Simulation configurations -------")
        log.info(" | Simulation number: " + str(config['simulation_number']))
        log.info(" | Discrete: " + str(config['discrete_simulation']))
        log.info(" | Topology: " + str(config['topology']))
        log.info(" | Request type: " + str(config['request_type']))
        log.info(" | Orchestrator: " + str(config['orchestrator']))
        log.info(" | Dump freq: " + str(config['dump_freq']))
        log.info(" | Request arrival lambda: " + str(config['request_arrival_lambda']))
        log.info(" | Request flifetime lambda: " + str(config['request_lifetime_lambda']))
        log.info(" | Request max latency: " + str(config['request_max_lat']))
        log.info(" | Request min latency: " + str(config['request_min_lat']))
        log.info(" | Request nf types: " + str(config['request_nf_type_count']))
        log.info(" | Request seed: " + str(config['request_seed']))
        log.info(" | Number of iteration: " + str(config['max_number_of_iterations']))
        log.info(" | Wait all request to expire (nothing = False): " + str(config['wait_all_req_expire']))
        log.info(" | Request queue size: " + str(int(config['req_queue_size'])))
        log.info(" ----------------------------------------")

        self.dump_freq = int(config['dump_freq'])
        self.last_dump_number = None
        self.max_number_of_iterations = int(config['max_number_of_iterations'])
        self.request_arrival_lambda = float(config['request_arrival_lambda'])
        self.wait_all_req_expire = bool(config['wait_all_req_expire'])
        self.request_lifetime_lambda = float(config['request_lifetime_lambda'])
        self.req_queue_size = int(config['req_queue_size'])
        # This stores the request waiting to be mapped
        self.__request_list = Queue.Queue()
        self.last_req_num = 0
        self.request_gen_iter = 1
        self.copy_of_rg_network_topology = None

        # Any MAP function ends before a new request arrives, no threads are
        # started, everything is sequential.
        self.__discrete_simulation = bool(config['discrete_simulation'])
        # represents simulation time, NOT real time!
        self.discrete_simulation_timer = 0.0

        # Request
        request_type = config['request_type']
        request_seed = int(config['request_seed'])
        nf_type_count = int(config['request_nf_type_count'])
        if request_type == "test":
            self.__request_generator = TestReqGen(self.request_lifetime_lambda,
                                                  nf_type_count, request_seed)
        elif request_type == "simple":
            if 'request_min_lat' in config and 'request_max_lat' in config:
                minlat = float(config['request_min_lat'])
                maxlat = float(config['request_max_lat'])
                self.__request_generator = SimpleReqGen(
                    self.request_lifetime_lambda, nf_type_count, request_seed,
                                                min_lat=minlat, max_lat=maxlat)
            else:
                self.__request_generator = SimpleReqGen(
                    self.request_lifetime_lambda, nf_type_count, request_seed)
        elif request_type == "multi":
            self.__request_generator = MultiReqGen(self.request_lifetime_lambda,
                                                   nf_type_count, request_seed)
        elif request_type == "simple_equilibrium":
            minlat = float(config['request_min_lat'])
            maxlat = float(config['request_max_lat'])
            # optional arguments which may never be modified
            opt_params = {}
            if 'equilibrium_radius' in config:
                opt_params['equilibrium_radius'] = int(config['equilibrium_radius'])
            if 'cutoff_epsilon' in config:
                opt_params['cutoff_epsilon'] = float(config['cutoff_epsilon'])
            if 'convergence_speedup_factor' in config:
                opt_params['convergence_speedup_factor'] = float(config['convergence_speedup_factor'])
            self.__request_generator = SimpleReqGenKeepActiveReqsFixed(
                self.request_lifetime_lambda, nf_type_count,
                request_seed, minlat, maxlat,
                int(config['equilibrium']), self.request_arrival_lambda,
                **opt_params)
        elif request_type == "more_deterministic":
            minlat = float(config['request_min_lat'])
            maxlat = float(config['request_max_lat'])
            self.__request_generator = SimpleMoreDeterministicReqGen(
                self.request_lifetime_lambda, nf_type_count, request_seed,
                minlat, maxlat)
        elif request_type == "simple_immortal":
            minlat = float(config['request_min_lat'])
            maxlat = float(config['request_max_lat'])
            initial_immortal_req_count = int(config['immortal_req_count'])
            self.__request_generator = \
                SimpleDeterministicInitiallyImmortalReqGen(
                self.request_lifetime_lambda, nf_type_count, request_seed,
                    initial_immortal_req_count, minlat, maxlat)
        else:
            log.error("Invalid 'request_type' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'request_type' in the simulation.cfg file! "
                "Please choose one of the followings: test, simple, multi, "
                "simple_equilibrium, more_deterministic")

        self.__remaining_request_lifetimes = []
        self.numpyrandom = N.random.RandomState(request_seed)

        # Resource
        resource_type = config['topology']
        if resource_type == "pico":
            self.__resource_getter = PicoResourceGetter()
        elif resource_type == "gwin":
            self.__resource_getter = GwinResourceGetter()
        elif resource_type == "carrier":
            self.__resource_getter = CarrierTopoGetter()
        elif resource_type == "loaded_topology":
            # this must contain already mapped Service Graphs with the given
            # path requirements as well!
            self.__resource_getter = LoadedResourceGetter(log,
                                                          config['loaded_nffg_path'])
            # denote premapped request numbers with negative numbers.
            req_num = 0
            starting_time_of_remapped_lives = None
            for service_graph in self.__resource_getter.getRunningSGs():
                if req_num == 0:
                    starting_time_of_remapped_lives = datetime.datetime.now()
                req_num -= 1
                life_time = self.__request_generator.get_request_lifetime(-1 * req_num)
                log.debug("Generated lifetime for premapped SG %s is %s s"%
                          (req_num, life_time))
                log.debug("Adding premapped SG to the system on path: %s" %
                          next(service_graph.reqs).sg_path)
                if self.__discrete_simulation:
                    death_time = life_time
                else:
                    death_time = starting_time_of_remapped_lives +\
                                 datetime.timedelta(0, life_time)
                service_life_element = {"dead_time": death_time,
                                        "SG": service_graph, "req_num": req_num}
                self.__remaining_request_lifetimes.append(service_life_element)

        elif resource_type == "fat_tree":
            self.__resource_getter = FatFreeTopoGetter()
        else:
            log.error("Invalid 'topology' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'topology' in the simulation.cfg file! "
                "Please choose one of the followings: pico, gwin, carrier")

        self.__network_topology_bare = self.__resource_getter.GetNFFG()
        self.__network_topology = copy.deepcopy(self.__network_topology_bare)

        # Init counters
        self.counters = SimulationCounters(len(self.__remaining_request_lifetimes))

        # Orchestrator
        if self.orchestrator_type == "online":
            log.info(" ---- Online specific configurations -----")
            log.info(" | Enable shortest path cache: " + str(config['enable_shortest_path_cache']))
            log.info(" | bw_factor: " + str(config['bw_factor']))
            log.info(" | res_factor: " + str(config['res_factor']))
            log.info(" | lat_factor: " + str(config['lat_factor']))
            log.info(" | shortest_paths: " + str(config['shortest_paths']))
            log.info(" | return_dist: " + str(config['return_dist']))
            log.info(" | propagate_e2e_reqs: " + str(config['propagate_e2e_reqs']))
            log.info(" | bt_limit: " + str(config['bt_limit']))
            log.info(" | bt_branching_factor: " + str(config['bt_branching_factor']))
            log.info(" -----------------------------------------")
            self.__orchestrator_adaptor = OnlineOrchestratorAdaptor(
                                            self.full_log_path,
                                            config_file_path, log)
        elif self.orchestrator_type == "hybrid":
            log.info(" ---- Hybrid specific configurations -----")
            log.info(" | What to optimize: " + str(config['what_to_optimize']))
            log.info(" | When to optimize: " + str(config['when_to_optimize']))
            log.info(" | When to optimize parameter: " + str(config['when_to_opt_parameter']))
            log.info(" | Optimize strategy: " + str(config['resource_share_strat']))
            log.info(" -----------------------------------------")
            log.info(" ---- Online specific configurations -----")
            log.info(" | Enable shortest path cache: " + str(
                config['enable_shortest_path_cache']))
            log.info(" | bw_factor: " + str(config['bw_factor']))
            log.info(" | res_factor: " + str(config['res_factor']))
            log.info(" | lat_factor: " + str(config['lat_factor']))
            log.info(" | shortest_paths: " + str(config['shortest_paths']))
            log.info(" | return_dist: " + str(config['return_dist']))
            log.info(
                " | propagate_e2e_reqs: " + str(config['propagate_e2e_reqs']))
            log.info(" | bt_limit: " + str(config['bt_limit']))
            log.info(
                " | bt_branching_factor: " + str(config['bt_branching_factor']))
            log.info(" -----------------------------------------")
            log.info(" ---- Offline specific configurations -----")
            log.info(" | Optimize already mapped nfs " + config[
                'optimize_already_mapped_nfs'])
            log.info(" | migration_coeff: " + config[
                'migration_coeff'])
            log.info(" | load_balance_coeff: " + config[
                'load_balance_coeff'])
            log.info(" | edge_cost_coeff: " + config[
                'edge_cost_coeff'])
            log.info(" | Migration cost handler given: " + config[
                'migration_handler_name'] if 'migration_handler_name' in config else "None")
            log.info(" -----------------------------------------")
            self.__orchestrator_adaptor = HybridOrchestratorAdaptor(
                                            self.__network_topology_bare,
                                            self.full_log_path,
                                            config_file_path,
                                            resource_type,
                                            self.__remaining_request_lifetimes, log)
        elif self.orchestrator_type == "offline":
            log.info(" ---- Offline specific configurations -----")
            log.info(" | Optimize already mapped nfs " + config['optimize_already_mapped_nfs'])
            log.info(" | migration_coeff: " + config[
                'migration_coeff'])
            log.info(" | load_balance_coeff: " + config[
                'load_balance_coeff'])
            log.info(" | edge_cost_coeff: " + config[
                'edge_cost_coeff'])
            log.info(" | Migration cost handler given: " + config[
                'migration_handler_name'] if 'migration_handler_name' in config else "None")

            opt_params = {}
            if 'time_limit' in config:
                opt_params['time_limit'] = float(config['time_limit'])
            if 'mip_gap_limit' in config:
                opt_params['mip_gap_limit'] = float(config['mip_gap_limit'])
            if 'node_limit' in config:
                opt_params['node_limit'] = int(config['node_limit'])

            opt_params.update(**config['migration_handler_kwargs'])

            self.__orchestrator_adaptor = OfflineOrchestratorAdaptor(
                self.full_log_path,
                config_file_path,
                bool(config['optimize_already_mapped_nfs']),
                config['migration_handler_name'], config['migration_coeff'],
                config['load_balance_coeff'], config['edge_cost_coeff'], log,
                **opt_params)
        else:
            log.error("Invalid 'orchestrator' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'orchestrator' in the simulation.cfg file! "
                "Please choose one of the followings: online, hybrid, offline")

    def __mapping(self, service_graph, life_time, req_num):

        # Log available memory
        log.info("System available memory: " + str(memory_usage_psutil()) + " GB")

        current_time = datetime.datetime.now()
        try:
            log.debug("# of VNFs in resource graph: %s" % len(
                [n for n in self.__network_topology.nfs]))
            log.debug("# of reqs in resource graph: %s" % len(
                [n for n in self.__network_topology.reqs]))

            # Give a copy for the mapping, so in case it fails, we dont have to
            # reset the prerocessed/modified resource
            self.__network_topology = self.__orchestrator_adaptor.MAP(
                copy.deepcopy(service_graph), copy.deepcopy(self.__network_topology))
            log.info("Time passed with one mapping response: %s s"%
                     (datetime.datetime.now() - current_time))
            # Adding successfully mapped request to the remaining_request_lifetimes
            if self.__discrete_simulation:
                death_time = self.discrete_simulation_timer + life_time
            else:
                death_time = datetime.datetime.now() + \
                             datetime.timedelta(0, life_time)
            service_life_element = {"dead_time": death_time,
                                    "SG": service_graph, "req_num": req_num}

            self.__remaining_request_lifetimes.append(service_life_element)

            log.info("Mapping thread: Mapping service_request_"+ str(req_num) + " successful +")

            self.counters.successful_mapping_happened()

            if not self.counters.dump_iter % self.dump_freq:
                self.dump()

        except uet.MappingException as me:
            log.info("Time passed with one mapping response: %s s" %
                     (datetime.datetime.now() - current_time))
            log.info("Mapping thread: Mapping service_request_" +
                     str(req_num) + " unsuccessful\n%s" % me.msg)
            # we continue working, the __network_topology is in the last valid state

            self.counters.unsuccessful_mapping_happened()
        except uet.UnifyException as ue:
            log.error("Mapping failed: %s", ue.msg)
            raise
        except Exception as e:
            log.error("Mapping failed: %s", e)
            raise
        # Try to dump even if unsucessful mapping happened, because the dum_iter
        # could have been increased due to exired requests.
        if not self.counters.dump_iter % self.dump_freq:
            self.dump()

    def dump(self):
        # It can happen that no change happens for a couple of iterations (no
        #  deletion, no successful mapping) and dump_iter doesn't increase
        # and we dump the same NFFG for multiple times.
        if self.counters.dump_iter != self.last_dump_number:
            self.last_dump_number = self.counters.dump_iter
            log.info("Dump NFFG to file after the " + str(self.counters.dump_iter) +
                     ". NFFG change")
            # NOTE: instead of dump_iter we give sim_iter to dumping function!!
            self.__orchestrator_adaptor.dump_mapped_nffg(
                self.counters.sim_iter, "change", self.sim_number,
                self.orchestrator_type, self.__network_topology)

    def __del_service(self, service, sim_iter):
        try:
            log.debug("# of VNFs in resource graph: %s" % len(
                [n for n in self.__network_topology.nfs]))
            log.debug("# of reqs in resource graph: %s" % len(
                [n for n in self.__network_topology.reqs]))

            log.info("Try to delete " + str(sim_iter) + ". sc")
            self.__network_topology = self.__orchestrator_adaptor.del_service(service['SG'],
                                                      self.__network_topology)
            log.info("Mapping thread: Deleting service_request_" +
                     str(sim_iter) + " successful -")
            self.__remaining_request_lifetimes.remove(service)

            self.counters.deleting_one_expired_service()

        except uet.MappingException:
            log.error("Mapping thread: Deleting service_request_" +
                      str(sim_iter) + " unsuccessful")
            raise
        except Exception as e:
            log.error("Delete failed: %s", e)
            raise

    def make_mapping(self, req_gen_thread):

        # in case of discrete simulation it is equivalent to "while True"
        while (req_gen_thread.is_alive() if not self.__discrete_simulation
               else True) or \
           not self.__request_list.empty():
            request_list_element = self.__request_list.get()
            request = request_list_element['request']
            life_time = self.__request_generator.get_request_lifetime(
                self.counters.running_requests)
            req_num = request_list_element['req_num']
            log.debug("make_mapping: generate %s lifetime for request %s" %
                      (life_time, req_num))

            self.__request_list.task_done()

            if req_num > self.last_req_num + 1:
                for discarded_req_num in xrange(self.last_req_num + 1, req_num):
                    log.info("Mapping thread: handling discarded request %s as"
                             " refused request!"%discarded_req_num)
                    self.counters.incoming_request_buffer_overflow_happened()
            elif req_num == self.last_req_num + 1:
                # we are on track, lets see if we can map it or not!
                pass
            elif req_num < self.last_req_num + 1:
                raise Exception("Implementation error in simulation framework, "
                                "request number should increase monotonically.")
            self.last_req_num = req_num

            # TODO: remove expired requests even when mapping didn't happen!
            # Remove expired service graph requests
            self.__clean_expired_requests()

            log.debug("Number of mapping iteration is %s"%req_num)
            self.__mapping(request, life_time, req_num)

            if self.__discrete_simulation:
                return

        if self.wait_all_req_expire:
            # Wait for all request to expire
            while len(self.__remaining_request_lifetimes) > 0:
                # Remove expired service graph requests
                self.__clean_expired_requests()

        log.info("End mapping thread!")

    def __clean_expired_requests(self):
        if self.__discrete_simulation:
            time = self.discrete_simulation_timer
        else:
            time = datetime.datetime.now()
        # Delete expired SCs
        purge_needed = False
        for service in self.__remaining_request_lifetimes:
            if service['dead_time'] < time:
                if not purge_needed:
                    # this needs to be done only once, when at least one
                    # expired request was found
                    self.counters.purging_all_expired_requests()
                    purge_needed = True
                self.__del_service(service, service['req_num'])

    def create_request(self):
        """
        Fills the request queue continuously with arriving requests. Returns
        True when the generator didn't finish, but just put a request in the
        queue. Returns False when the request generator is terminated.
        :return: bool
        """

        # Simulation cycle
        while True:

            # Get request
            service_graph = \
                    self.__request_generator.get_request(self.__network_topology_bare,
                                                     self.request_gen_iter)
            if self.__request_list.qsize() > self.req_queue_size:
                log.info("Request Generator thread: discarding generated "
                        "request %s, because the queue is full!" %
                         self.request_gen_iter)
            else:
                log.info("Request Generator thread: Add request " +
                         str(self.request_gen_iter))
                request_list_element = {"request": service_graph,
                                        "req_num": self.request_gen_iter}
                self.__request_list.put(request_list_element)

            scale_radius = (1/self.request_arrival_lambda)
            exp_time = self.numpyrandom.exponential(scale_radius)
            if self.__discrete_simulation:
                log.debug("Incrementing discrete simulation timer by %s"%
                          exp_time)
                self.discrete_simulation_timer += exp_time
            else:
                time.sleep(exp_time)

            log.debug("Request Generator thread: Number of requests waiting in"
                      " the queue %s"%self.__request_list.qsize())
            # Increase simulation iteration is done by counters
            # Increasing request generatior iteration counter
            self.request_gen_iter += 1
            if self.request_gen_iter > self.max_number_of_iterations:
                # meaning: all the requests are generated (or discarded) which
                # will be needed during the simulation
                log.info("Stop request generator thread")
                return False

            if self.__discrete_simulation:
                return True

    def start(self):
        try:
            if self.__discrete_simulation:
                while self.create_request():
                    self.make_mapping(None)
                log.info("End discrete simulation.")
            else:
                req_gen_thread = threading.Thread(None, self.create_request,
                                                  "request_generator_thread_T1")
                log.info("Start request generator thread")

                mapping_thread = threading.Thread(None, self.make_mapping,
                                                  "mapping_thread_T2",
                                                  [req_gen_thread])
                log.info("Start mapping thread")

                req_gen_thread.start()
                mapping_thread.start()

                req_gen_thread.join()
                mapping_thread.join()

        except threading.ThreadError:
            log.error(" Unable to start threads")
        except Exception as e:
            log.error("Exception in simulation: %s", e)
            raise
        finally:
            # Create JSON files
            # This output is not advised to use!
            requests = {"mapped_requests": self.counters.mapped_array,
                        "running_requests": self.counters.running_array,
                        "refused_requests": self.counters.refused_array}
            full_path_json = os.path.join(self.path,
                                          "requests" + str(
                                              time.ctime()) + ".json")
            with open(full_path_json, 'w') as outfile:
                json.dump(requests, outfile)

            # make a dump after everything is finished to see the final state!
            self.dump()


def memory_usage_psutil():
    # return the available memory in GB
    mem = psutil.virtual_memory()
    return ((float(mem.available)/1024)/1024)/1024


if __name__ == "__main__":

    if len(sys.argv) > 2:
        log.error("Too many input parameters!")
    elif len(sys.argv) < 2:
        log.error("Too few input parameters!")
    elif not os.path.isfile(sys.argv[1]):
        log.error("Configuration file does not exist!")
    else:
        test = MappingSolutionFramework(sys.argv[1])

        # Copy simulation.cfg to testXY dir
        shutil.copy(sys.argv[1], test.path)

        test.start()




