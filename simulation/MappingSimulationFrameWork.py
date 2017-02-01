from ResourceGetter import ResouceGetter
from RequestGenerator import TestReqGen
from RequestGenerator import SimpleReqGen
from RequestGenerator import MultiReqGen
from OrchestratorAdaptor import *
import logging

import sys
#sys.path.append(./RequestGenerator)
#from escape.mapping.simulation import ResourceGetter
#from escape.mapping.simulation import RequestGenerator

log = logging.getLogger("StressTest")
log.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s:%(name)s:%(message)s')

class MappingSolutionFramework:

    __discrete_simulation = True
    __resource_getter = None
    __request_generator = None
    __orchestrator_adaptor = None
    __remaining_request_lifetimes = list()

    def __init__(self, simulation_type):
        self.__discreate_simulation = simulation_type


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
            life_time += 2000

            #Discrete working
            if discrete_sim:

                time += 1

                #Get Orchestrator
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

                #Synchronous MAP call
                try:
                    resource_graph = orchestrator_adaptor.MAP(service_graph,resource_graph)

                    #Adding successfully mapped request to the remaining_request_lifetimes
                    service_life_element = {"dead_time":time+life_time,"SG":service_graph}
                    self.__remaining_request_lifetimes.append(service_life_element)
                    log.info("Mapping service graph " + str(sim_iter) + " successfull")
                except:
                    log.info("Mapping service graph " + str(sim_iter) + " unsuccessfull")

                #Remove expired service graph requests
                resource_graph = self.__clean_expired_requests(time,resource_graph)


            #Indiscrete working
            else:
                #TODO: Create this simulation type
                pass

            #Increase simulation iteration
            if (sim_iter < sim_end):
                sim_iter += 1
            else:
                sim_running = False


if __name__ == "__main__":

    log.info("Start simulating")
    test = MappingSolutionFramework(True)
    test.simulate("pico","multi","online",300,True)
