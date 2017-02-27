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


try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

from ResourceGetter import *
from RequestGenerator import TestReqGen
from RequestGenerator import SimpleReqGen
from RequestGenerator import MultiReqGen
from OrchestratorAdaptor import *

import alg1.UnifyExceptionTypes as uet

config = ConfigObj("simulation.cfg")
log = logging.getLogger(" Simulator")
logging.basicConfig(format='%(levelname)s:%(message)s')
logging.basicConfig(filename='log_file.log', filemode='w', level=logging.DEBUG)
formatter = logging.Formatter('%(asctime)s |   Simulator   | %(levelname)s | \t%(message)s')
hdlr = logging.FileHandler('../log_file.log')
hdlr.setFormatter(formatter)
log.addHandler(hdlr)
log.setLevel(logging.DEBUG)

#Global variables
#resource_graph = None
#request_list = list()
#mapping_thread_flag = True


class MappingSolutionFramework(threading.Thread):

    def __init__(self, config_file_path, request_list):
        config = ConfigObj(config_file_path)

        self.__discrete_simulation = bool(config['discrete_simulation'])
        # Ha a discrete_simulation utan van vmi akkor True-ra ertekelodik ki

        self.dump_interval = int(config['dump_interval'])
        self.max_number_of_iterations = int(config['max_number_of_iterations'])

        # This stores the request waiting to be mapped
        threading.Thread.__init__(self)
        self.__request_list = request_list

        # TODO: process other params

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
            self.__request_generator = TestReqGen()
        elif request_type == "simple":
            self.__request_generator = SimpleReqGen()
        elif request_type == "multi":
            self.__request_generator = MultiReqGen()
        else:
            log.error("Invalid 'request_type' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'request_type' in the simulation.cfg file! "
                "Please choose one of the followings: test, simple, multi")

        self.__remaining_request_lifetimes = list()


        # Orchestrator
        orchestrator_type = config['orchestrator']
        if orchestrator_type == "online":
            self.__orchestrator_adaptor = OnlineOrchestratorAdaptor(
                self.__network_topology)
        elif orchestrator_type == "hybrid":
            log.info(" ---- Hybrid specific configurations -----")
            log.info(" | What to optimize: " + str(config['what_to_optimize']))
            log.info(" | When to optimize: " + str(config['when_to_optimize']))
            log.info(
                " | Optimize strategy: " + str(config['orchestrator']))
            log.info(" -----------------------------------------")
            self.__orchestrator_adaptor = HybridOrchestratorAdaptor(
                self.__network_topology)
        elif orchestrator_type == "offline":
            log.info(" ---- Offline specific configurations -----")
            log.info(" | Optimize already mapped nfs " + config[
                'optimize_already_mapped_nfs'])
            log.info(" | Migration cost handler given: " + config[
                'migration_handler_name'] if 'migration_handler_name' in config else "None")
            self.__orchestrator_adaptor = OfflineOrchestratorAdaptor(
                self.__network_topology,
                bool(config['optimize_already_mapped_nfs']),
                config['migration_handler_name'],
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
            if not sim_iter % 5:
                log.info("Dump NFFG to file after the " + str(sim_iter) + ". mapping")
                self.__orchestrator_adaptor.dump_mapped_nffg(sim_iter, "mapping")
        except uet.MappingException:
            log.info("Mapping thread: Mapping service_request_" +
                     str(sim_iter) + " unsuccessful")


    def __del_service(self, service, sim_iter):
        try:
            self.__orchestrator_adaptor.del_service(service['SG'])
            log.info("Mapping thread: Deleting service_request_" +
                     str(sim_iter) + " successful")
            self.__remaining_request_lifetimes.remove(service)

            if not sim_iter % 5:
                log.info("Dump NFFG to file after the " +
                         str(sim_iter) + ". deletion")
                self.__orchestrator_adaptor.\
                    dump_mapped_nffg(sim_iter, "deletion")

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

        #Wait for all request to expire
        while len(self.__remaining_request_lifetimes) > 0:
            # Remove expired service graph requests
            self.__clean_expired_requests(datetime.datetime.now())

        log.info("End mapping thread")


    def __clean_expired_requests(self,time):
        # Delete expired SCs
        for service in self.__remaining_request_lifetimes:
            if service['dead_time'] < time:
               self.__del_service(service, service['req_num'])


    def create_request(self, sim_end):
        log.info("Start request generator thread")
        topology = self.__network_topology

        # Simulation cycle
        sim_running = True
        sim_iter = 0
        while sim_running:

            # Get request
            service_graph, life_time = \
                self.__request_generator.get_request(topology, sim_iter)

            # Discrete working
            if self.__discrete_simulation:
                pass

            # Not discrete working
            else:
                log.info("Request Generator thread: Add request " + str(sim_iter))
                request_list_element = {"request": service_graph,
                                    "life_time": life_time, "req_num": sim_iter}
                self.__request_list.put(request_list_element)

                #request_list.append(request_list_element)

                scale_radius = 2
                exp_time = N.random.exponential(scale_radius, (1, 1))
                time.sleep(exp_time)

            # Increase simulation iteration
            if (sim_iter < sim_end):
                sim_iter += 1
            else:
                sim_running = False
                mapping_thread_flag = False
                log.info("Stop request generator thread")


if __name__ == "__main__":

    log.info(" Start simulation")
    log.info(" ------ Simulation configurations -------")
    log.info(" | Topology: " + str(config['topology']))
    log.info(" | Request type: " + str(config['request_type']))
    log.info(" | Orchestrator: " + str(config['orchestrator']))
    log.info(" ----------------------------------------")

    request_list = Queue.Queue()
    test = MappingSolutionFramework('simulation.cfg', request_list)

    try:
        req_gen_thread = threading.Thread(None, test.create_request,
                                        "request_generator_thread_T1",
                                        ([config['max_number_of_iterations']]))

        mapping_thread = threading.Thread(None, test.make_mapping,
                                          "mapping_thread_T2")
        req_gen_thread.start()
        mapping_thread.start()
    except:
        log.error(" Unable to start threads")

    #test.simulate("pico","simple","online",300,True)
    #req_gen_thread.join()
    #mapping_thread.join()