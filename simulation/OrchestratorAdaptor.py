from abc import ABCMeta, abstractmethod
import logging

log = logging.getLogger(" Orchestrator ")
log.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s:%(message)s')

try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

import alg1.MappingAlgorithms as online_mapping
import hybrid.HybridOrchestrator as hybrid_mapping

class AbstractOrchestratorAdaptor:
    __metaclass__ = ABCMeta

    __resource_graph = None

    @abstractmethod
    def MAP(self, request):
        return

    @abstractmethod
    def del_service(self, request):
        return

    @abstractmethod
    def dump_mapped_nffg(self):
        return

class OnlineOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self,resource):
        self.__resource_graph = resource

    def MAP(self, request):

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
        dump_nffg = self.__resource_graph.dump()
        try:
            f = open('dump_nffg', 'a')
            f.write("-------------------------------New test-------------------------------")
            f.write(dump_nffg)
            f.close()
        except:
            log.error("Dump_mapped_nffg file does not exist ")



class HybridOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    concrete_hybrid_orchestrator = None

    def __init__(self, resource,what_to_opt_strat, when_to_opt_strat, resource_share_strat):
        self.concrete_hybrid_orchestrator = hybrid_mapping.HybridOrchestrator(resource, what_to_opt_strat, when_to_opt_strat, resource_share_strat)

    def MAP(self, request):

        mode = NFFG.MODE_ADD
        self.concrete_hybrid_orchestrator.MAP(request,self.concrete_hybrid_orchestrator)

    def del_service(self, request):
        """
        mode = NFFG.MODE_DEL
        self.__resource_graph = hybrid_mapping.MAP(request)
        """
        pass

    def dump_mapped_nffg(self):
        pass