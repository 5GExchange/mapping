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
    offline_status = False


    def __init__(self, resource_graph, what_to_opt_strat, when_to_opt_strat, res_share_strat):

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
        else: log.error("Invalid when_to_opt type!")


        def merge_all_request(request):
            #TODO:
            global all_request
            pass


        def do_online_mapping(self,request, online_RG):

            mode = NFFG.MODE_ADD

            self.__res_online= online_mapping.MAP(request, online_RG,
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

            self.__res_offline = offline_mapping.MAP(request, offline_RG,
                                                         enable_shortest_path_cache=True,
                                                         bw_factor=1,
                                                         res_factor=1,
                                                         lat_factor=1,
                                                         shortest_paths=None,
                                                         return_dist=False,
                                                         mode=mode,
                                                         bt_limit=6,
                                                         bt_branching_factor=3)
            self.offline_status= False



        def merge_online_offline(self,onlineRG, offlineRG):
            mergeRG= onlineRG.copy()

            NFFGToolBox().merge_nffgs(mergeRG, offlineRG)

            return mergeRG

        def MAP(self, request):

            #Collect the requests
            merge_all_request(request)

            if not self.offline_status:
                # Resource sharing strategy
                if res_share_strat == "dynamic":
                    self.__res_online, self.__res_offline = DynamicMaxOnlineToAll().share_resource(
                        resource_graph)
                elif res_share_strat == "double_hundred":
                    self.__res_online, self.__res_offline = DoubleHundred().share_resource(
                        resource_graph)
                else:
                    log.error("Invalid res_share type!")


            #Start online mapping thread
            try:
                online_mapping_thread = threading.Thread(None, do_online_mapping,
                        "Online mapping thread", (request, self.__res_online))
                online_mapping_thread.start()
            except:
                log.error("Failed to start online thread")


            # Start offline mapping thread
            if self.__when_to_opt.need_to_optimize():

                requestToOpt = self.__what_to_opt.reqs_to_optimize()

                try:
                    offline_mapping_thread = threading.Thread(None, do_offline_mapping,
                                    "Offline mapping thread",(requestToOpt, self.__res_offline))
                    offline_mapping_thread.start()
                    self.offline_status = True
                except:
                    log.error("Failed to start offline thread")


            elif not self.__when_to_opt.need_to_optimize():
                log.info("No need to optimize!")
            else:
                log.error("Failed to start offline")

            online_mapping_thread.join()






