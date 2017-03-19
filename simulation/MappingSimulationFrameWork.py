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
import time
import shutil
import logging
import threading
import sys
import json
import copy
import os

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
from RequestGenerator import MultiReqGen
from RequestGenerator import SimpleReqGen
from RequestGenerator import TestReqGen
from ResourceGetter import *

log = logging.getLogger(" Simulator")

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

        log.info("Configuration file: " + str(config_file_path))
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
        log.info(" | Number of iteration: " + str(config['max_number_of_iterations']))
        log.info(" | Wait all request to expire (nothing = False): " + str(config['wait_all_req_expire']))
        log.info(" ----------------------------------------")

        self.number_of_iter = config['max_number_of_iterations']
        self.dump_freq = int(config['dump_freq'])
        self.max_number_of_iterations = int(config['max_number_of_iterations'])
        self.request_arrival_lambda = float(config['request_arrival_lambda'])
        self.wait_all_req_expire = bool(config['wait_all_req_expire'])
        self.__discrete_simulation = bool(config['discrete_simulation'])
        self.request_lifetime_lambda = float(config['request_lifetime_lambda'])

        # This stores the request waiting to be mapped
        self.__request_list = request_list
        self.sim_iter = 0
        self.copy_of_rg_network_topology = None
        self.dump_iter = 0
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

        self.__network_topology = self.__resource_getter.GetNFFG()

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
        else:
            log.error("Invalid 'request_type' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'request_type' in the simulation.cfg file! "
                "Please choose one of the followings: test, simple, multi")

        self.__remaining_request_lifetimes = []
        self.mapped_requests = 0
        self.mapped_array = [0]
        self.refused_requests = 0
        self.refused_array = [0]
        self.running_requests = 0
        self.running_array = [0]

        # Orchestrator
        if self.orchestrator_type == "online":
            self.__orchestrator_adaptor = OnlineOrchestratorAdaptor(
                                            self.__network_topology,
                                            self.deleted_services,
                                            self.full_log_path,
                                            config_file_path)
        elif self.orchestrator_type == "hybrid":
            log.info(" ---- Hybrid specific configurations -----")
            log.info(" | What to optimize: " + str(config['what_to_optimize']))
            log.info(" | When to optimize: " + str(config['when_to_optimize']))
            log.info(" | When to optimize parameter: " + str(config['when_to_opt_parameter']))
            log.info(" | Optimize strategy: " + str(config['orchestrator']))
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
                                            self.__network_topology,
                                            self.deleted_services,
                                            self.full_log_path,
                                            config_file_path)
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

            self.__orchestrator_adaptor = OfflineOrchestratorAdaptor(
                self.__network_topology,
                self.deleted_services,
                self.full_log_path,
                config_file_path,
                bool(config['optimize_already_mapped_nfs']),
                config['migration_handler_name'], config['migration_coeff'],
                config['load_balance_coeff'], config['edge_cost_coeff'],
                **config['migration_handler_kwargs'])
        else:
            log.error("Invalid 'orchestrator' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'orchestrator' in the simulation.cfg file! "
                "Please choose one of the followings: online, hybrid, offline")


    def __mapping(self, service_graph, life_time, orchestrator_adaptor, time, sim_iter):
        try:
            log.debug("# of VNFs in resource graph: %s" % len(
                [n for n in self.__orchestrator_adaptor.resource_graph.nfs]))

            self.copy_of_rg_network_topology = self.__orchestrator_adaptor.get_copy_of_rg()

            orchestrator_adaptor.MAP(service_graph)
            # Adding successfully mapped request to the remaining_request_lifetimes
            service_life_element = {"dead_time": time +
                            life_time, "SG": service_graph, "req_num": sim_iter}

            self.__remaining_request_lifetimes.append(service_life_element)
            log.info("Mapping thread: Mapping service_request_"
                     + str(sim_iter) + " successful +")
            self.mapped_requests += 1
            self.running_requests += 1
            self.mapped_array.append(self.mapped_requests)
            self.refused_array.append(self.refused_requests)
            self.dump_iter += 1
            if not self.dump_iter % self.dump_freq:
                self.dump()

        except uet.MappingException as me:
            log.info("Mapping thread: Mapping service_request_" +
                     str(sim_iter) + " unsuccessful\n%s"%me.msg)
            self.refused_requests += 1
            self.refused_array.append(self.refused_requests)
            orchestrator_adaptor.resource_graph = self.copy_of_rg_network_topology
        except Exception as e:
            log.error("Mapping failed: %s", e)
            raise

    def dump(self):
        log.info("Dump NFFG to file after the " + str(self.dump_iter) + ". NFFG change")
        self.__orchestrator_adaptor.dump_mapped_nffg(
            self.dump_iter, "change", self.sim_number, self.orchestrator_type)

    def __del_service(self, service, sim_iter):
        try:
            log.debug("# of VNFs in resource graph: %s" % len(
                [n for n in self.__orchestrator_adaptor.resource_graph.nfs]))

            log.info("Try to delete " + str(sim_iter) + ". sc")
            self.__orchestrator_adaptor.del_service(service['SG'])
            log.info("Mapping thread: Deleting service_request_" +
                     str(sim_iter) + " successful -")
            self.__remaining_request_lifetimes.remove(service)

            self.dump_iter += 1
            if not self.dump_iter % self.dump_freq:
                self.dump()

        except uet.MappingException:
            log.error("Mapping thread: Deleting service_request_" +
                      str(sim_iter) + " unsuccessful")
        except Exception as e:
            log.error("Delete failed: %s", e)
            raise


    def make_mapping(self):
        log.info("Start mapping thread")

        while req_gen_thread.is_alive():
            while not self.__request_list.empty():
                request_list_element = self.__request_list.get()
                request = request_list_element['request']
                life_time = request_list_element['life_time']
                req_num = request_list_element['req_num']
                self.__request_list.task_done()

                self.__mapping(request, datetime.timedelta(0, life_time),
                               self.__orchestrator_adaptor,
                               datetime.datetime.now(),
                               req_num)

                # Remove expired service graph requests
                self.__clean_expired_requests(datetime.datetime.now())

                self.running_array.append(self.running_requests)


        if self.wait_all_req_expire:
            # Wait for all request to expire
            while len(self.__remaining_request_lifetimes) > 0:
                # Remove expired service graph requests
                self.__clean_expired_requests(datetime.datetime.now())

        log.info("End mapping thread!")


    def __clean_expired_requests(self,time):
        # Delete expired SCs
        for service in self.__remaining_request_lifetimes:
            if service['dead_time'] < time:
               self.__del_service(service, service['req_num'])
               self.deleted_services.append(service)
               self.running_requests -= 1


    def create_request(self):
        log.info("Start request generator thread")
        topology = self.__network_topology
        sim_end = self.max_number_of_iterations

        # Simulation cycle
        sim_running = True
        self.sim_iter = 1
        while sim_running:

            # Get request
            service_graph, life_time = \
                self.__request_generator.get_request(topology, self.sim_iter)

            # Discrete working
            if self.__discrete_simulation:
                pass

            # Not discrete working
            else:
                log.info("Request Generator thread: Add request " + str(self.sim_iter))
                request_list_element = {"request": service_graph,
                                    "life_time": life_time, "req_num": self.sim_iter}
                self.__request_list.put(request_list_element)

                scale_radius = (1/self.request_arrival_lambda)
                exp_time = N.random.exponential(scale_radius)
                time.sleep(exp_time)

            # Increase simulation iteration
            if (self.sim_iter < sim_end):
                self.sim_iter += 1
            else:
                sim_running = False
                log.info("Stop request generator thread")


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
            requests = {"mapped_requests": test.mapped_array,
                        "running_requests": test.running_array,
                        "refused_requests": test.refused_array}
            full_path_json = os.path.join(test.path,
                                          "requests" + str(time.ctime()) + ".json")
            with open(full_path_json, 'w') as outfile:
                json.dump(requests, outfile)




