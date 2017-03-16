import copy
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
import Queue

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

    def __init__(self, RG, config_file_path, deleted_services):
            config = ConfigObj(config_file_path)

            # Protects the res_online
            self.lock = threading.Lock()
            self.res_online = None
            self.__res_offline = RG.copy()
            self.deleted_services = deleted_services
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
            self.reqs_under_optimization = None

            # When to optimize strategy
            when_to_opt_strat = config['when_to_optimize']
            if when_to_opt_strat == "modell_based":
                self.__when_to_opt = ModelBased()
            elif when_to_opt_strat == "fixed_req_count":
                self.__when_to_opt = FixedReqCount()
            elif when_to_opt_strat == "fixed_time":
                self.__when_to_opt = FixedTime()
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

            # Mapped RG
            self.resource_graph = RG
            # Resource sharing strategy
            resource_share_strat = config['resource_share_strat']
            if resource_share_strat == "double_hundred":
                self.__res_sharing_strat = DoubleHundred(self.resource_graph)
            elif resource_share_strat == "dynamic":
                self.__res_sharing_strat = DynamicMaxOnlineToAll(self.resource_graph)
            else:
                raise ValueError(
                    'Invalid resource_share_strat type! Please choose '
                                   'one of the followings: double_hundred, '
                                   'dynamic')

            #Queue for online mapping
            self.online_fails = Queue.Queue()

    def merge_all_request(self, sum, request):
        sum = NFFGToolBox.merge_nffgs(sum, request)
        return sum

    def do_online_mapping(self, request, online_RG):
        temp_res_online = copy.deepcopy(self.res_online)
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
            log.warning("do_online_mapping : Unsuccessful online mapping :( ")
            log.warning(error.msg)
            self.res_online = temp_res_online
            self.online_fails.put(error)
            # Balazs: an online failure due to mapping is natural, we continue working.

        except Exception as e:
            # Balazs: exception is not thrown when acquire didnt succeed, this exception is fatal
            log.error(str(e.message) + str(e.__class__))
            log.error("do_online_mapping : "
                      "Can not acquire res_online or cant online mapping :( ")
            raise
        finally:
            self.lock.release()

    def do_offline_mapping(self, request):
            try:
                log.debug("SAP count in request %s and in resource: %s, resource total size: %s"%(len([s for s in request.saps]),
                          len([s for s in self.__res_offline.saps]), len(self.__res_offline)))
                #TODO: The migration handler should be instantiated in the constructor based on the ConfigObj!
                self.__res_offline = offline_mapping.MAP(
                    request, self.__res_offline, True, "ConstantMigrationCost",
                    migration_coeff=1.0, load_balance_coeff=1.0,
                    edge_cost_coeff=1.0)

                log.info("Offline mapping is ready")

                log.info("Delete expired requests")
                self.del_exp_reqs_from_SUMreq()
                log.info("Try to merge online and offline")
                self.merge_online_offline()

            except uet.MappingException as e:
                log.error(e.msg)
                log.error("Mapping thread: "
                          "Offline mapping: Unable to mapping offline!")
                # Balazs: in case the MILP fails with MappingException we can continue working.

    def del_exp_reqs_from_SUMreq(self):
        mode = NFFG.MODE_DEL
        for i in self.deleted_services:
            delete = False
            for j in i['SG'].nfs:
                if j in self.__res_offline.nfs:
                    delete = True
                    j.operation = NFFG.OP_DELETE
            if delete:
              self.__res_offline = online_mapping.MAP(i['SG'],
                                                      self.__res_offline,
                                                      enable_shortest_path_cache=True,
                                                      bw_factor=1, res_factor=1,
                                                      lat_factor=1,
                                                      shortest_paths=None,
                                                      return_dist=False,
                                                      propagate_e2e_reqs=True,
                                                      bt_limit=6,
                                                      bt_branching_factor=3,
                                                      mode=mode)
              # TODO: Remove i from sumreq as well
              # self.deleted_services.remove(i)

    def set_online_resource_graph(self):
        # Resource sharing strategy
        try:
            self.lock.acquire()
            self.res_online = self.__res_sharing_strat.get_online_resource(self.res_online,
                                                                           self.__res_offline)
        except Exception as e:
            log.error(e.message)
            log.error("Unhandled Exception catched during resource sharing.")
            raise
        finally:
            self.lock.release()

    def set_offline_resource_graph(self):
      # Resources sharing startegy
      self.__res_offline = self.__res_sharing_strat.get_offline_resource(self.res_online,
                                                                         self.__res_offline)

    def merge_online_offline(self):
            try:
                self.lock.acquire()
                before_merge = copy.deepcopy(self.res_online)

                try:
                    # NOTE: The simulation framework handles a list which stores the expired requests.
                    # # Balazs: Delete requests from res_offline which have been expired since the optimization started
                    # _, expired_reqs = NFFGToolBox.generate_difference_of_nffgs(self.__res_offline,
                    #                                                            self.res_online,
                    #                                                            ignore_infras=True)
                    # self.__res_offline = online_mapping.MAP(expired_reqs, self.__res_offline,
                    #                                         propagate_e2e_reqs=False,
                    #                                         mode=NFFG.MODE_DEL)

                    # Balazs: Delete requests from res_online, which are possibly migrated
                    # NOTE: if an NF to be deleted doesn't exist in the substrate DEL mode ignores it.
                    possible_reqs_to_migrate = copy.deepcopy(self.reqs_under_optimization)
                    for nf in possible_reqs_to_migrate.nfs:
                      nf.operation = NFFG.OP_DELETE
                    self.res_online = online_mapping.MAP(possible_reqs_to_migrate,
                                                         self.res_online,
                                                         propagate_e2e_reqs=False,
                                                         mode=NFFG.MODE_DEL)

                    self.res_online = NFFGToolBox.merge_nffgs(self.res_online,
                                                              self.__res_offline)
                    # Checking whether the merge was in fact successful according to resources.
                    self.res_online.calculate_available_node_res()
                    self.res_online.calculate_available_link_res([])
                    log.info("merge_online_offline : "
                             "Lock res_online, optimalization enforce :)")

                # Balazs: if mapping delete fails, it makes no sense to merge
                # Balazs The calc res functions throw only RuntimeError if it is
                # failed due to resource reservation collision!
                except RuntimeError as e:
                    self.res_online = before_merge
                    log.warn(e.message)
                    # We continue to work from this stage, we can try optimization again
                    log.warn("Unable to merge online and offline :(")
            except Exception as e:
                log.error(e.message)
                # Balazs: exception is not thrown when acquire didnt succeed, this exception is fatal
                log.error("Unhandled Exception during merge :(")
                raise
            finally:
                self.lock.release()

    def MAP(self, request):

        # Collect the requests
        self.merge_all_request(self.SUM_req, request)

        #if not self.offline_mapping_thread.is_alive():
        self.set_online_resource_graph()

        # Start online mapping thread
        online_mapping_thread = threading.Thread(None, self.do_online_mapping,
                        "Online mapping thread", (request, self.res_online))
        try:
            online_mapping_thread.start()
        except Exception as e:
            log.error(e.message)
            log.error("Failed to start online thread")
            #Balazs Why Raise runtime?? why not the same Exception
            raise # RuntimeError
        try:
            offline_status = self.offline_mapping_thread.is_alive()
        except Exception as e:
            log.error("Exception catched when checking for offline mapping "
                      "is_alive: %s", e.message)
            offline_status = False

        # Start offline mapping thread
        if self.__when_to_opt.need_to_optimize(offline_status, 3):
            self.reqs_under_optimization = self.__what_to_opt.reqs_to_optimize(self.SUM_req)
            try:
                self.set_offline_resource_graph()
                self.offline_mapping_thread = threading.Thread(None,
                            self.do_offline_mapping, "Offline mapping thread",
                                                            [self.reqs_under_optimization])
                log.info("Start offline optimalization!")
                self.offline_mapping_thread.start()
                #Balazs This is not necessary, there would be 2 joins after each other
                # online_mapping_thread.join()

            except Exception as e:
                log.error(e.message)
                log.error("Failed to start offline thread")
                #Balazs Why Raise runtime?? why not the same Exception
                raise # RuntimeError
        else:
            #Balazs This is not necessary, there would be 2 joins after each other
            # online_mapping_thread.join()
            log.info("No need to optimize!")

        online_mapping_thread.join()
        if not self.online_fails.empty():
            error = self.online_fails.get()
            try:
                raise uet.MappingException(error.msg, False)
            except:
                raise uet.MappingException(error.message, False)











