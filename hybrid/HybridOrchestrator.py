import threading

import datetime
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
from hybrid.OptimizationDataHandler import *
import milp.milp_solution_in_nffg as offline_mapping
import alg1.MappingAlgorithms as online_mapping
import alg1.UnifyExceptionTypes as uet
import Queue
from memory_profiler import profile
from memory_profiler import memory_usage
log = logging.getLogger(" Hybrid Orchestrator")


class ResNFFGProtector(object):

  def __init__(self, lock_name, do_logging=False):
    self.readers_count = 0
    self.reader_counter_protector = threading.Lock()
    self.res_nffg_protector = threading.Lock()
    self.do_logging = do_logging
    self.lock_name = lock_name

  def start_reading_res_nffg(self, read_reason):
    self.reader_counter_protector.acquire()
    self.readers_count += 1
    if self.readers_count == 1:
      self.res_nffg_protector.acquire()
      if self.do_logging:
        log.debug("Locking %s nffg for reading: \"%s\", number of current readers: %s"
                  %(self.lock_name, read_reason, self.readers_count))
    self.reader_counter_protector.release()

  def finish_reading_res_nffg(self, read_reason):
    self.reader_counter_protector.acquire()
    self.readers_count -= 1
    if self.readers_count < 0:
      raise RuntimeError("Some thread tried to release reading right on res_online multiple times!")
    if self.readers_count == 0:
      self.res_nffg_protector.release()
      if self.do_logging:
        log.debug("Releasing %s nffg for reading: \"%s\", number of current readers: %s"
                  %(self.lock_name, read_reason, self.readers_count))
    self.reader_counter_protector.release()

  def start_writing_res_nffg(self, write_reason):
    self.res_nffg_protector.acquire()
    if self.do_logging:
      log.debug("Locking %s nffg for writing: \"%s\"."%(self.lock_name, write_reason))

  def finish_writing_res_nffg(self, write_reason):
    self.res_nffg_protector.release()
    if self.do_logging:
      log.debug("Releasing %s nffg for writing: \"%s\"."%(self.lock_name, write_reason))


class HybridOrchestrator():

    OFFLINE_STATE_INIT = 0
    OFFLINE_STATE_RUNNING = 1
    OFFLINE_STATE_FINISHED = 2

    def __init__(self, RG, config_file_path, deleted_services, full_log_path,
                 resource_type, remaining_request_lifetimes):

            config = ConfigObj(config_file_path)

            formatter = logging.Formatter(
                '%(asctime)s | Hybrid Orches | %(levelname)s | \t%(message)s')
            hdlr = logging.FileHandler(full_log_path)
            hdlr.setFormatter(formatter)
            log.addHandler(hdlr)
            log.setLevel(logging.DEBUG)

            # Protects the res_online
            self.res_online_protector = ResNFFGProtector("res_online", True)
            self.res_online = None
            self.res_offline = copy.deepcopy(RG)
            self.deleted_services = deleted_services

            #TODO: ellenorizni hogy itt nem e copy-t kell atadni
            self.remaining_request_lifetimes = remaining_request_lifetimes

            # All request in one NFFG
            # The sum of reqs needs to be accessed from Offline optimization to determine
            # what to opt and online mapping have to gather all requests there
            self.sum_req_protector = ResNFFGProtector("sum_req", True)
            self.SUM_req = NFFG()
            self.offline_mapping_thread = None
            self.offline_status = HybridOrchestrator.OFFLINE_STATE_INIT
            self.reoptimized_resource = None
            self.when_to_opt_param = int(float(config['when_to_opt_parameter']))


            # What to optimize strategy
            what_to_opt_strat = config['what_to_optimize']
            if what_to_opt_strat == "reqs_since_last":
                self.__what_to_opt = ReqsSinceLastOpt(full_log_path, config_file_path, resource_type)
            elif what_to_opt_strat == "all_reqs":
                self.__what_to_opt = AllReqsOpt(full_log_path, config_file_path, resource_type)
            elif what_to_opt_strat == "reqs_lifetime":
                self.__what_to_opt = ReqsBasedOnLifetime(full_log_path, config_file_path, resource_type)
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
            elif when_to_opt_strat == "always":
                self.__when_to_opt = Always(full_log_path)
            else:
                raise ValueError(
                    'Invalid when_to_opt type! Please choose '
                                   'one of the followings: modell_based, '
                                   'fixed_req_count, fixed_time, '
                                   'periodical_model_based, always')

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

            self.optional_milp_params = {}
            if 'time_limit' in config:
              self.optional_milp_params['time_limit'] = int(config['time_limit'])
            if 'mip_gap_limit' in config:
              self.optional_milp_params['mip_gap_limit'] = float(config['mip_gap_limit'])
            if 'node_limit' in config:
              self.optional_milp_params['node_limit'] = int(config['node_limit'])
            self.optional_milp_params.update(**config['migration_handler_kwargs'])

            self.offline_mapping_num = 0

    def merge_all_request(self, request):
        self.sum_req_protector.start_writing_res_nffg("Appending new request to the "
                                                      "sum of requests")
        self.SUM_req = NFFGToolBox.merge_nffgs(self.SUM_req, request)
        log.debug("Requests in SUM_req: %s"%len([r.sg_path for r in self.SUM_req.reqs]))
        self.sum_req_protector.finish_writing_res_nffg("New request %s appended to "
                                                       "sum req" % request)

    def do_online_mapping(self, request, resource):
        self.set_online_resource_graph(resource, request)
        # keep_input_unchanged=True makes it unnecessary
        # temp_res_online = copy.deepcopy(self.res_online)

        try:
            # propagate_e2e_reqs must be turned False (so they are not tried to
            # be splitted and the e2e versions removed!) We want to keep them in
            # the res_online, so reoptimization wouldn't hurt violate them!
            self.res_online = online_mapping.MAP(request, self.res_online,
                                            bw_factor=1, res_factor=1,
                                            lat_factor=1,
                                            shortest_paths=None,
                                            return_dist=False,
                                            propagate_e2e_reqs=False,
                                            bt_limit=6,
                                            bt_branching_factor=3, mode=NFFG.MODE_ADD,
                                            keep_e2e_reqs_in_output=False,
                                            keep_input_unchanged=True)

            log.info("do_online_mapping : Successful online mapping :)")
        except uet.MappingException as error:
            log.warning("do_online_mapping : Unsuccessful online mapping :( ")
            log.warning(error.msg)
            # keep_input_unchanged=True makes it unnecessary
            # self.res_online = temp_res_online
            self.online_fails.put(error)
            # Balazs: an online failure due to mapping is natural, we continue working.
        except Exception as e:
            # Balazs: exception is not thrown when acquire didnt succeed, this exception is fatal
            log.error(str(e.message) + str(e.__class__))
            log.error("do_online_mapping : "
                      "Unhandled exception cought during online mapping :( ")
            raise

    fp = open('memory_profiler.log', 'a')
    @profile(stream=fp)
    def do_offline_mapping(self):

            mem_in_beginning = 0
            try:
                mem_in_beginning = memory_usage(-1, interval=1, timeout=1)
                log.debug("Total MEMORY usage in the beginning of the do_offline_mapping: "+ str(mem_in_beginning)+" MB")
                self.offline_status = HybridOrchestrator.OFFLINE_STATE_RUNNING
                # WARNING: we can't lock both of them at the same time, cuz that can cause deadlock
                # If both of them needs to be locked make the order: res_online -> sum_req!
                self.set_offline_resource_graph()

                # read what shall we optimize.
                self.sum_req_protector.start_reading_res_nffg("Determine set of requests to optimize")
                self.del_exp_reqs_from_sum_req()
                self.reqs_under_optimization = self.__what_to_opt.reqs_to_optimize(self.SUM_req,
                                                                                   self.remaining_request_lifetimes)
                tmp_sum_req = copy.deepcopy(self.SUM_req)
                self.sum_req_protector.finish_reading_res_nffg("Got requests to optimize")
                log.debug("SAP count in request %s and in resource: %s, resource total size: %s" %
                          (len([s for s in self.reqs_under_optimization.saps]),
                           len([s for s in self.res_offline.saps]),
                           len(self.res_offline)))

                # set mapped NF reoptimization True, and delete other NFs from
                # res_offline which are not in reqs_under_optimization, because
                # it is what_to_opt's responsibilty to determine the set of requests to optimize!
                # ignore_infras=True calculates the difference only on the SG.
                self.res_offline = NFFGToolBox.recreate_all_sghops(self.res_offline)
                _, reqs_not_to_be_opt = NFFGToolBox.generate_difference_of_nffgs(
                  self.res_offline,
                  self.reqs_under_optimization,
                  ignore_infras=True)

                # Remove infras from del graph to avoid unnecessary warning during delete.
                for infra in [i for i in reqs_not_to_be_opt.infras]:
                  reqs_not_to_be_opt.del_node(infra)
                if len([n for n in self.reqs_under_optimization.nfs]) == 0:
                  raise uet.MappingException("Offline didn't get any requests to optimize",
                                             False)
                not_top_opt_nfs = [n.id for n in reqs_not_to_be_opt.nfs]
                # Even in case of all_reqs strategy this may be non zero, in
                # case a deletion happened during execution of this function.
                log.debug("Removing requests (%s NFs) from res_offline which "
                          "shouldn't be optimized! Examples: %s"%(len(not_top_opt_nfs),
                                                                  not_top_opt_nfs[:20]))
                if len(not_top_opt_nfs) > 0:
                  # NOTE: generate_difference_of_nffgs doesn't return with the
                  # EdgeReqs! This is an ugly solution!!!
                  for req in tmp_sum_req.reqs:
                    if req.sg_path[0] in [sg.id for sg in reqs_not_to_be_opt.sg_hops]:
                      self.res_offline.del_edge(req.src.node.id, req.dst.node.id,
                                                id=req.id)
                  self.res_offline = online_mapping.MAP(reqs_not_to_be_opt,
                                                        self.res_offline,
                                                        mode=NFFG.MODE_DEL,
                                                        keep_input_unchanged=True)
                log.debug("Adding %s path requirements to offline resource."
                          %len([r for r in self.reqs_under_optimization.reqs]))
                for req in self.reqs_under_optimization.reqs:
                  if not self.res_offline.network.has_edge(req.src.node.id,
                                                           req.dst.node.id, key=req.id):
                    # Bandwidth requirements of SGhops are already known by the
                    # flowrules!! IF we would keep the EdgeReqs with non-zero
                    # bandwidth, they would count as additional bw!
                    # Only the delay is important in this case!
                    req.bandwidth = 0.0
                    # port objects are set correctly by NFFG lib
                    self.res_offline.add_req(req.src, req.dst, req=req)
                    # log.debug("Adding requirement with zero-ed bandwidth on "
                    #           "path %s"%req.sg_path)

                # we don't want to map additional requests, so set request to empty
                self.res_offline = offline_mapping.MAP(
                    NFFG(), self.res_offline, True,
                    self.mig_handler, self.migration_coeff, self.load_balance_coeff,
                    self.edge_cost_coeff, **self.optional_milp_params)

                mem_usage = memory_usage(-1, interval=1, timeout=1)
                log.debug("Total MEMORY usage in the end of the do_offline_mapping: " + str(mem_usage) + " MB")
                log.debug("Total MEMORY difference: " + str(mem_usage[0] - mem_in_beginning[0]) + " MB")

                # Need to del_exp_reqs_from_res_offline and merge
                log.info("Try to merge online and offline")
                # the merge MUST set the state before releasing the writing lock
                self.merge_online_offline()
                self.__what_to_opt.opt_data_handler.write_data(
                    len([n for n in self.reqs_under_optimization.nfs]),
                    (time.time() - self.offline_start_time ))

                self.offline_start_time = 0
                log.info("Offline mapping is ready!")

            except uet.MappingException as e:
                mem_usage = memory_usage(-1, interval=1, timeout=1)
                log.debug("Total MEMORY usage after mapping error of the do_offline_mapping: " + str(mem_usage)+" MB")
                log.debug("Total MEMORY difference: " + str(mem_usage[0] - mem_in_beginning[0]) + " MB")
                log.warn(e.msg)
                log.warn("Mapping thread: "
                          "Offline mapping: Unable to mapping offline!")
                # Balazs: in case the MILP fails with MappingException we can continue working.
                self.offline_status = HybridOrchestrator.OFFLINE_STATE_INIT
            except Exception as e:
                mem_usage = memory_usage(-1, interval=1, timeout=1)
                log.debug("Total MEMORY usage after error of the do_offline_mapping: " + str(mem_usage)+" MB")
                log.debug("Total MEMORY difference: " + str(mem_usage[0] - mem_in_beginning[0]) + " MB")
                if hasattr(e, 'msg'):
                  msg = e.msg
                else:
                  msg = e.message
                log.error("Offline mapping failed: with exception %s, message:"
                          " %s"%(e,msg))
                raise

    def del_exp_reqs_from_nffg(self, self_nffg_name):
        try:
          for i in self.deleted_services:
              delete = False
              for j in i['SG'].nfs:
                  if j.id in [nf.id for nf in getattr(self, self_nffg_name).nfs]:
                      delete = True
                      j.operation = NFFG.OP_DELETE
              if delete:
                log.debug("Deleting NFs from %s due to expiration during the "
                          "offline optimization: %s" %
                          (self_nffg_name, i['SG'].network.nodes()))
                for req in i['SG'].reqs:
                  getattr(self, self_nffg_name).del_edge(req.src.node.id,
                                                         req.dst.node.id, id=req.id)
                  log.debug("Deleting E2E requirement from %s on path %s" %
                            (self_nffg_name, req.sg_path))
                setattr(self, self_nffg_name, online_mapping.MAP(i['SG'],
                                              getattr(self, self_nffg_name),
                                              mode=NFFG.MODE_DEL,
                                              keep_input_unchanged=True))

        except uet.UnifyException as ue:
          log.error("UnifyException catched during deleting expired "
                    "requests from %s" % self_nffg_name)
          log.error(ue.msg)
          raise
        except Exception as e:
          log.error("Unhandled exception catched during deleting expired "
                    "requests from %s" % self_nffg_name)
          raise

    def remove_sg_from_sum_req(self, request):
      """
      Removes request from SUM_req, the sum_req protector lock must be called
      around it!
      :param request:
      :return:
      """
      # The MAP function removed from NFFGs which represent mappings,
      # removal from an SG collection is much easier.
      nf_deleted = False
      for nf in request.nfs:
        self.SUM_req.del_node(nf.id)
        nf_deleted = True
      # if nf_deleted:
      #   log.debug("Deleted NFs of request %s from sum_req"%request.id)
      req_deleted = False
      for req in request.reqs:
        self.SUM_req.del_edge(req.src.node.id, req.dst.node.id, id=req.id)
        req_deleted = True
      # if req_deleted:
      #   log.debug("Deleted EdgeReq on path %s from sum_req"%
      #             [r for r in request.reqs])
      if nf_deleted and not req_deleted:
        raise Exception("NFs were removed from sum_req, but their EdgeReq wasn't!")
      for sap in request.saps:
        # if sap.id is a string it may try to iterate in it... so we can
        # prevent this with checking whether it contains this node.
        if sap.id in self.SUM_req.network:
          if self.SUM_req.network.out_degree(sap.id) + \
             self.SUM_req.network.in_degree(sap.id) == 0:
            self.SUM_req.del_node(sap.id)

    def del_exp_reqs_from_sum_req(self):
      log.debug("Deleting expired requests from sum_req.")
      for i in self.deleted_services:
        self.remove_sg_from_sum_req(i['SG'])

    def set_online_resource_graph(self, resource, request):
        # Resource sharing strategy
        try:
            log.debug("Setting online resource for sharing between "
                      "online and offline resources")
            if self.offline_status == HybridOrchestrator.OFFLINE_STATE_RUNNING or \
                  self.offline_status == HybridOrchestrator.OFFLINE_STATE_INIT:
              # The online_res may be under merge OR offline reoptimization is idle because it was not needed.
              self.res_online = self.__res_sharing_strat.get_online_resource(resource,
                                                                             self.res_offline)
              log.debug("Setting online resource based on received resource "
                        "for request %s!"%request.id)
            elif self.offline_status == HybridOrchestrator.OFFLINE_STATE_FINISHED:
              # we need to set res_online based on the reoptimized resource not the one handled by our caller.
              # An expiration could have happened while we were merging or waiting for res_online setting.
              self.del_exp_reqs_from_nffg("reoptimized_resource")
              # lock is not needed because offline is terminated.
              self.res_online = self.__res_sharing_strat.get_online_resource(self.reoptimized_resource,
                                                                             self.res_offline)
              log.debug("Setting online resource based on reoptimized resource "
                        "for request %s!"%request.id)
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
      self.res_offline = self.__res_sharing_strat.get_offline_resource(self.res_online,
                                                                       self.res_offline)
      self.del_exp_reqs_from_nffg("res_offline")
      self.res_online_protector.finish_reading_res_nffg("Offline resource was set")

    def merge_online_offline(self):
            try:
                self.res_online_protector.start_writing_res_nffg("Removing SC-s which are possibly migrated and merging")
                starting_time = datetime.datetime.now()

                log.info("Delete expired requests from the res_offline")
                # so we won't fail in merging due to already expired services.
                # res_offline for multi-threaded writing is also covered by the
                # res_online_protector
                self.del_exp_reqs_from_nffg("res_offline")

                # res_online always contains only the alive and currently mapped requests!
                self.reoptimized_resource = copy.deepcopy(self.res_online)
                # Balazs: Delete requests from res_online, which are possibly migrated
                # NOTE: if an NF to be deleted doesn't exist in the substrate DEL mode ignores it.
                log.debug("merge_online_offline: Removing NFs to be migrated from "
                          "res_online, examples: %s"%self.reqs_under_optimization.network.nodes()[:20])
                # deepcopy is not necessary here, SUM_req (at least its relevant subset) is copied
                possible_reqs_to_migrate = self.reqs_under_optimization
                for nf in possible_reqs_to_migrate.nfs:
                  nf.operation = NFFG.OP_DELETE
                # if there is NF which is not in res_online anymore, DEL mode ignores it
                for req in possible_reqs_to_migrate.reqs:
                  self.reoptimized_resource.del_edge(req.src.node.id, req.dst.node.id, id=req.id)
                self.reoptimized_resource = online_mapping.MAP(possible_reqs_to_migrate,
                                                     self.reoptimized_resource,
                                                     mode=NFFG.MODE_DEL,
                                                     keep_input_unchanged=True)
                log.debug("merge_online_offline: Applying offline optimization...")
                self.reoptimized_resource = NFFGToolBox.merge_nffgs(self.reoptimized_resource,
                                                                    self.res_offline)
                starting_time = datetime.datetime.now()
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
                log.debug("Time passed with merging online and offline resources: %s"%
                          (datetime.datetime.now() - starting_time))
                self.res_online_protector.finish_writing_res_nffg("Merged or failed during merging "
                                                                    "res_online and the optimized res_offline")

    def MAP(self, request, resource):

        # Start online mapping thread
        online_mapping_thread = threading.Thread(None, self.do_online_mapping,
                        "Online mapping thread", [request, resource])
        try:
            log.info("Start online mapping!")
            # res_online surely shouldn't be modified while an online mapping
            # is in progress! Until we return with its copy where the new
            # request is also mapped.
            self.res_online_protector.start_writing_res_nffg(
              "Map a request in an online manner")
            online_mapping_thread.start()
        except Exception as e:
            log.error(e.message)
            log.error("Failed to start online thread")
            #Balazs Why Raise runtime?? why not the same Exception
            raise # RuntimeError

        # Start offline mapping thread
        # check if there is anything to optimize
        if self.res_online is not None and len([n for n in self.res_online.nfs]) > 0:
          if self.__when_to_opt.need_to_optimize(not self.offline_status==HybridOrchestrator.OFFLINE_STATE_INIT, self.when_to_opt_param):
              try:
                  self.offline_mapping_thread = threading.Thread(None,
                              self.do_offline_mapping, "Offline mapping thread", [])
                  log.info("Start offline optimalization!")
                  self.offline_start_time = time.time()
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
            self.res_online_protector.finish_writing_res_nffg("Online mapping failed")
            raise uet.MappingException(error.msg, False)

        res_online_to_return = copy.deepcopy(self.res_online)
        self.res_online_protector.finish_writing_res_nffg("Online mapping finished")

        # Collect the requests
        # NOTE: only after we know for sure, this request is mapped and the other
        # lock is released (to avoid deadlock)
        self.merge_all_request(request)

        return res_online_to_return











