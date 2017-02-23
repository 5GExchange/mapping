import threading

try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

from hybrid.WhatToOptimizeStrategy import *
from hybrid.WhenToOptimizeStrategy import *
from hybrid.ResourceSharingStrategy import *
import milp.milp_solution_in_nffg as offline_mapping
import alg1.MappingAlgorithms as online_mapping

log = logging.getLogger(" Hybrid Orchestrator")
log.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s:%(message)s')
logging.basicConfig(filename='log_file.log', filemode='w', level=logging.DEBUG)
formatter = logging.Formatter('%(asctime)s | Hybrid Orches | %(levelname)s | \t%(message)s')
hdlr = logging.FileHandler('../log_file.log')
hdlr.setFormatter(formatter)
log.addHandler(hdlr)
log.setLevel(logging.DEBUG)


class HybridOrchestrator():

    __what_to_opt = None
    __when_to_opt = None
    __res_offline = None
    res_online = None
    __res_sharing_strat = None
    offline_status = False
    resource_graph = None
    SUM_req = NFFG()
    offline_mapping_thread = None

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
            else:
                raise RuntimeError('Invalid when_to_opt type! Please choose one of the followings: modell_based, fixed_req_count, fixed_time, periodical_model_based, allways')
                log.error("Invalid when_to_opt type!")

            #Resource sharing strategy
            self.__res_sharing_strat = resource_share_strat

            #Mapped RG
            self.resource_graph = RG


    def merge_all_request(self, sum,request):
        NFFGToolBox.merge_nffgs(sum, request)
        return sum

    def do_online_mapping(self, request, online_RG):

            mode = NFFG.MODE_ADD
            self.res_online = online_mapping.MAP(request, online_RG,
                                            enable_shortest_path_cache=True,
                                            bw_factor=1, res_factor=1,
                                            lat_factor=1,
                                            shortest_paths=None,
                                            return_dist=False, mode=mode,
                                            bt_limit=6,
                                            bt_branching_factor=3)

    def do_offline_mapping(self, request, offline_RG):
            try:
                #self.__res_offline = offline_mapping.convert_mip_solution_to_nffg([request], offline_RG)
                self.__res_offline = offline_mapping.MAP(request, offline_RG, True, "ConstantMigrationCost")
                try:
                    log.info("Merge online and offline")
                    self.merge_online_offline(self.res_online,
                                              self.__res_offline)
                except:
                    log.warning("Unable to merge online and offline")
            except:
                log.error(
                "Mapping thread: Offline mapping: Unable to mapping offline!")
            finally:
                self.offline_status = False


    def set_resource_graphs(self):
        # Resource sharing strategy
        if self.__res_sharing_strat == "dynamic":
            self.res_online, self.__res_offline = DynamicMaxOnlineToAll().\
                share_resource(self.resource_graph)
        elif self.__res_sharing_strat == "double_hundred":
            self.res_online, self.__res_offline = DoubleHundred().\
                share_resource(self.resource_graph, self.res_online, self.__res_offline)
        else: log.error("Invalid res_share type!")

    def merge_online_offline(self, onlineRG, offlineRG):
            mergeRG= onlineRG.deepcopy()

            NFFGToolBox().merge_nffgs(mergeRG, offlineRG)

            self.res_online = mergeRG


    def MAP(self, request, vmi):

        #Collect the requests
        self.merge_all_request(self.SUM_req, request)

        if not self.offline_status:
            self.set_resource_graphs()

        #Start online mapping thread
        online_mapping_thread = threading.Thread(None, self.do_online_mapping,
                        "Online mapping thread", (request, self.res_online))
        try:
            online_mapping_thread.start()
        except:
            log.error("Failed to start online thread")

        # Start offline mapping thread
        if self.__when_to_opt.need_to_optimize(self.offline_status, 3):
            #if self.offline_status:

            requestToOpt = self.__what_to_opt.reqs_to_optimize(self.SUM_req)
            try:
                self.offline_mapping_thread = threading.Thread(None, self.do_offline_mapping,
                                "Offline mapping thread", (requestToOpt, self.__res_offline))
                log.info("Start offline optimalization!")
                self.offline_mapping_thread.start()
                #self.offline_status = True
            except:
                log.error("Failed to start offline thread")

            online_mapping_thread.join()

        elif not self.__when_to_opt.need_to_optimize(self.offline_status, 3):
            online_mapping_thread.join()
            log.info("No need to optimize!")
        else:
            log.error("Failed to start offline")









