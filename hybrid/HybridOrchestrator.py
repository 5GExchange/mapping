import threading
import logging
from escape.mapping.simulation import AbstractOrchestratorAdaptor
from WhatToOptimizeStrategy import *
from WhenToOptimizeStrategy import *
from ResourceSharingStrategy import *

from ResourceSharingStrategy import AbstractResourceSharingStrategy
try:
    from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 "../nffg_lib/")))
    from nffg import NFFG, NFFGToolBox

try:
    from escape.mapping.alg1 import MappingAlgorithms as online_mapping
except ImportError:
    import sys, os
    nffg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../alg1/'))
    sys.path.append(nffg_dir)
    import MappingAlgorithms as online_mapping


try:
    from escape.mapping.milp import milp_solution_in_nffg as offline_mapping
except ImportError:
    import sys, os
    nffg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../milp/'))
    sys.path.append(nffg_dir)
    import milp_solution_in_nffg as offline_mapping

log = logging.getLogger(" ")
log.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s:%(message)s')

class HybridOrchestrator(AbstractOrchestratorAdaptor):

    __what_to_opt = None
    __when_to_opt = None
    __res_share = None
    def __init__(self, resource_graph, what_to_opt_strat, when_to_opt_strat, res_share_strat):

        if what_to_opt_strat == "reqs_since_last":
            self.__what_to_opt = ReqsSinceLastOpt()
        elif what_to_opt_strat == "all_reqs":
            self.__what_to_opt = AllReqsOpt()
        else: log.error("Invalid what_to_opt type!")


        if when_to_opt_strat == "modell_based":
            self.__when_to_opt = ModelBased()
        elif when_to_opt_strat == "fixed_req_count":
            self.__when_to_opt = FixedReqCount()
        elif when_to_opt_strat == "fixed_time":
            self.__when_to_opt = Fixedtime()
        elif when_to_opt_strat == "periodical_model_based":
            self.__when_to_opt = PeriodicalModelBased()
        else: log.error("Invalid when_to_opt type!")


        if res_share_strat == "dynamic":
            self.__res_share = DynamicMaxOnlineToAll()
        elif res_share_strat == "double_hundred":
            self.__res_share = DoubleHundred()
        else: log.error("Invalid res_share type!")

        def MAP(self, request, resource):

            mode = NFFG.MODE_ADD

            network, shortest_paths = offline_mapping.MAP(request, resource,
                                                         enable_shortest_path_cache=True,
                                                         bw_factor=1,
                                                         res_factor=1,
                                                         lat_factor=1,
                                                         shortest_paths=None,
                                                         return_dist=True,
                                                         mode=mode,
                                                         bt_limit=6,
                                                         bt_branching_factor=3)
            return network