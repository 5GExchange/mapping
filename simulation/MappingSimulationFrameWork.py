import threading
import datetime
import time
import logging
import numpy as N
from configobj import ConfigObj

# try:
#     from escape.mapping.nffg_lib import NFFG, NFFGToolBox
# except ImportError:
#     import sys, os
#     sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
#                                                  "../../escape/escape/nffg_lib/")))
#     from nffg import NFFG, NFFGToolBox
# try:
#     from escape.mapping.hybrid import HybridOrchestrator as hybrid_mapping
# except ImportError:
#     import sys, os
#     nffg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../hybrid/'))
#     sys.path.append(nffg_dir)
#     import HybridOrchestrator as hybrid_mapping
#
# try:
#     from escape.mapping.alg1 import UnifyExceptionTypes as uet
# except ImportError:
#     import sys, os
#     nffg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../alg1/'))
#     sys.path.append(nffg_dir)
#     import UnifyExceptionTypes as uet

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


log = logging.getLogger(" Simulator")
log.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s:%(message)s')
config = ConfigObj("simulation.cfg")

#Global variables
resource_graph = None
request_list = list()
mapping_thread_flag = True

class MappingSolutionFramework:

    __discrete_simulation = None
    __resource_getter = None
    __network_topology = None
    __request_generator = None
    __orchestrator_adaptor = None
    __remaining_request_lifetimes = list()

    def __init__(self, simulation_type, resource_type, request_type, orchestrator_type):
        self.__discrete_simulation = simulation_type

        #Resoure
        if resource_type == "pico":
            self.__resource_getter = PicoResourceGetter()
        elif resource_type == "gwin":
            self.__resource_getter = GwinResourceGetter()
        else:
            log.error("Invalid 'topology' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'topology' in the simulation.cfg file! Please choose one of the followings: pico, gwin")

        self.__network_topology = self.__resource_getter.GetNFFG()

        #Request
        if request_type == "test":
            self.__request_generator = TestReqGen()
        elif request_type == "simple":
            self.__request_generator = SimpleReqGen()
        elif request_type == "multi":
            self.__request_generator = MultiReqGen()
        else:
            log.error("Invalid 'request_type' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'request_type' in the simulation.cfg file! Please choose one of the followings: test, simple, multi")


        #Orchestrator
        if orchestrator_type == "online":
            self.__orchestrator_adaptor = OnlineOrchestratorAdaptor(self.__network_topology)
        elif orchestrator_type == "hybrid":
            log.info(" ---- Hybrid specific configurations -----")
            log.info(" | What to optimize: " + str(config['what_to_optimize']))
            log.info(" | When to optimize: " + str(config['when_to_optimize']))
            log.info(" | Optimize strategy: " + str(config['optimize_strategy']))
            log.info(" -----------------------------------------")
            self.__orchestrator_adaptor = HybridOrchestratorAdaptor(self.__network_topology,config['what_to_optimize'], config['when_to_optimize'], config['optimize_strategy'])
        else:
            log.error("Invalid 'orchestrator' in the simulation.cfg file!")
            raise RuntimeError(
                "Invalid 'orchestrator' in the simulation.cfg file! Please choose one of the followings: test, simple, multi")

    def __mapping(self, service_graph, life_time, orchestrator_adaptor, time, sim_iter):
        # Synchronous MAP call
        try:
            orchestrator_adaptor.MAP(service_graph)
            # Adding successfully mapped request to the remaining_request_lifetimes
            service_life_element = {"dead_time": time + life_time, "SG": service_graph, "req_num": sim_iter}
            self.__remaining_request_lifetimes.append(service_life_element)
            log.info(" Mapping thread: Mapping service_request_" + str(sim_iter) + " successfull")

        except uet.MappingException:
            log.info(" Mapping thread: Mapping service_request_" + str(sim_iter) + " unsuccessfull")

    def __del_service(self,service,sim_iter):

        try:
            self.__orchestrator_adaptor.del_service(service['SG'])
            log.info(" Mapping thread: Deleting service_request_" + str(sim_iter) + " successfull")
            self.__remaining_request_lifetimes.remove(service)
        except uet.MappingException:
            log.error(" Mapping thread: Deleting service_request_" + str(sim_iter) + " unsuccessfull")

    def make_mapping(self):

        global request_list

        log.info("Start mapping thread")
        while mapping_thread_flag:
            while len(request_list) > 0:
                request_list_element = request_list.pop(0)
                request = request_list_element['request']
                life_time = request_list_element['life_time']
                req_num = request_list_element['req_num']
                self.__mapping(request,datetime.timedelta(0,life_time),self.__orchestrator_adaptor,datetime.datetime.now(),req_num)

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
               self.__del_service(service,service['req_num'])


    def create_request(self,sim_end):

        global mapping_thread_flag
        virtual_time = 0

        log.info("Start request generator thread")
        topology = self.__network_topology

        #Simulation cycle
        sim_running = True
        sim_iter = 0
        while sim_running:

            #Get request
            service_graph, life_time  = self.__request_generator.get_request(topology,sim_iter)

            #Discrete working
            if self.__discrete_simulation:
                pass
                """
                virtual_time += 1
                resource_graph = self.__mapping(resource_graph, service_graph, life_time, orchestrator_adaptor, virtual_time, sim_iter)
                #Remove expired service graph requests
                resource_graph = self.__clean_expired_requests(time,resource_graph)
                """

            # Not discrete working
            else:
                log.info(" Request Generator thread: Add request " + str(sim_iter))
                request_list_element = {"request": service_graph, "life_time": life_time,"req_num":sim_iter}
                request_list.append(request_list_element)

                scale_radius = 2
                n = 1000
                exp_time = N.random.exponential(scale_radius, (1, 1))
                #time.sleep(exp_time)

            #Increase simulation iteration
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
    test = MappingSolutionFramework(False, config['topology'], config['request_type'], config['orchestrator'])

    try:
        req_gen_thread = threading.Thread(None,test.create_request,"request_generator_thread",([50]))
        mapping_thread = threading.Thread(None,test.make_mapping,"mapping_thread")
        req_gen_thread.start()
        mapping_thread.start()

    except:
        log.error(" Unable to start threads")

    #test.simulate("pico","simple","online",300,True)
    req_gen_thread.join()
    mapping_thread.join()