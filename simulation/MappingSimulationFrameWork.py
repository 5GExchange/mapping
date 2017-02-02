from ResourceGetter import ResouceGetter
from RequestGenerator import TestReqGen
from RequestGenerator import SimpleReqGen
from RequestGenerator import MultiReqGen
from OrchestratorAdaptor import *
import threading
import time
import logging
import numpy as N
import pylab as plt

try:
    from escape.mapping.alg1 import UnifyExceptionTypes as uet
except ImportError:
    import sys, os
    nffg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../alg1/'))
    sys.path.append(nffg_dir)
    import UnifyExceptionTypes as uet


import sys
#sys.path.append(./RequestGenerator)
#from escape.mapping.simulation import ResourceGetter
#from escape.mapping.simulation import RequestGenerator

log = logging.getLogger("StressTest")
log.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s:%(name)s:%(message)s')

#Global variables
resource_graph = None
request_list = list()

class MappingSolutionFramework:

    __discrete_simulation = True
    __resource_getter = None
    __request_generator = None
    __orchestrator_adaptor = None
    __remaining_request_lifetimes = list()

    def __init__(self, simulation_type):
        self.__discreate_simulation = simulation_type

    def __mapping(self,resource_graph,service_graph,life_time,orchestrator_adaptor,time,sim_iter):
        # Synchronous MAP call
        before_mapping_RG = resource_graph.copy()
        try:
            resource_graph = orchestrator_adaptor.MAP(service_graph, resource_graph)

            # Adding successfully mapped request to the remaining_request_lifetimes
            service_life_element = {"dead_time": time + life_time, "SG": service_graph}
            self.__remaining_request_lifetimes.append(service_life_element)
            log.info("Mapping service graph " + str(sim_iter) + " successfull")
        except uet.MappingException:
            log.info("Mapping service graph " + str(sim_iter) + " unsuccessfull")
            resource_graph = before_mapping_RG

        return resource_graph


    def __mapping_thread(self,rg,orchestrator_adaptor,sim_iter):

        global request_list
        global resource_graph

        while len(request_list) > 0:
            request_list_element = request_list.pop(0)
            request = request_list_element['request']
            life_time = request_list_element['life_time']
            resource_graph = self.__mapping(rg,request,life_time,orchestrator_adaptor,time.ctime(),sim_iter)


    def __clean_expired_requests(self,time,resource_graph):

        # Delete expired SCs
        for sc in self.__remaining_request_lifetimes:
            if sc['dead_time'] < time:
                # Delete mapping
                for nf in sc['SG'].nfs:
                    resource_graph.del_node(nf)
                # refresh the active SCs list
                self.__remaining_request_lifetimes.remove(sc)

        return resource_graph



    def simulate(self,topology_type,request_type,orchestrator_type,sim_end,discrete_sim=False):

        time = 0

        #Get resource
        resource_getter = ResouceGetter()
        global resource_graph
        resource_graph = resource_getter.GetNFFG(topology_type)

        #Simulation cycle
        sim_running = True
        sim_iter = 0
        while sim_running:

            #Get request
            #TODO: EZT MEG MODOSITANI AZ OSZTALYDIAGRAM SZERINT
            if request_type == "test":
                request_generator = TestReqGen()
            elif request_type == "simple":
                request_generator = SimpleReqGen()
            elif request_type == "multi":
                request_generator = MultiReqGen()
            else:
                #TODO: create exception
                pass
            service_graph, life_time  = request_generator.get_request(resource_graph,sim_iter)

            # Get Orchestrator
            if orchestrator_type == "online":
                orchestrator_adaptor = OnlineOrchestrator()
            """
            elif orchestrator_type == "offline":
                orchestrator_adaptor = OfflineOrchestrator()
            elif orchestrator_type == "hybrid":
                orchestrator_adaptor = HybridOrchestrator()
            else:
                # TODO: create exception
                pass
            """

            #Discrete working
            if discrete_sim:

                time += 1
                resource_graph = self.__mapping(resource_graph, service_graph, life_time, orchestrator_adaptor, time, sim_iter)
                #Remove expired service graph requests
                resource_graph = self.__clean_expired_requests(time,resource_graph)


            # Not discrete working
            else:
                request_list_element = {"request": service_graph, "life_time": life_time}
                request_list.append(request_list_element)

                if not mapping_thread.is_alive:
                    try:
                        mapping_thread = threading.Thread(self.__mapping_thread, (resource_graph,orchestrator_adaptor,sim_iter))
                        mapping_thread.start()
                    except:
                        log.error("Mapping thread doesn't start")

                scale_radius = 2
                n = 1000
                exp_time = N.random.exponential(scale_radius, (n, 1))
                time.sleep(exp_time)


                # Remove expired service graph requests
                resource_graph = self.__clean_expired_requests(time.ctime(), resource_graph)


            #Increase simulation iteration
            if (sim_iter < sim_end):
                sim_iter += 1
            else:
                sim_running = False


if __name__ == "__main__":

    log.info("Start simulation")
    test = MappingSolutionFramework(True)
    test.simulate("pico","simple","online",300,True)
