import threading
from configobj import ConfigObj

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

    #def __init__(self, RG, what_to_opt_strat, when_to_opt_strat, resource_share_strat):
    def __init__(self, RG, config_file_path):
            config = ConfigObj(config_file_path)

            # What to optimize strategy
            what_to_opt_strat = config['what_to_opt_strat']
            if what_to_opt_strat == "reqs_since_last":
                self.__what_to_opt = ReqsSinceLastOpt()
            elif what_to_opt_strat == "all_reqs":
                self.__what_to_opt = AllReqsOpt()
            else:
                raise RuntimeError(
                    'Invalid what_to_opt_strat type! Please choose one of the '
                    'followings: all_reqs, reqs_since_last')

            # When to optimize strategy
            when_to_opt_strat = config['when_to_opt_strat']
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
                raise RuntimeError(
                    'Invalid when_to_opt type! Please choose '
                                   'one of the followings: modell_based, '
                                   'fixed_req_count, fixed_time, '
                                   'periodical_model_based, allways')

            # Resource sharing strategy
            resource_share_strat = config['resource_share_strat']
            if resource_share_strat == "double_hundred":
                self.__res_sharing_strat = DoubleHundred()
            elif resource_share_strat == "dynamic":
                self.__res_sharing_strat = DynamicMaxOnlineToAll()
            else:
                raise RuntimeError(
                    'Invalid resource_share_strat type! Please choose '
                                   'one of the followings: double_hundred, '
                                   'dynamic')
            #Mapped RG
            self.resource_graph = RG

    def merge_all_request(self, sum, request):
        sum = NFFGToolBox.merge_nffgs(sum, request)
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
                    self.offline_status = False
                    log.info("Merge online and offline")
                    self.res_online = self.merge_online_offline(self.res_online,
                                              self.__res_offline)

                except:
                    log.warning("Unable to merge online and offline")
            except:
                log.error(
                "Mapping thread: Offline mapping: Unable to mapping offline!")
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
            mergeRG= onlineRG.copy()
            mergeRG = NFFGToolBox().merge_nffgs(mergeRG, offlineRG)
            return mergeRG

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









