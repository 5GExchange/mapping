import ResourceGetter
import RequestGenerator


class MappingSolutionFramework:

    remaining_request_lifetimes = []

    def __init__(self, resource_getter, request_generator, orchestrator_adaptor):
        self.__resource_getter = resource_getter
        self.__request_generator = request_generator
        self.__orchestrator_adaptor = orchestrator_adaptor


if __name__ == "__main__":
    getresource = ResourceGetter()
    getrequest = RequestGenerator()
    orch_adaptor = OrchestratorAdaptor()
    test = MappingSolutionFramework(getresource,getrequest,orch_adaptor)
