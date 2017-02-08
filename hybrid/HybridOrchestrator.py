import threading
import logging
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


class HybridOrchestrator():

    __what_to_opt = None
    __when_to_opt = None
    __res_offline = None
    __res_online = None
    __res_sharing_strat = None
    offline_status = False
    resource_graph = None
    SUM_req = NFFG()


    def __init__(self, RG, what_to_opt_strat, when_to_opt_strat, resource_share_strat):

            #What to optimize strategy
            if what_to_opt_strat == "reqs_since_last":
                self.__what_to_opt = ReqsSinceLastOpt()
            elif what_to_opt_strat == "all_reqs":
                self.__what_to_opt = AllReqsOpt()
            else: log.error("Invalid what_to_opt type!")

            # When to optimize strategy
            if when_to_opt_strat == "modell_based":
                self.__when_to_opt = ModelBased()
            elif when_to_opt_strat == "fixed_req_count":
                self.__when_to_opt = FixedReqCount()
            elif when_to_opt_strat == "fixed_time":
                self.__when_to_opt = Fixedtime()
            elif when_to_opt_strat == "periodical_model_based":
                self.__when_to_opt = PeriodicalModelBased()
            elif when_to_opt_strat == "allways":
                self.__when_to_opt = Allways()
            else: log.error("Invalid when_to_opt type!")

            #Resource sharing strategy
            self.__res_sharing_strat = resource_share_strat

            #Mapped RG
            self.resource_graph = RG


    def merge_all_request(self, sum,request):
        NFFGToolBox.merge_nffgs(sum, request)
        return sum

    def do_online_mapping(self, request, online_RG):

            mode = NFFG.MODE_ADD
            self.__res_online = online_mapping.MAP(request, online_RG,
                                                          enable_shortest_path_cache=True,
                                                          bw_factor=1,
                                                          res_factor=1,
                                                          lat_factor=1,
                                                          shortest_paths=None,
                                                          return_dist=False,
                                                          mode=mode,
                                                          bt_limit=6,
                                                          bt_branching_factor=3)

    def do_offline_mapping(self, request, offline_RG):

            mode = NFFG.MODE_ADD
            #self.__res_offline = offline_mapping.MAP(request, offline_RG)
            try:
                self.__res_offline = offline_mapping.convert_mip_solution_to_nffg(request, offline_RG)
                self.offline_status = False
            except:
                log.error("Unable to mapping offline")
                self.offline_status = False

    def set_resource_graphs(self):
        # Resource sharing strategy
        if self.__res_sharing_strat == "dynamic":
            self.__res_online, self.__res_offline = DynamicMaxOnlineToAll().\
                share_resource(self.resource_graph)
        elif self.__res_sharing_strat == "double_hundred":
            self.__res_online, self.__res_offline = DoubleHundred().\
                share_resource(self.resource_graph,self.__res_online,self.__res_offline)
        else: log.error("Invalid res_share type!")

    def merge_online_offline(self, onlineRG, offlineRG):
            mergeRG= onlineRG.copy()

            NFFGToolBox().merge_nffgs(mergeRG, offlineRG)

            return mergeRG

    def MAP(self, request):

        #Collect the requests
        self.merge_all_request(self.SUM_req,request)

        if not self.offline_status:
            self.set_resource_graphs()


        #Start online mapping thread
        online_mapping_thread = threading.Thread(None, self.do_online_mapping,
                                                 "Online mapping thread", (request, self.__res_online))
        try:
            online_mapping_thread.start()
        except:
            log.error("Failed to start online thread")

        # Start offline mapping thread

        if self.__when_to_opt.need_to_optimize(self.offline_status):
            requestToOpt = self.__what_to_opt.reqs_to_optimize(self.SUM_req)

            try:
                offline_mapping_thread = threading.Thread(None, self.do_offline_mapping,
                                "Offline mapping thread", (requestToOpt, self.__res_offline))
                offline_mapping_thread.start()
                self.offline_status = True
            except:
                log.error("Failed to start offline thread")

            online_mapping_thread.join()

        elif not self.__when_to_opt.need_to_optimize(self.offline_status):
            online_mapping_thread.join()
            log.info("No need to optimize!")
        else:
            log.error("Failed to start offline")









