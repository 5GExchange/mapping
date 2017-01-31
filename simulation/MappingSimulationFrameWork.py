import ResourceGetter
import RequestGenerator
import sys
#sys.path.append(./RequestGenerator)
#from escape.mapping.simulation import ResourceGetter
#from escape.mapping.simulation import RequestGenerator


class MappingSolutionFramework:

    remaining_request_lifetimes = []

    def __init__(self, resource_getter, request_generator): #, orchestrator_adaptor):
        self.__resource_getter = resource_getter
        self.__request_generator = request_generator
        #self.__orchestrator_adaptor = orchestrator_adaptor


if __name__ == "__main__":
    getresource = ResourceGetter.ResouceGetter()
    asd = getresource.GetNFFG('pico')
    getrequest = RequestGenerator.RequestGenerator()
   # orch_adaptor = OrchestratorAdaptor()
    test = MappingSolutionFramework(getresource,getrequest) #,orch_adaptor)
