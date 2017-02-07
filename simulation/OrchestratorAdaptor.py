from abc import ABCMeta, abstractmethod
try:
    from escape.mapping.alg1 import MappingAlgorithms as online_mapping
except ImportError:
    import sys, os
    nffg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../alg1/'))
    sys.path.append(nffg_dir)
    import MappingAlgorithms as online_mapping

try:
    from escape.mapping.hybrid import HybridOrchestrator as hybrid_mapping
except ImportError:
    import sys, os
    nffg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../hybrid/'))
    sys.path.append(nffg_dir)
    import HybridOrchestrator as hybrid_mapping

try:
    from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 "../nffg_lib/")))
    from nffg import NFFG, NFFGToolBox


class AbstractOrchestratorAdaptor:
    __metaclass__ = ABCMeta

    __resource_graph = None

    @abstractmethod
    def MAP(self, request):
        return

    @abstractmethod
    def del_service(self,request,resource):
        return

    @abstractmethod
    def dump_mapped_nffg(self):
        return

class OnlineOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self,resource):
        self.__resource_graph = resource

    def MAP(self, request):

        #Mik az alabbiak?
        #enable_shortest_path_cache
        #shortest paths

        #TODO: bw_factor, res_factor es lat_factor bekotese
        #TODO: fullremap parameter bekotese
        #TODO: bt_limit bekotese
        #TODO: bt_br_factor

        fullremap = False
        #mode = NFFG.MODE_REMAP if fullremap else NFFG.MODE_ADD
        mode = NFFG.MODE_ADD


        self.__resource_graph, shortest_paths = online_mapping.MAP(request,self.__resource_graph,
                                                        enable_shortest_path_cache=True,
                                                        bw_factor=1, res_factor=1,
                                                        lat_factor=1,
                                                        shortest_paths=None,
                                                        return_dist=True, mode=mode,
                                                        bt_limit=6,
                                                        bt_branching_factor=3)

    def del_service(self, request):

        #Mik az alabbiak?
        #enable_shortest_path_cache
        #shortest paths

        #TODO: bw_factor, res_factor es lat_factor bekotese
        #TODO: fullremap parameter bekotese
        #TODO: bt_limit bekotese
        #TODO: bt_br_factor

        mode = NFFG.MODE_DEL
        self.__resource_graph = online_mapping.MAP(request, self.__resource_graph,
                                        enable_shortest_path_cache=False,
                                        bw_factor=1, res_factor=1,
                                        lat_factor=1,
                                        shortest_paths=None,
                                        return_dist=False, mode=mode)

    def dump_mapped_nffg(self):
        return


