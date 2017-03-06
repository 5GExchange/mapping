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
from ResourceGetter import *
from RequestGenerator import TestReqGen
from RequestGenerator import SimpleReqGen
from RequestGenerator import MultiReqGen
from OrchestratorAdaptor import *
import threading
import Queue
import datetime
import time
import logging
import numpy as N
from configobj import ConfigObj
import alg1.UnifyExceptionTypes as uet
import numpy as np
import matplotlib.pyplot as plt

try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox


log = logging.getLogger(" Simulator")
logging.basicConfig(format='%(levelname)s:%(message)s')
logging.basicConfig(filename='log_file.log', filemode='w', level=logging.DEBUG)
formatter = logging.Formatter('%(asctime)s |   Simulator   | %(levelname)s | \t%(message)s')
hdlr = logging.FileHandler('../log_file.log')
hdlr.setFormatter(formatter)
log.addHandler(hdlr)
log.setLevel(logging.DEBUG)


class MappingSolutionFramework():

    def __init__(self, config_file_path, request_list):
        config = ConfigObj(config_file_path)

        log.info(" Start simulation")
        log.info(" ------ Simulation configurations -------")
        log.info(" | Topology: " + str(config['topology']))
        log.info(" | Request type: " + str(config['request_type']))
        log.info(" | Orchestrator: " + str(config['orchestrator']))
        log.info(" ----------------------------------------")

        self.number_of_iter = config['max_number_of_iterations']
        self.dump_freq = int(config['dump_freq'])
        self.sim_number = int(config['simulation_number'])
        self.max_number_of_iterations = int(config['max_number_of_iterations'])
        self.request_arrival_lambda = float(config['request_arrival_lambda'])
        # Ha a discrete_simulation utan van vmi akkor True-ra ertekelodik ki
        self.__discrete_simulation = bool(config['discrete_simulation'])
        self.request_lifetime_lambda = float(config['request_lifetime_lambda'])
        # This stores the request waiting to be mapped
        self.__request_list = request_list
        self.sim_iter = 0
        # Resource
        resource_type = config['topology']
        if resource_type == "pico":
            self.__resource_getter = PicoResourceGetter()
        elif resource_type == "gwin":
            self.__resource_getter = GwinResourceGetter()
        else:
            log.error("Invalid 'topology' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'topology' in the simulation.cfg file! "
                "Please choose one of the followings: pico, gwin")

        self.__network_topology = self.__resource_getter.GetNFFG()

        # Request
        request_type = config['request_type']
        if request_type == "test":
            self.__request_generator = TestReqGen(self.request_lifetime_lambda)
        elif request_type == "simple":
            self.__request_generator = SimpleReqGen(self.request_lifetime_lambda)
        elif request_type == "multi":
            self.__request_generator = MultiReqGen(self.request_lifetime_lambda)
        else:
            log.error("Invalid 'request_type' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'request_type' in the simulation.cfg file! "
                "Please choose one of the followings: test, simple, multi")

        self.__remaining_request_lifetimes = list()

        self.__mapped_requests = 0
        self.__mapped_array = [0]
        self.__refused_requests = 0
        self.__refused_array = [0]
        self.__running_requests = 0
        self.__running_array = [0]


        # Orchestrator
        self.orchestrator_type = config['orchestrator']
        if self.orchestrator_type == "online":
            self.__orchestrator_adaptor = OnlineOrchestratorAdaptor(
                self.__network_topology)
        elif self.orchestrator_type == "hybrid":
            log.info(" ---- Hybrid specific configurations -----")
            log.info(" | What to optimize: " + str(config['what_to_optimize']))
            log.info(" | When to optimize: " + str(config['when_to_optimize']))
            log.info(
                " | Optimize strategy: " + str(config['orchestrator']))
            log.info(" -----------------------------------------")
            self.__orchestrator_adaptor = HybridOrchestratorAdaptor(
                self.__network_topology)
        elif self.orchestrator_type == "offline":
            log.info(" ---- Offline specific configurations -----")
            log.info(" | Optimize already mapped nfs " + config[
                'optimize_already_mapped_nfs'])
            log.info(" | Migration cost handler given: " + config[
                'migration_handler_name'] if 'migration_handler_name' in config else "None")
            self.__orchestrator_adaptor = OfflineOrchestratorAdaptor(
                self.__network_topology,
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
            orchestrator_adaptor.MAP(service_graph)
            # Adding successfully mapped request to the remaining_request_lifetimes
            service_life_element = {"dead_time": time +
                            life_time, "SG": service_graph, "req_num": sim_iter}

            self.__remaining_request_lifetimes.append(service_life_element)
            log.info("Mapping thread: Mapping service_request_"
                     + str(sim_iter) + " successful")
            self.__mapped_requests += 1
            self.__mapped_array.append(self.__mapped_requests)
            self.__running_requests += 1
            self.__running_array.append(self.__running_requests)
            if not sim_iter % self.dump_freq:
                log.info("Dump NFFG to file after the " + str(sim_iter) + ". mapping")
                self.__orchestrator_adaptor.dump_mapped_nffg(
                sim_iter, "mapping", self.sim_number, self.orchestrator_type)
        except uet.MappingException:
            log.info("Mapping thread: Mapping service_request_" +
                     str(sim_iter) + " unsuccessful")
            self.__refused_requests += 1
            self.__refused_array.append(self.__refused_requests)

    def __del_service(self, service, sim_iter):
        try:
            self.__orchestrator_adaptor.del_service(service['SG'])
            log.info("Mapping thread: Deleting service_request_" +
                     str(sim_iter) + " successful")
            self.__remaining_request_lifetimes.remove(service)

            self.__running_requests -= 1
            self.__running_array.append(self.__running_requests)

            if not sim_iter % self.dump_freq:
                log.info("Dump NFFG to file after the " +
                         str(sim_iter) + ". deletion")
                self.__orchestrator_adaptor.\
                    dump_mapped_nffg(sim_iter, "deletion",
                                     self.sim_number, self.orchestrator_type)

        except uet.MappingException:
            log.error("Mapping thread: Deleting service_request_" +
                      str(sim_iter) + " unsuccessful")


    def make_mapping(self):
        log.info("Start mapping thread")
        while mapping_thread.is_alive:
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

        # Wait for all request to expire
        while len(self.__remaining_request_lifetimes) > 0:
            # Remove expired service graph requests
            self.__clean_expired_requests(datetime.datetime.now())

        log.info("End mapping thread")


    def __clean_expired_requests(self,time):
        # Delete expired SCs
        for service in self.__remaining_request_lifetimes:
            if service['dead_time'] < time:
               self.__del_service(service, service['req_num'])


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
                mapping_thread_flag = False
                log.info("Stop request generator thread")


if __name__ == "__main__":
    request_list = Queue.Queue()
    test = MappingSolutionFramework('simulation.cfg', request_list)
    try:
        req_gen_thread = threading.Thread(None, test.create_request,
                                        "request_generator_thread_T1")

        mapping_thread = threading.Thread(None, test.make_mapping,
                                          "mapping_thread_T2")
        req_gen_thread.start()
        mapping_thread.start()

        req_gen_thread.join()
        mapping_thread.join()

        #Plot generator
        plt.plot([0 for i in xrange(test.__mapped_array.length)],test.__mapped_array)
        plt.show()



    except:
        log.error(" Unable to start threads")
