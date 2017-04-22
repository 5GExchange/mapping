# Copyright 2017 Balazs Nemeth
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
import shutil
import logging
import threading
import sys
import json
import copy
import os
from time import sleep
import subprocess

import numpy as N
from configobj import ConfigObj

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
from OrchestratorAdaptor import *
from RequestGenerator import *
from ResourceGetter import *

log = logging.getLogger(" Simulator")


class SimulationCounters():

    def __init__(self):
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
        self.running_requests = 0
        self.running_array = [0]

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

    def __init__(self, config_file_path, request_list):
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
        log.info(" | Request lifetime lambda: " + str(config['request_lifetime_lambda']))
        log.info(" | Request max latency: " + str(config['request_max_lat']))
        log.info(" | Request min latency: " + str(config['request_min_lat']))
        log.info(" | Request nf types: " + str(config['request_nf_type_count']))
        log.info(" | Request seed: " + str(config['request_seed']))
        log.info(" | Number of iteration: " + str(config['max_number_of_iterations']))
        log.info(" | Wait all request to expire (nothing = False): " + str(config['wait_all_req_expire']))
        log.info(" | Equilibrium: " + str(config['equilibrium']))
        log.info(" | Equilibrium radius: " + str(config['equilibrium_radius']))
        log.info(" | Request queue size: " + str(int(config['req_queue_size'])))
        log.info(" ----------------------------------------")

        self.dump_freq = int(config['dump_freq'])
        self.max_number_of_iterations = int(config['max_number_of_iterations'])
        self.request_arrival_lambda = float(config['request_arrival_lambda'])
        self.wait_all_req_expire = bool(config['wait_all_req_expire'])
        self.__discrete_simulation = bool(config['discrete_simulation'])
        self.request_lifetime_lambda = float(config['request_lifetime_lambda'])
        self.req_queue_size = int(config['req_queue_size'])
        # This stores the request waiting to be mapped
        self.__request_list = request_list
        self.copy_of_rg_network_topology = None
        # This is used to let the orchestrators know which SGs have been expired.
        self.deleted_services = []

        # Resource
        resource_type = config['topology']
        if resource_type == "pico":
            self.__resource_getter = PicoResourceGetter()
        elif resource_type == "gwin":
            self.__resource_getter = GwinResourceGetter()
        elif resource_type == "carrier":
            self.__resource_getter = CarrierTopoGetter()
        else:
            log.error("Invalid 'topology' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'topology' in the simulation.cfg file! "
                "Please choose one of the followings: pico, gwin, carrier")

        self.__network_topology_bare = self.__resource_getter.GetNFFG()
        self.__network_topology = copy.deepcopy(self.__network_topology_bare)

        # Request
        request_type = config['request_type']
        request_seed = int(config['request_seed'])
        nf_type_count = int(config['request_nf_type_count'])
        if request_type == "test":
            self.__request_generator = TestReqGen(self.request_lifetime_lambda, nf_type_count, request_seed)
        elif request_type == "simple":
            if 'request_min_lat' in config and 'request_max_lat' in config:
                minlat = float(config['request_min_lat'])
                maxlat = float(config['request_max_lat'])
                self.__request_generator = SimpleReqGen(
                    self.request_lifetime_lambda, nf_type_count, request_seed, min_lat=minlat, max_lat=maxlat)
            else:
                self.__request_generator = SimpleReqGen(self.request_lifetime_lambda, nf_type_count, request_seed)
        elif request_type == "multi":
            self.__request_generator = MultiReqGen(self.request_lifetime_lambda, nf_type_count, request_seed)
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
        else:
            log.error("Invalid 'request_type' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'request_type' in the simulation.cfg file! "
                "Please choose one of the followings: test, simple, multi")

        self.__remaining_request_lifetimes = []
        self.numpyrandom = N.random.RandomState(request_seed)

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
                                            self.deleted_services,
                                            self.full_log_path,
                                            config_file_path, log)
        elif self.orchestrator_type == "hybrid":
            log.info(" ---- Hybrid specific configurations -----")
            log.info(" | What to optimize: " + str(config['what_to_optimize']))
            log.info(" | When to optimize: " + str(config['when_to_optimize']))
            log.info(" | When to optimize parameter: " + str(config['when_to_opt_parameter']))
            log.info(" | Optimize strategy: " + str(config['orchestrator']))
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
                                            self.deleted_services,
                                            self.full_log_path,
                                            config_file_path, log)
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
                opt_params['time_limit'] = int(config['time_limit'])
            if 'mip_gap_limit' in config:
                opt_params['mip_gap_limit'] = float(config['mip_gap_limit'])
            if 'node_limit' in config:
                opt_params['node_limit'] = int(config['node_limit'])

            opt_params.update(**config['migration_handler_kwargs'])

            self.__orchestrator_adaptor = OfflineOrchestratorAdaptor(
                self.deleted_services,
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
        self.counters = SimulationCounters()

    def __mapping(self, service_graph, life_time, req_num):
        current_time = datetime.datetime.now()
        try:
            log.debug("# of VNFs in resource graph: %s" % len(
                [n for n in self.__network_topology.nfs]))

            # Give a copy for the mapping, so in case it fails, we dont have to
            # reset the prerocessed/modified resource
            self.__network_topology = self.__orchestrator_adaptor.MAP(
                copy.deepcopy(service_graph), copy.deepcopy(self.__network_topology))
            log.info("Time passed with one mapping response: %s s"%
                     (datetime.datetime.now() - current_time))
            # Adding successfully mapped request to the remaining_request_lifetimes
            service_life_element = {"dead_time": datetime.datetime.now() +
                                                 datetime.timedelta(0, life_time),
                                    "SG": service_graph, "req_num": req_num}

            self.__remaining_request_lifetimes.append(service_life_element)
            log.info("Mapping thread: Mapping service_request_"+ str(req_num) + " successful +")

            self.counters.successful_mapping_happened()

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

    def make_mapping(self):
        log.info("Start mapping thread")

        last_req_num = 0
        while req_gen_thread.is_alive() or not self.__request_list.empty():
            request_list_element = self.__request_list.get()
            request = request_list_element['request']
            life_time = request_list_element['life_time']
            req_num = request_list_element['req_num']
            self.__request_list.task_done()

            if req_num > last_req_num + 1:
                for discarded_req_num in xrange(last_req_num + 1, req_num):
                    log.info("Mapping thread: handling discarded request %s as"
                             " refused request!"%discarded_req_num)
                    self.counters.incoming_request_buffer_overflow_happened()
            elif req_num == last_req_num + 1:
                # we are on track, lets see if we can map it or not!
                pass
            elif req_num < last_req_num + 1:
                raise Exception("Implementation error in simulation framework, "
                                "request number should increase monotonically.")
            last_req_num = req_num

            # TODO: remove expired requests even when mapping didn't happen!
            # Remove expired service graph requests
            self.__clean_expired_requests(datetime.datetime.now())

            log.debug("Number of mapping iteration is %s"%req_num)
            self.__mapping(request, life_time, req_num)

        if self.wait_all_req_expire:
            # Wait for all request to expire
            while len(self.__remaining_request_lifetimes) > 0:
                # Remove expired service graph requests
                self.__clean_expired_requests(datetime.datetime.now())

        log.info("End mapping thread!")


    def __clean_expired_requests(self,time):
        # Delete expired SCs
        purge_needed = False
        for service in self.__remaining_request_lifetimes:
            if service['dead_time'] < time:
                if not purge_needed:
                    self.counters.purging_all_expired_requests()
                    purge_needed = True
                self.__del_service(service, service['req_num'])
                self.deleted_services.append(service)
                log.debug("Number of requests in the deleted_services list: %s"
                          %len(self.deleted_services))

    def create_request(self):
        log.info("Start request generator thread")

        # Simulation cycle
        sim_running = True
        request_gen_iter = 1
        while sim_running:

            # Get request
            service_graph, life_time = \
                self.__request_generator.get_request(self.__network_topology_bare,
                                                     request_gen_iter,
                                                     self.counters.running_requests)
            # Discrete working
            if self.__discrete_simulation:
                pass
            # Not discrete working
            else:
                if self.__request_list.qsize() > self.req_queue_size:
                    log.info("Request Generator thread: discarding generated "
                            "request %s with lifetime %s because the queue is full!"%
                             (request_gen_iter, life_time))
                else:
                    log.info("Request Generator thread: Add request " + str(request_gen_iter))
                    log.debug("Request Generator thread: Generated lifetime of "
                              "request %s is %s s"%(request_gen_iter, life_time))
                    request_list_element = {"request": service_graph,
                                            "life_time": life_time,
                                            "req_num": request_gen_iter}
                    self.__request_list.put(request_list_element)

                scale_radius = (1/self.request_arrival_lambda)
                exp_time = self.numpyrandom.exponential(scale_radius)
                time.sleep(exp_time)

            log.debug("Request Generator thread: Number of requests waiting in"
                      " the queue %s"%self.__request_list.qsize())
            # Increase simulation iteration is done by counters
            # Increasing request generatior iteration counter
            request_gen_iter += 1
            if request_gen_iter > self.max_number_of_iterations:
                # meaning: all the requests are generated (or discarded) which
                # will be needed during the simulation
                sim_running = False
                log.info("Stop request generator thread")


def test_sg_consumer(test, request_list, consumption_time, maxiter):
    running_reqs = []
    for i in xrange(0,maxiter):
        request_list_element = request_list.get()
        request = request_list_element['request']
        life_time = request_list_element['life_time']
        req_num = request_list_element['req_num']
        request_list.task_done()

        test.counters.running_requests = len(running_reqs)
        log.debug("TEST: Number of requests in the system: %s"%
                  test.counters.running_requests)
        sleep(consumption_time)
        current_time = time.time()
        running_reqs.append((current_time+life_time, req_num))

        expired_reqs = []
        for death_time, req_num in running_reqs:
            if death_time < current_time:
                expired_reqs.append(req_num)
        running_reqs = filter(lambda x: x[1] not in expired_reqs, running_reqs)


if __name__ == "__main__":
    request_list = Queue.Queue()

    if len(sys.argv) > 2:
        log.error("Too many input parameters!")
    elif len(sys.argv) < 2:
        log.error("Too few input parameters!")
    elif not os.path.isfile(sys.argv[1]):
        log.error("Configuration file does not exist!")
    else:
        test = MappingSolutionFramework(sys.argv[1], request_list)

        # Copy simulation.cfg to testXY dir
        shutil.copy(sys.argv[1], test.path)

        try:
            req_gen_thread = threading.Thread(None, test.create_request,
                                            "request_generator_thread_T1")

            mapping_thread = threading.Thread(None, test.make_mapping,
                                              "mapping_thread_T2")

            # This tests the equilibrium state, consums SG-s in a constant rate
            # test_sg_consumer_thread = threading.Thread(None, test_sg_consumer,
            #                                            "test_sg_consumer",
            #                                            [test, request_list, 0.01, 300000])
            req_gen_thread.start()
            # test_sg_consumer_thread.start()
            mapping_thread.start()

            req_gen_thread.join()
            # test_sg_consumer_thread.join()
            mapping_thread.join()

        except threading.ThreadError:
            log.error(" Unable to start threads")
        except Exception as e:
            log.error("Exception in simulation: %s", e)
            raise
        finally:
            # Create JSON files
            # This output is not advised to use!
            requests = {"mapped_requests": test.counters.mapped_array,
                        "running_requests": test.counters.running_array,
                        "refused_requests": test.counters.refused_array}
            full_path_json = os.path.join(test.path,
                                          "requests" + str(time.ctime()) + ".json")
            with open(full_path_json, 'w') as outfile:
                json.dump(requests, outfile)

            # make a dump after everything is finished to see the final state!
            test.dump()




