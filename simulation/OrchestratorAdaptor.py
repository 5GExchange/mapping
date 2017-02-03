from abc import ABCMeta, abstractmethod
try:
    from escape.mapping.alg1 import MappingAlgorithms
except ImportError:
    import sys, os
    nffg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../alg1/'))
    sys.path.append(nffg_dir)
    import MappingAlgorithms

try:
    from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 "../nffg_lib/")))
    from nffg import NFFG, NFFGToolBox


class AbstractOrchestratorAdaptor:
    __metaclass__ = ABCMeta

    @abstractmethod
    def MAP(self, request,resource):
        return

class OnlineOrchestrator(AbstractOrchestratorAdaptor):

    def MAP(self, request,resource):

        #Mik az alabbiak?
        #enable_shortest_path_cache
        #shortest paths


        #TODO: bw_factor, res_factor es lat_factor bekotese
        #TODO: fullremap parameter bekotese
        #TODO: bt_limit bekotese
        #TODO: bt_br_factor

        fullremap = False
        mode = NFFG.MODE_REMAP if fullremap else NFFG.MODE_ADD

        network, shortest_paths = MappingAlgorithms.MAP(request,resource,
                                                        enable_shortest_path_cache=True,
                                                        bw_factor=1, res_factor=1,
                                                        lat_factor=1,
                                                        shortest_paths=None,
                                                        return_dist=True, mode=mode,
                                                        bt_limit=6,
                                                        bt_branching_factor=3)

        return network