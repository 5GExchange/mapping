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


class ResNFFGProtector(object):

  def __init__(self, do_logging=False):
    self.readers_count = 0
    self.reader_counter_protector = threading.Lock()
    self.res_nffg_protector = threading.Lock()
    self.do_logging = do_logging

  def start_reading_res_nffg(self, read_reason):
    self.reader_counter_protector.acquire()
    self.readers_count += 1
    if self.readers_count == 1:
      self.res_nffg_protector.acquire()
      if self.do_logging:
        log.debug("Locking res nffg for reading: \"%s\", number of current readers: %s"
                  %(read_reason, self.readers_count))
    self.reader_counter_protector.release()

  def finish_reading_res_nffg(self, read_reason):
    self.reader_counter_protector.acquire()
    self.readers_count -= 1
    if self.readers_count < 0:
      raise RuntimeError("Some thread tried to release reading right on res_online multiple times!")
    if self.readers_count == 0:
      self.res_nffg_protector.release()
      if self.do_logging:
        log.debug("Releasing res nffg for reading: \"%s\", number of current readers: %s"
                  %(read_reason, self.readers_count))
    self.reader_counter_protector.release()

  def start_writing_res_nffg(self, write_reason):
    self.res_nffg_protector.acquire()
    if self.do_logging:
      log.debug("Locking res nffg for writing: \"%s\"."%write_reason)

  def finish_writing_res_nffg(self, write_reason):
    self.res_nffg_protector.release()
    if self.do_logging:
      log.debug("Releasing res nffg for writing: \"%s\"."%write_reason)


class HybridOrchestrator():

    OFFLINE_STATE_INIT = 0
    OFFLINE_STATE_RUNNING = 1
    OFFLINE_STATE_FINISHED = 2

    def __init__(self, RG, config_file_path, deleted_services, full_log_path):
            config = ConfigObj(config_file_path)

            formatter = logging.Formatter(
                '%(asctime)s | Hybrid Orches | %(levelname)s | \t%(message)s')
            hdlr = logging.FileHandler(full_log_path)
            hdlr.setFormatter(formatter)
            log.addHandler(hdlr)
            log.setLevel(logging.DEBUG)

            # Protects the res_online
            self.res_online_protector = ResNFFGProtector(True)
            self.res_online = None
            self.__res_offline = copy.deepcopy(RG)
            self.deleted_services = deleted_services
            # All request in one NFFG
            # The sum of reqs needs to be accessed from Offline optimization to determine
            # what to opt and online mapping have to gather all requests there
            self.sum_req_protector = ResNFFGProtector(True)
            self.SUM_req = NFFG()
            self.offline_mapping_thread = None
            self.offline_status = HybridOrchestrator.OFFLINE_STATE_INIT
            self.reoptimized_resource = None
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
                self.__when_to_opt = ModelBased(full_log_path)
            elif when_to_opt_strat == "fixed_req_count":
                self.__when_to_opt = FixedReqCount(full_log_path)
            elif when_to_opt_strat == "fixed_time":
                self.__when_to_opt = FixedTime(full_log_path)
            elif when_to_opt_strat == "periodical_model_based":
                self.__when_to_opt = PeriodicalModelBased(full_log_path)
            elif when_to_opt_strat == "allways":
                self.__when_to_opt = Allways(full_log_path)
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
                self.__res_sharing_strat = DoubleHundred(self.resource_graph, full_log_path)
            elif resource_share_strat == "dynamic":
                self.__res_sharing_strat = DynamicMaxOnlineToAll(self.resource_graph, full_log_path)
            else:
                raise ValueError(
                    'Invalid resource_share_strat type! Please choose '
                                   'one of the followings: double_hundred, '
                                   'dynamic')

            # Queue for online mapping
            self.online_fails = Queue.Queue()

            # Set offline mapping parameters
            self.mig_handler = config['migration_handler_name']
            self.optimize_already_mapped_nfs = bool(config['optimize_already_mapped_nfs'])
            self.migration_coeff = float(config['migration_coeff'])
            self.load_balance_coeff = float(config['load_balance_coeff'])
            self.edge_cost_coeff = float(config['edge_cost_coeff'])

    def merge_all_request(self, sum, request):
        self.sum_req_protector.start_writing_res_nffg("Appending new request to the sum of requests")
        sum = NFFGToolBox.merge_nffgs(sum, request)
        self.sum_req_protector.finish_writing_res_nffg("New request %s appended to sum req" % request)
        return sum

    def do_online_mapping(self, request, resource):
        self.res_online_protector.start_writing_res_nffg("Map a request in an online manner")
        self.set_online_resource_graph(resource)
        temp_res_online = copy.deepcopy(self.res_online)
        try:
            mode = NFFG.MODE_ADD
            
            self.res_online = online_mapping.MAP(request, self.res_online,
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
                      "Unhandled exception cought during online mapping :( ")
            raise
        finally:
            self.res_online_protector.finish_writing_res_nffg("Online mapping finished or failed")

    def do_offline_mapping(self):
            try:
                self.sum_req_protector.start_reading_res_nffg("Determine set of requests to optimize")
                self.reqs_under_optimization = self.__what_to_opt.reqs_to_optimize(self.SUM_req)
                self.sum_req_protector.finish_reading_res_nffg("Got requests to optimize")
                log.debug("SAP count in request %s and in resource: %s, resource total size: %s"%
                        (len([s for s in self.reqs_under_optimization.saps]),
                          len([s for s in self.__res_offline.saps]), len(self.__res_offline)))
                self.offline_status = HybridOrchestrator.OFFLINE_STATE_RUNNING

                self.__res_offline = offline_mapping.MAP(
                    self.reqs_under_optimization, self.__res_offline, self.optimize_already_mapped_nfs,
                    self.mig_handler, self.migration_coeff, self.load_balance_coeff,
                    self.edge_cost_coeff)

                log.info("Offline mapping is ready")

                log.info("Delete expired requests from the request summary")
                self.del_exp_reqs_from_SUMreq()
                log.info("Try to merge online and offline")
                # the merge MUST set the state before releasing the writeing lock
                self.merge_online_offline()
            except uet.MappingException as e:
                log.warn(e.msg)
                log.warn("Mapping thread: "
                          "Offline mapping: Unable to mapping offline!")
                # Balazs: in case the MILP fails with MappingException we can continue working.
                self.offline_status = HybridOrchestrator.OFFLINE_STATE_INIT

    def del_exp_reqs_from_SUMreq(self):
        mode = NFFG.MODE_DEL
        # We had better lock sum_req for the whole function to give some priority for the
        # offline-online RG merging over the online mapping
        self.sum_req_protector.start_writing_res_nffg("Removing expired request from sum_req")
        try:
          for i in self.deleted_services:
              delete = False
              for j in i['SG'].nfs:
                  if j.id in [nf.id for nf in self.__res_offline.nfs]:
                      delete = True
                      j.operation = NFFG.OP_DELETE
              if delete:
                log.debug("Deleting NFs from res_offline due to expiration during the "
                          "offline optimization: %s"%i['SG'].network.nodes())
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

                self.SUM_req = online_mapping.MAP(i['SG'],
                                                  self.SUM_req,
                                                  mode=mode)
        except uet.UnifyException as ue:
          log.error("UnifyException catched during deleting expired requests from sum_req")
          log.error(ue.msg)
          raise
        except Exception as e:
          log.error("Unhandled exception catched during deleting expired requests from sum_req")
          raise
        finally:
          self.sum_req_protector.finish_writing_res_nffg("Removed or failed during expired "
                                                         "request deletion from sum_req")

    def set_online_resource_graph(self, resource):
        # Resource sharing strategy
        try:
            log.debug("Setting online resource for sharing between "
                      "online and offline resources")
            if self.offline_status == HybridOrchestrator.OFFLINE_STATE_RUNNING or \
                  self.offline_status == HybridOrchestrator.OFFLINE_STATE_INIT:
              # The online_res may be under merge OR offline reoptimization is idle because it was not needed.
              self.res_online = self.__res_sharing_strat.get_online_resource(resource,
                                                                             self.__res_offline)
              log.debug("Setting online based on received resource!")
            elif self.offline_status == HybridOrchestrator.OFFLINE_STATE_FINISHED:
              # we need to set res_online based on the reoptimized resource not the one handled by our caller
              # lock is not needed because offline is terminated.
              self.res_online = self.__res_sharing_strat.get_online_resource(self.reoptimized_resource,
                                                                             self.__res_offline)
              log.debug("Setting online resource based on reoptimized resource!")
              self.offline_status = HybridOrchestrator.OFFLINE_STATE_INIT
            else:
              raise Exception("Invalid offline_status: %s"%self.offline_status)
        except Exception as e:
            log.error(e.message)
            log.error("Unhandled Exception catched during resource sharing.")
            raise
        log.debug("Setting online resource")

    def set_offline_resource_graph(self):
      # Resources sharing startegy
      self.res_online_protector.start_reading_res_nffg("Setting offline resource")
      self.__res_offline = self.__res_sharing_strat.get_offline_resource(self.res_online,
                                                                         self.__res_offline)
      self.res_online_protector.finish_reading_res_nffg("Offline resource was set")

    def merge_online_offline(self):
            try:
                self.res_online_protector.start_writing_res_nffg("Removing SC-s which are possibly migrated and merging")
                before_merge = copy.deepcopy(self.res_online)
                # Balazs: Delete requests from res_online, which are possibly migrated
                # NOTE: if an NF to be deleted doesn't exist in the substrate DEL mode ignores it.
                log.debug("merge_online_offline: Removing NFs to be migrated from "
                          "res_online: %s"%self.reqs_under_optimization.network.nodes())
                possible_reqs_to_migrate = copy.deepcopy(self.reqs_under_optimization)
                for nf in possible_reqs_to_migrate.nfs:
                  nf.operation = NFFG.OP_DELETE
                # if there is NF which is not in res_online anymore, DEL mode ignores it
                # TODO: should we make another copy of res_online and delete the expired reqs from that copy? Otherwise returning with a copy of res_online may return with the "possible reqs to migratate" deleted
                self.res_online = online_mapping.MAP(possible_reqs_to_migrate,
                                                     self.res_online,
                                                     propagate_e2e_reqs=False,
                                                     mode=NFFG.MODE_DEL)
                log.debug("merge_online_offline: Applying offline optimization...")
                self.reoptimized_resource = NFFGToolBox.merge_nffgs(self.res_online,
                                                                    self.__res_offline)
                try:
                  # Checking whether the merge was in fact successful according to resources.
                    self.reoptimized_resource.calculate_available_node_res()
                    self.reoptimized_resource.calculate_available_link_res([])

                    log.info("merge_online_offline : "
                             "Optimization applied successfully :)")
                    self.offline_status = HybridOrchestrator.OFFLINE_STATE_FINISHED
                # Balazs The calc res functions throw only RuntimeError if it is
                # failed due to resource reservation collision!
                except RuntimeError as e:
                    self.res_online = before_merge
                    log.warn(e.message)
                    # We continue to work from this stage, we can try optimization again
                    log.warn("Unable to merge online and offline :(")
                    self.offline_status = HybridOrchestrator.OFFLINE_STATE_INIT
            except Exception as e:
                log.error(e.message)
                # Balazs: this exception is fatal
                log.error("Unhandled Exception during merge :(")
                self.offline_status = HybridOrchestrator.OFFLINE_STATE_INIT
                raise
            finally:
                self.res_online_protector.finish_writing_res_nffg("Merged or failed during merging "
                                                                    "res_online and the optimized res_offline")

    def MAP(self, request, resource):

        # Collect the requests
        self.merge_all_request(self.SUM_req, request)

        # Start online mapping thread
        online_mapping_thread = threading.Thread(None, self.do_online_mapping,
                        "Online mapping thread", [request, resource])
        try:
            log.info("Start online mapping!")
            online_mapping_thread.start()
        except Exception as e:
            log.error(e.message)
            log.error("Failed to start online thread")
            #Balazs Why Raise runtime?? why not the same Exception
            raise # RuntimeError

        # Start offline mapping thread
        # check if there is anything to optimize
        self.res_online_protector.start_reading_res_nffg("Check if there is anything to optimize")
        if len([n for n in self.res_online.nfs]) > 0:
          self.res_online_protector.finish_reading_res_nffg("Checking if there was anything to optimize (yes)")
          if self.__when_to_opt.need_to_optimize(self.offline_status==HybridOrchestrator.OFFLINE_STATE_INIT, 3):
              try:
                  self.set_offline_resource_graph()
                  self.offline_mapping_thread = threading.Thread(None,
                              self.do_offline_mapping, "Offline mapping thread", [])
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
        else:
          self.res_online_protector.finish_reading_res_nffg("Checking if there was anything to optimize (no)")

        online_mapping_thread.join()

        if not self.online_fails.empty():
            error = self.online_fails.get()
            raise uet.MappingException(error.msg, False)

        self.res_online_protector.start_reading_res_nffg("Returning independent copy of res_online")
        res_online_to_return = copy.deepcopy(self.res_online)
        self.res_online_protector.finish_reading_res_nffg("Got independent copy for return")
        return res_online_to_return











