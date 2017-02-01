from ResourceGetter import ResouceGetter
from RequestGenerator import RequestGenerator
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


if __name__ == "__main__":
    resource_graph = ResouceGetter()
    asd = resource_graph.GetNFFG('pico')
    request = RequestGenerator()
   # orch_adaptor = OrchestratorAdaptor()
    test = MappingSolutionFramework(resource_graph,request) #,orch_adaptor)
