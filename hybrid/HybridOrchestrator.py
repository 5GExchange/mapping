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
import alg1.UnifyExceptionTypes as uet

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

    def __init__(self, RG, config_file_path):
            config = ConfigObj(config_file_path)

            # Protects the res_online
            self.lock = threading.Lock()

            self.res_online = None
            self.__res_offline = NFFG()

            # All request in one NFFG
            self.SUM_req = NFFG()
            self.offline_mapping_thread = None
            self.when_to_opt_param = config['when_to_opt_parameter']

            # What to optimize strategy
            what_to_opt_strat = config['what_to_optimize']
            if what_to_opt_strat == "reqs_since_last":
                self.__what_to_opt = ReqsSinceLastOpt()
            elif what_to_opt_strat == "all_reqs":
                self.__what_to_opt = AllReqsOpt()
            else:
                raise ValueError(
                    'Invalid what_to_opt_strat type! Please choose one of the '
                    'followings: all_reqs, reqs_since_last')

            # When to optimize strategy
            when_to_opt_strat = config['when_to_optimize']
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
                raise ValueError(
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
                raise ValueError(
                    'Invalid resource_share_strat type! Please choose '
                                   'one of the followings: double_hundred, '
                                   'dynamic')
            # Mapped RG
            self.resource_graph = RG

    def merge_all_request(self, sum, request):
        sum = NFFGToolBox.merge_nffgs(sum, request)
        return sum

    def do_online_mapping(self, request, online_RG):
        try:
            mode = NFFG.MODE_ADD
            self.lock.acquire()
            self.res_online = online_mapping.MAP(request, online_RG,
                                            enable_shortest_path_cache=True,
                                            bw_factor=1, res_factor=1,
                                            lat_factor=1,
                                            shortest_paths=None,
                                            return_dist=False,
                                            propagate_e2e_reqs=True,
                                            bt_limit=6,
                                            bt_branching_factor=3, mode=mode)
            log.info("do_online_mapping : Successful online mapping :)")
        except uet.MappingException as error:
            log.error("do_online_mapping : Unsuccessful online mapping :( ")
            log.error(error.msg)
            raise uet.MappingException(error.msg, error.backtrack_possible)

        except Exception as e:
            log.error(str(e.message) + str(e.__class__))
            log.error("do_online_mapping : "
                      "Can not acquire res_online or cant online mapping :( ")
        finally:
            self.lock.release()

    def do_offline_mapping(self, request):
            try:
                self.offline_status = True
                self.__res_offline = offline_mapping.MAP(
                    request, self.__res_offline, True, "ConstantMigrationCost")
                log.info("Offline mapping is ready")
                try:
                    log.info("Try to merge online and offline")
                    self.merge_online_offline()
                except Exception as e:
                    log.error(e.message)
                    log.error("Unable to merge online and offline")
            except uet.MappingException as e:
                log.error(e.msg)
                log.error("Mapping thread: "
                          "Offline mapping: Unable to mapping offline!")
                self.offline_status = False


    def set_resource_graphs(self):
        # Resource sharing strategy
        try:
            self.lock.acquire()
            self.res_online, self.__res_offline = self.__res_sharing_strat.\
                share_resource(self.resource_graph, self.res_online,
                               self.__res_offline)
        except Exception as e:
            log.error(e.message)
            log.error("set_resource_graphs: Can not acquire res_online")
        finally:
            self.lock.release()


    def merge_online_offline(self):
            try:
                self.lock.acquire()
                self.res_online = NFFGToolBox().merge_nffgs(self.res_online,
                                                            self.__res_offline)
                log.info("merge_online_offline : "
                         "Lock res_online, optimalization enforce :)")
            except Exception as e:
                log.error(e.message)
                log.error("merge_online_offline: Can not accuire res_online :(")
            finally:
                self.lock.release()


    def MAP(self, request):

        # Collect the requests
        self.merge_all_request(self.SUM_req, request)

        #if not self.offline_mapping_thread.is_alive():
        self.set_resource_graphs()

        # Start online mapping thread
        online_mapping_thread = threading.Thread(None, self.do_online_mapping,
                        "Online mapping thread", (request, self.res_online))
        try:
            online_mapping_thread.start()
        except Exception as e:
            log.error(e.message)
            log.error("Failed to start online thread")
            raise RuntimeError
        try:
            offline_status = self.offline_mapping_thread.is_alive()
        except:
            offline_status = False

        # Start offline mapping thread
        if self.__when_to_opt.need_to_optimize(offline_status, 3):
            requestToOpt = self.__what_to_opt.reqs_to_optimize(self.SUM_req)
            try:
                self.offline_mapping_thread = threading.Thread(None,
                            self.do_offline_mapping, "Offline mapping thread",
                                                            [requestToOpt])
                log.info("Start offline optimalization!")
                self.offline_mapping_thread.start()
                online_mapping_thread.join()

            except Exception as e:
                log.error(e.message)
                log.error("Failed to start offline thread")
                raise RuntimeError

        elif not self.__when_to_opt.need_to_optimize(self.offline_status, 3):
            online_mapping_thread.join()
            log.info("No need to optimize!")
        else:
            log.error("Failed to start offline")









