from ResourceGetter import ResouceGetter
from RequestGenerator import TestReqGen
from RequestGenerator import SimpleReqGen
from RequestGenerator import MultiReqGen
from AbstractOrchestrator 

import sys
#sys.path.append(./RequestGenerator)
#from escape.mapping.simulation import ResourceGetter
#from escape.mapping.simulation import RequestGenerator


class MappingSolutionFramework:

    #__request_generator = None
    remaining_request_lifetimes = []

    def __init__(self, resource_getter, request_generator): #, orchestrator_adaptor):
        self.__resource_getter = resource_getter
        self.__request_generator = request_generator
        #self.__orchestrator_adaptor = orchestrator_adaptor

    def simulate(self,topology_type,request_type,sim_end,discrete_sim):

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
            service_graph = request_generator.get_request()

            #Discrete working
            if discrete_sim:



            #Indiscrete working
            else:
                pass

            #Increase simulation iteration
            if (sim_iter < sim_end):
                sim_iter += 1
            else:
                sim_running = False






if __name__ == "__main__":

    #Start simulate:

    resource_graph = ResouceGetter()
    asd = resource_graph.GetNFFG('pico')
    request = RequestGenerator()
   # orch_adaptor = OrchestratorAdaptor()
    test = MappingSolutionFramework(resource_graph,request) #,orch_adaptor)
