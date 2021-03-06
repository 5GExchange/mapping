# Copyright 2017 Balazs Nemeth
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Core functions and classes of Algorithm1.
"""

import copy
from collections import deque

import networkx as nx

import Alg1_Helper as helper
import BacktrackHandler as backtrack
import GraphPreprocessor
import UnifyExceptionTypes as uet
from Alg1_Helper import NFFG, NFFGToolBox
from MappingManager import MappingManager


class CoreAlgorithm(object):
  def __init__ (self, net0, req0, chains0, mode, cache_shortest_path,
                overall_highest_delay,
                bw_factor=1, res_factor=1, lat_factor=1, shortest_paths=None,
                dry_init=False, propagate_e2e_reqs=True,
                keep_e2e_reqs_in_output=False):
    self.log = helper.log.getChild(self.__class__.__name__)
    self.log.setLevel(helper.log.getEffectiveLevel())

    self.log.info("Initializing algorithm variables")

    # needed for reset()
    self.req0 = copy.deepcopy(req0)
    self.net0 = copy.deepcopy(net0)

    self.original_chains = chains0
    self.enable_shortest_path_cache = cache_shortest_path
    self.mode = mode

    # parameters contolling the backtrack process
    # how many of the best possible VNF mappings should be remembered
    self.bt_branching_factor = 3
    self.bt_limit = 6

    # If dry_init the algorithm initialization avoids every calculation
    # intensive step, could be used to change the mapping structure and
    # construct an output NFFG based on a custom mapping structure
    self.dry_init = dry_init
    if dry_init:
      self.log.warn("Dry initialization! The start function won't be able to "
                    "run, because only minimal preprocessing was done!")
    if keep_e2e_reqs_in_output and propagate_e2e_reqs:
      raise uet.BadInputException(
        "Cannot propagate and keep E2E requirements in the output NFFG",
        "Both 'keep_e2e_reqs_in_output' and 'propagate_e2e_reqs' are set to "
        "True!")
    self.keep_e2e_reqs_in_output = keep_e2e_reqs_in_output
    self.propagate_e2e_reqs = propagate_e2e_reqs

    self._preproc(net0, req0, chains0, shortest_paths, overall_highest_delay)

    # must be sorted in alphabetic order of keys: cpu, mem, storage
    self.resource_priorities = [0.333, 0.333, 0.333]

    # which should count more in the objective function
    self.bw_factor = bw_factor
    self.res_factor = res_factor
    self.lat_factor = lat_factor

    # The new preference parameters are f(x) == 0 if x<c and f(1) == e,
    # exponential in between.
    # The bandwidth parameter refers to the average link utilization
    # on the paths to the nodes (and also collocated request links).
    # If  the even the agv is high it is much worse!
    self.pref_params = dict(cpu=dict(c=0.4, e=2.5), mem=dict(c=0.4, e=2.5),
                            storage=dict(c=0.4, e=2.5),
                            bandwidth=dict(c=0.1, e=10.0))

    # Functions to give the prefence values of a given ratio of resource
    # utilization. All fucntions should map every number between [0,1] to [0,1]
    # real intervals and should be monotonic!
    self.pref_funcs = dict(cpu=self._pref_noderes, mem=self._pref_noderes,
                           storage=self._pref_noderes, bandwidth=self._pref_bw)

    # we need to store the original preprocessed NFFG too. with remove VNF-s 
    # and not STATIC links
    self.bare_infrastucture_nffg = self.net

    # peak number of VNFs that were mapped to resource at the same time
    self.peak_mapped_vnf_count = 0
    self.sap_count = len([i for i in self.req.saps])

    # The networkx graphs from the NFFG should be enough for the core
    # unwrap them, to save one indirection after the preprocessor has
    # finished.
    self.net = self.net.network
    self.req = self.req.network

  def _preproc (self, net0, req0, chains0, shortest_paths,
                overall_highest_delay):
    self.log.info("Preprocessing:")

    # 100 000ms is considered to be infinite latency
    self.manager = MappingManager(net0, req0, chains0,
                                  overall_highest_delay, self.dry_init)

    self.preprocessor = GraphPreprocessor.GraphPreprocessorClass(net0, req0,
                                                                 chains0,
                                                                 self.manager)
    self.preprocessor.shortest_paths = shortest_paths
    self.net = self.preprocessor.processNetwork(self.mode,
                                                self.enable_shortest_path_cache,
                                                self.dry_init)
    self.req, chains_with_subgraphs = self.preprocessor.processRequest(
      self.mode, self.net, self.dry_init)
    if not self.dry_init:
      self.bt_handler = backtrack.BacktrackHandler(chains_with_subgraphs,
                                                   self.bt_branching_factor,
                                                   self.bt_limit)
    else:
      self.req = req0

  def _checkBandwidthUtilOnHost (self, i, bw_req):
    """
    Checks if a host can satisfy the bandwidth requirement, returns its
    utilization if yes, or 0 if it is a SAP, -1 if it can`t satisfy.
    """
    if self.net.node[i].type != 'SAP':
      # if first element is a NodeInfra, then traffic also needs
      # to be steered out from the previously mapped VNF.
      if self.net.node[i].availres['bandwidth'] < bw_req:
        self.log.debug(
          "Host %s has only %f Mbps capacity but %f is required." % (
            i, self.net.node[i].availres['bandwidth'], bw_req))
        return -1, None
      else:
        if self.net.node[i].resources['bandwidth'] == float("inf"):
          return 0, 0
        util_of_host = float(self.net.node[i].resources['bandwidth'] - (
          self.net.node[i].availres['bandwidth'] - bw_req)) / \
                       self.net.node[i].resources['bandwidth']
        return 0, util_of_host
    else:
      return 1, 0

  def _calculateAvgLinkUtil (self, path_to_map, linkids, bw_req, vnf_id=None):
    """Checks if the path can satisfy the bandwidth requirement.
    Returns the average link utilization on the path if
    that path is feasible with bw_req, -1 otherwise.
    If vnf_id is None, then the path`s end is already mapped."""
    sum_w = 0
    internal_bw_req = 0
    sap_count_on_path = 0
    if vnf_id is not None:
      if self.req.node[vnf_id].resources['bandwidth'] is not None:
        internal_bw_req = self.req.node[vnf_id].resources['bandwidth']
        # this is only a preliminary check (the bw_req should also be
        # accomadated
        # by the hosting node)
        avail_bw = self.net.node[path_to_map[-1]].availres[
                     'bandwidth'] - internal_bw_req
        if avail_bw < 0:
          return -1

    if len(path_to_map) > 1:
      for i, j, k in zip(path_to_map[:-1], path_to_map[1:], linkids):
        if self.net[i][j][k].availbandwidth < bw_req:
          self.log.debug(
            "Link %s, %s has only %f Mbps capacity, but %f is required." % (
              i, j, self.net[i][j][k].availbandwidth, bw_req))
          return -1
        else:
          if not self.net[i][j][k].bandwidth == float("inf"):
            sum_w += float(self.net[i][j][k].bandwidth - (
              self.net[i][j][k].availbandwidth - bw_req)) / self.net[i][j][
                       k].bandwidth
        # either only steers the traffic through a host or at the
        # beginning of the path, steers out from the VNF
        is_it_sap, util = self._checkBandwidthUtilOnHost(i, bw_req)
        if is_it_sap >= 0:
          sap_count_on_path += is_it_sap
          sum_w += util
        else:
          return -1

      # The last node of the path should also be considered:
      #  - it is a SAP or
      #  - the traffic is steered into the to-be-mapped VNF
      is_it_sap, util = self._checkBandwidthUtilOnHost(path_to_map[-1],
                                                       bw_req + internal_bw_req)
      if is_it_sap >= 0:
        sap_count_on_path += is_it_sap
        sum_w += util
      else:
        return -1
      sum_w /= (len(path_to_map) - 1) + (len(path_to_map) - sap_count_on_path)

    elif len(path_to_map) == 0:
      self.log.warn(
        "Tried to calculate average link utilization on 0 length path!")
      return -1

    else:
      # required when trying to collocate two ends of a link.
      act_bw = self.net.node[path_to_map[0]].availres['bandwidth']
      max_bw = self.net.node[path_to_map[0]].resources['bandwidth']
      # sum of the two bw reqs are subtracted from guaranteed bw between
      # all (static and dynamic) ports of the host (BiS-BiS)
      if max_bw < float("inf"):
        sum_w = float(max_bw - (act_bw - bw_req - internal_bw_req)) / max_bw
      else:
        sum_w = 0.0
      if act_bw < bw_req + internal_bw_req:
        self.log.debug(
          "Node %s don`t have %f Mbps capacity for mapping a link." % (
            path_to_map[0], bw_req))
        return -1
        # path has only one element, so sum_w is already average.

    # Utilization of host-internal bandwidths are also included.
    return sum_w

  def _sumLatencyOnPath (self, path_to_map, linkids):
    """Summarizes all latency (link, and forwarding) on the path.
    prev_vnf_id is the already mapped and vnf_id is the to-be-placed
    VNF in the greedy process.
    Latency requirement satisfaction should be checked outside of this
    function, should be done by the helper functions of MappingManager.
    """
    sum_lat = 0
    try:

      if len(path_to_map) > 1:
        # routing the traffic from the previously used host to its
        # outbound port takes time too.(host`s lat is between all ports)
        if self.net.node[path_to_map[0]].type != 'SAP':
          sum_lat += self.net.node[path_to_map[0]].resources['delay']

        for i, j, k in zip(path_to_map[:-1], path_to_map[1:], linkids):
          sum_lat += self.net[i][j][k].delay
          if self.net.node[j].type != 'SAP':
            sum_lat += self.net.node[j].resources['delay']

      elif len(path_to_map) == 1:
        # In this case, collocation is about to happen
        # if there is VNF internal requirement, that should be forwarded
        # to the lower orchestration layer.
        # But forwarding from the previous VNF to the collocated one
        # takes latency between a pair of dynamic ports

        # TODO: ERDay branch hacking to resolve BiSBiS latency model mismatch
        # sum_lat = 0
        sum_lat = self.net.node[path_to_map[0]].resources['delay']

      else:
        self.log.warn("Tried to check latency sum on 0 length path!")
        return -1

    except KeyError as e:
      raise uet.BadInputException(" node/edge data: %s data not found." % e)
    return sum_lat

  # UNUSED NOW
  def _preferenceValueOfUtilization (self, x, attr):
    c = self.pref_params[attr]['c']
    e = self.pref_params[attr]['e']
    if x < c:
      return 0.0
    else:
      return (e + 1) ** float((x - c) / (1 - c)) - 1

  def _pref_noderes (self, x):
    if x < 0.2:
      return 0.0
    else:
      return 1.25 * x - 0.25

  def _pref_bw (self, x):
    if x < 0.2:
      return 0.0
    else:
      return -1.5625 * ((x - 1) ** 2) + 1

  def _checkAntiAffinityCriteria (self, node_id, vnf_id, bt_record):
    """
    Checks whether there is an anti-affinity criteria for this 
    host wich may spoil the greedy mapping of this VNF. 
       Anti-affinitity: if this is not the host of any of the already mapped 
          VNFs, which are present in the anti-affinity list, then 
          returns true, false otherwise.
    Saves the bt_record if we are at the temporary host of the other end of 
    the anti-affinity for delegating .
    """
    vnf = self.req.node[vnf_id]
    infra = self.net.node[node_id]
    if len(vnf.constraints.antiaffinity.values()) > 0:
      anti_aff_ruined = False
      setattr(vnf, 'anti_aff_metadata', {})
      for anti_aff_pair in vnf.constraints.antiaffinity.values():
        vnf.anti_aff_metadata[anti_aff_pair] = 0
      for anti_aff_pair in vnf.constraints.antiaffinity.values():
        host_of_aff_pair = self.manager.getIdOfChainEnd_fromNetwork(
          anti_aff_pair)
        if host_of_aff_pair != -1:
          vnf.anti_aff_metadata[anti_aff_pair] += 1
          if host_of_aff_pair == node_id:
            anti_aff_ruined = True
            if self.net.node[
              host_of_aff_pair].infra_type == infra.TYPE_BISBIS and \
               self.net.node[host_of_aff_pair].mapping_features.get(
                  'antiaffinity', False):
              # it there are multiple Infras, where this can be delegated, the 
              # last visited is chosen. It could be done more sophisticatedly, 
              # now it is just a random selection among the feasible ones.
              self.log.debug("Setting anti-affinity delegation data with "
                             "backtracking record: %s" % bt_record)
              setattr(vnf, 'anti_aff_delegation_data', bt_record)
      if anti_aff_ruined:
        return False
      else:
        return True
    else:
      return True

  def _resolveAntiAffinityDelegationIfPossible (self, cid, vnf_id):
    """
    Checks whether the mapping procedure failed because of Anti-affinity 
    criteria on the VNF which was tried to map the most recently. Saves the
    anti-affinity criteria for delegating to the hosting BiSBiS of the other 
    end of anti-affinity.
    Returns a boolean whether the anti-affinity could be delegated or not.
    Should be called after catching a MappingException which cannot be
    backtracked
    """
    vnf = self.req.node[vnf_id]
    if hasattr(vnf, 'anti_aff_delegation_data'):
      # anti_aff_delegation_data is a 'bt_record' type object
      self._takeOneGreedyStep(cid, vnf.anti_aff_delegation_data)
      self.log.debug("Delegating anti-affinity requirement of %s: %s to lower "
                     "layer on BiSBiS %s" % (
                       vnf.id, vnf.constraints.antiaffinity,
                       vnf.anti_aff_delegation_data['target_infra']))
      if not hasattr(self, 'delegated_anti_aff_crit'):
        setattr(self, 'delegated_anti_aff_crit',
                {vnf_id: vnf.constraints.antiaffinity})
      else:
        self.delegated_anti_aff_crit[vnf_id] = \
          copy.deepcopy(vnf.constraints.antiaffinity.values())
      # this anti-affinity is resolved for the current mapping process 
      # permanently (this cannot even be backstepped, because we have run out 
      # of backsteps earlier)
      for aa_id, anti_aff_pair in vnf.constraints.antiaffinity.items():
        antiaff_pair_dict = self.req.node[
          anti_aff_pair].constraints.antiaffinity
        self.req.node[anti_aff_pair].constraints.antiaffinity = {k: v for k, v
                                                                 in \
                                                                 antiaff_pair_dict.items()
                                                                 if v != vnf_id}
      vnf.constraints.antiaffinity = {}
      return True
    else:
      return False

  def _objectiveFunction (self, cid, node_id, prev_vnf_id, vnf_id, reqlinkid,
                          path_to_map, linkids, sum_latency):
    """
    Calculates a function to determine which node is better to map to,
    returns -1, if not feasible
    """
    requested = self.req.node[vnf_id].resources
    available = self.net.node[node_id].availres
    maxres = self.net.node[node_id].resources
    bw_req = self.req[prev_vnf_id][vnf_id][reqlinkid].bandwidth
    sum_res = 0

    if len(path_to_map) == 0:
      raise uet.InternalAlgorithmException(
        "No path given to host %s for preference value calculation!" % node_id)

    if available['mem'] >= requested['mem'] and available['cpu'] >= requested[
      'cpu'] and available['storage'] >= requested['storage']:
      avg_link_util = self._calculateAvgLinkUtil(path_to_map, linkids, bw_req,
                                                 vnf_id)
      if avg_link_util == -1:
        self.log.debug("Host %s is not a good candidate for hosting %s due to "
                       "bandwidth requirement." % (node_id, vnf_id))
        return -1
      local_latreq = self.manager.getLocalAllowedLatency(cid, prev_vnf_id,
                                                         vnf_id, reqlinkid)
      if sum_latency == -1 or sum_latency > local_latreq or not \
         self.manager.isVNFMappingDistanceGood( \
            prev_vnf_id, vnf_id, path_to_map[0], path_to_map[-1]) or \
            local_latreq == 0 or not \
         self.manager.areChainEndsReachableInLatency( \
            sum_latency, node_id, cid):
        self.log.debug(
          "Host %s is too far measured in latency for hosting %s." %
          (node_id, vnf_id))
        return -1

      # Here we know that node_id have enough resource and the path
      # leading there satisfies the bandwidth req of the potentially
      # mapped edge of req graph. And the latency requirements as well

      max_rescomponent_value = 0
      for attr, res_w in zip(['cpu', 'mem', 'storage'],
                             self.resource_priorities):
        if maxres[attr] == float("inf"):
          sum_res += self.pref_funcs[attr](0.0)
        else:
          sum_res += res_w * self.pref_funcs[attr](
            float(maxres[attr] - (available[attr] - requested[attr])) / maxres[
              attr])
        max_rescomponent_value += self.pref_funcs[attr](1.0) * res_w

      # Scale them to the same interval
      scaled_res_comp = 10 * float(sum_res) / max_rescomponent_value
      scaled_bw_comp = 10 * float(
        self.pref_funcs['bandwidth'](avg_link_util)) / \
                       self.pref_funcs['bandwidth'](1.0)
      # Except latency component, because it is added outside of the objective 
      # function
      # scaled_lat_comp = 10 * float(sum_latency) / local_latreq

      self.log.debug("avglinkutil pref value: %f, sum res: %f" % (
        self.bw_factor * scaled_bw_comp, self.res_factor * scaled_res_comp))

      value = self.bw_factor * scaled_bw_comp + self.res_factor * \
                                                scaled_res_comp

      return value
    else:
      self.log.debug(
        "Host %s does not have engough node resource for hosting %s." %
        (node_id, vnf_id))
      return -1

  def _updateGraphResources (self, bw_req, path, linkids, vnf=None, node=None,
                             redo=False):
    """Subtracts the required resources by the (vnf, node) mapping
    and path with bw_req from the available resources of the
    substrate network. vnf and node variables should be given, if those are
    just mapped now. (not when we want to map only a path between two already
    mapped VNFs)
    redo=True means we are doing a backstep in the mapping and we want to redo 
    the resource reservations.
    TODO: use redo parameter!! and checking not to exceed max!!
    NOTE1: the ending of `path` is `node`.
    NOTE2: feasibility is already checked by _objectiveFunction()"""

    if vnf is not None and node is not None:
      if self.net.node[node].type != 'INFRA':
        raise uet.InternalAlgorithmException(
          "updateGraphResources should only be called on Infra nodes!")
      if redo:
        res_to_substractoradd = copy.deepcopy(self.req.node[vnf].resources)
        for attr in ['cpu', 'mem', 'storage', 'bandwidth']:
          # delay is not subtracted!!
          if res_to_substractoradd[attr] is not None:
            res_to_substractoradd[attr] = -1 * res_to_substractoradd[attr]
      else:
        res_to_substractoradd = self.req.node[vnf].resources
      newres = self.net.node[node].availres.subtractNodeRes(
        res_to_substractoradd,
        self.net.node[node].resources)
      self.net.node[node].availres = newres

    if redo:
      bw_req = -1 * bw_req

    if len(path) == 0:
      self.log.warn("Updating resources with 0 length path!")
    elif len(path) > 0:
      # collocation or 1st element of path needs to be updated.
      if self.net.node[path[0]].type != 'SAP':
        self.net.node[path[0]].availres['bandwidth'] -= bw_req
        new_bw = self.net.node[path[0]].availres['bandwidth']
        if new_bw < 0 or new_bw > self.net.node[path[0]].resources['bandwidth']:
          self.log.error("Node bandwidth is incorrect with value %s!" % new_bw)
          raise uet.InternalAlgorithmException("An internal bandwidth value got"
                                               " below zero or exceeded "
                                               "maximal value!")
        elif new_bw == 0:
          self.net.node[
            path[0]].weight = float("inf")
        else:
          self.net.node[path[0]].weight = 1.0 / new_bw
      if len(path) > 1:
        for i, j, k in zip(path[:-1], path[1:], linkids):
          self.net[i][j][k].availbandwidth -= bw_req
          new_bw = self.net[i][j][k].availbandwidth
          if new_bw < 0 or new_bw * 0.999 > self.net[i][j][k].bandwidth:
            self.log.error(
              "Link bandwidth is incorrect with value %s!" % new_bw)
            raise uet.InternalAlgorithmException("The bandwidth resource of "
                                                 "link %s got below zero, "
                                                 "or exceeded maximal value!"
                                                 % k)
          elif new_bw == 0:
            self.net[i][j][k].weight = float("inf")
          else:
            self.net[i][j][k].weight = 1.0 / new_bw
          # update node bandwidth resources on the path
          if self.net.node[j].type != 'SAP':
            self.net.node[j].availres['bandwidth'] -= bw_req
            new_bw_innode = self.net.node[j].availres['bandwidth']
            if new_bw_innode < 0 or new_bw_innode > \
               self.net.node[j].resources['bandwidth']:
              self.log.error("Node bandwidth is incorrect with value %s!" %
                             new_bw_innode)
              raise uet.InternalAlgorithmException("The bandwidth resource"
                                                   " of node %s got below "
                                                   "zero, or exceeded the "
                                                   "maximal value!" % j)
            elif new_bw_innode == 0:
              self.net.node[j].weight = float("inf")
            else:
              self.net.node[j].weight = 1.0 / new_bw_innode
    self.log.debug("Available network resources are updated: redo: %s, vnf: "
                   "%s, path: %s" % (redo, vnf, path))

  def _takeOneGreedyStep (self, cid, step_data):
    """
    Calls all required functions to take a greedy step, mapping the actual 
    VNF and link to the selected host and path.
    Feasibility should be already tested for every case.
    And adds the step_data back to the current backtrack level, so it could be 
    undone just like in other cases.
    """
    self.log.debug(
      "Mapped VNF %s to node %s in network. Updating data accordingly..." %
      (step_data['vnf_id'], step_data['target_infra']))
    self.manager.vnf_mapping.append((step_data['vnf_id'],
                                     step_data['target_infra']))
    # maintain peak VNF count during the backtracking
    if len(self.manager.vnf_mapping) - self.sap_count > \
       self.peak_mapped_vnf_count:
      self.peak_mapped_vnf_count = len(
        self.manager.vnf_mapping) - self.sap_count
    self.log.debug("Request Link %s, %s, %s mapped to path: %s" % (
      step_data['prev_vnf_id'], step_data['vnf_id'], step_data['reqlinkid'],
      step_data['path']))
    self.manager.link_mapping.add_edge(step_data['prev_vnf_id'],
                                       step_data['vnf_id'],
                                       key=step_data['reqlinkid'],
                                       mapped_to=step_data['path'],
                                       path_link_ids=step_data['path_link_ids'])
    self._updateGraphResources(step_data['bw_req'],
                               step_data['path'], step_data['path_link_ids'],
                               step_data['vnf_id'],
                               step_data['target_infra'])
    self.manager.updateChainLatencyInfo(cid, step_data['used_latency'],
                                        step_data['target_infra'])
    self.bt_handler.addFreshlyMappedBacktrackRecord(step_data, None)

  def _mapOneVNF (self, cid, subgraph, start, prev_vnf_id, vnf_id, reqlinkid,
                  bt_record=None):
    """
    Starting from the node (start), where the previous vnf of the chain
    was mapped, maps vnf_id to an appropriate node.
    is_it_forward_step indicates if we have to check for all possible mappings 
    and save it to the backtrack structure, or we have received a backtrack 
    record due to a backstep.
    """
    best_node_que = deque(maxlen=self.bt_branching_factor)
    deque_length = 0
    base_bt_record = {'prev_vnf_id': prev_vnf_id, 'vnf_id': vnf_id,
                      'reqlinkid': reqlinkid, 'last_used_node': start,
                      'bw_req': self.req[prev_vnf_id][vnf_id] \
                        [reqlinkid].bandwidth}
    # Edge data must be used from the substrate network!
    # NOTE(loops): shortest path from i to i is [i] (This path is the
    # collocation, and 1 long paths are handled right by the
    # _objectiveFunction()/_calculateAvgLinkUtil()/_sumLat() functions)
    paths, linkids = helper.shortestPathsBasedOnEdgeWeight(subgraph, start)
    # TODO: sort 'paths' in ordered dict according to new latency pref value.
    # allow only infras which has some 'supported'
    self.log.debug("Potential hosts #1 (unfiltered) for  VNF %s: %s"
                   % (vnf_id, paths.keys()))
    potential_hosts = filter(lambda h, nodes=self.net.node:
                             nodes[h].type == 'INFRA' and nodes[
                                                            h].supported is
                                                          not None,
                             paths.keys())
    # allow only hosts which supports this NF
    self.log.debug("Potential hosts #2 (non-Infras and nodes without "
                   "supported NFs are filtered) for  VNF %s: %s"
                   % (vnf_id, potential_hosts))
    potential_hosts = filter(lambda h, v=vnf_id, nodes=self.net.node,
                                    vnfs=self.req.node: vnfs[
                                                          v].functional_type in
                                                        nodes[h].supported,
                             potential_hosts)
    self.log.debug("Potential hosts #3 (not supporting this NF type are "
                   "filtered) for  VNF %s: %s" % (vnf_id, potential_hosts))
    # TODO: is it still spoils something??
    # allow only hosts which complies to plac_crit if any
    # potential_hosts = filter(lambda h, v=vnf_id, vnfs=self.req.node:
    #   len(vnfs[v].placement_criteria)==0 or h in vnfs[v].placement_criteria, 
    #                          potential_hosts)
    # self.log.debug("Potential hosts #4 (filtering due to placement criteria)"
    #                " for  VNF %s: %s"%(vnf_id, potential_hosts))
    potential_hosts_sumlat = []
    for host in potential_hosts:
      potential_hosts_sumlat.append((host, self._sumLatencyOnPath(paths[host],
                                                                  linkids[
                                                                    host])))
    hosts_with_lat_prefvalues = self.manager.calcDelayPrefValues( \
      potential_hosts_sumlat, prev_vnf_id, vnf_id,
      reqlinkid, cid, subgraph, start)
    self.log.debug("Hosts with lat pref values from VNF %s: \n %s" % (vnf_id,
                                                                      hosts_with_lat_prefvalues))
    for map_target, sumlat, latprefval in hosts_with_lat_prefvalues:
      value = self._objectiveFunction(cid, map_target,
                                      prev_vnf_id, vnf_id,
                                      reqlinkid,
                                      paths[map_target],
                                      linkids[map_target],
                                      sumlat)
      self.log.debug("Objective function value for VNF %s - Host %s "
                     "mapping: %s" % (vnf_id, map_target, value))
      if value > -1:
        self.log.debug("Calculated latency preference value: %f for VNF %s and "
                       "path: %s" % (latprefval, vnf_id, paths[map_target]))
        value += 10.0 * latprefval
        self.log.debug("Calculated value: %f for VNF %s and path: %s" % (
          value, vnf_id, paths[map_target]))
        just_found = copy.deepcopy(base_bt_record)
        just_found.update(zip(('target_infra', 'path', 'path_link_ids',
                               'used_latency', 'obj_func_value'),
                              (map_target, paths[map_target],
                               linkids[map_target], sumlat, value)))

        # returns true if the anti-affinity criteria is ruined.
        if not self._checkAntiAffinityCriteria(map_target, vnf_id, just_found):
          self.log.debug("Skipping possible host %s due to anti-affinity "
                         "criteria for VNF %s" % (map_target, vnf_id))
          continue

        if deque_length == 0:
          best_node_que.append(just_found)
          deque_length += 1
        else:
          best_node_sofar = best_node_que.pop()
          best_node_que.append(best_node_sofar)
          if best_node_sofar['obj_func_value'] > value:
            best_node_que.append(just_found)
          elif deque_length <= self.bt_branching_factor > 1:
            least_good_que = deque()
            least_good_sofar = best_node_que.popleft()
            deque_length -= 1
            while least_good_sofar['obj_func_value'] > value:
              least_good_que.append(least_good_sofar)
              # too many good nodes can be remove, because we already 
              # know just found is worse than the best node
              least_good_sofar = best_node_que.popleft()
              deque_length -= 1
            best_node_que.appendleft(least_good_sofar)
            best_node_que.appendleft(just_found)
            deque_length += 2
            while deque_length < self.bt_branching_factor:
              try:
                best_node_que.appendleft(least_good_que.popleft())
              except IndexError:
                break
      else:
        self.log.debug("Host %s is not a good candidate for hosting %s."
                       % (map_target, vnf_id))
        pass
    try:
      best_node_sofar = best_node_que.pop()
      self.bt_handler.addBacktrackLevel(cid, best_node_que)
      # we don't have to deal with the deque length anymore, because it is 
      # handled by the bactrack structure.
    except IndexError:
      self.log.info("Couldn`t map VNF %s anywhere, trying backtrack..." %
                    vnf_id)
      raise uet.MappingException("Couldn`t map VNF %s anywhere trying"
                                 "backtrack..." % vnf_id,
                                 backtrack_possible=True)
    self._takeOneGreedyStep(cid, best_node_sofar)

  def _mapOneRequestLink (self, cid, g, vnf1, vnf2, reqlinkid):
    """
    Maps a request link, when both ends are already mapped.
    Uses the weighted shortest path.
    TODO: Replace dijkstra with something more sophisticated.
    """
    n1 = self.manager.getIdOfChainEnd_fromNetwork(vnf1)
    n2 = self.manager.getIdOfChainEnd_fromNetwork(vnf2)
    if n1 == -1 or n2 == -1:
      self.log.error("Not both end of request link are mapped: %s, %s, %s" % (
        vnf1, vnf2, reqlinkid))
      raise uet.InternalAlgorithmException(
        "Not both end of request link are mapped: %s, %s" % (vnf1, vnf2))
    bw_req = self.req[vnf1][vnf2][reqlinkid].bandwidth

    try:
      path, linkids = helper.shortestPathsBasedOnEdgeWeight(g, n1, target=n2)
      path = path[n2]
      linkids = linkids[n2]
    except (nx.NetworkXNoPath, KeyError) as e:
      raise uet.MappingException(
        "No path found between substrate nodes: %s and %s for mapping a "
        "request link between %s and %s" % (n1, n2, vnf1, vnf2),
        backtrack_possible=True)

    used_lat = self._sumLatencyOnPath(path, linkids)

    if self._calculateAvgLinkUtil(path, linkids, bw_req) == -1:
      self.log.info(
        "Last link of chain or best-effort link %s, %s couldn`t be mapped!" % (
          vnf1, vnf2))
      raise uet.MappingException(
        "Last link of chain or best-effort link %s, %s, %s couldn`t be mapped "
        "due to link capacity" % (vnf1, vnf2, reqlinkid),
        backtrack_possible=True)
    elif self.manager.getLocalAllowedLatency(cid, vnf1, vnf2, reqlinkid) < \
       used_lat:
      raise uet.MappingException(
        "Last link %s, %s, %s of chain couldn`t be mapped due to latency "
        "requirement." % (vnf1, vnf2, reqlinkid),
        backtrack_possible=True)
    self.log.debug(
      "Last link of chain or best-effort link %s, %s was mapped to path: %s" % (
        vnf1, vnf2, path))
    self._updateGraphResources(bw_req, path, linkids)
    self.manager.updateChainLatencyInfo(cid, used_lat, n2)
    link_mapping_rec = {'bw_req': bw_req, 'path': path,
                        'linkids': linkids, 'used_lat': used_lat,
                        'vnf1': vnf1, 'vnf2': vnf2,
                        'reqlinkid': reqlinkid}
    self.bt_handler.addFreshlyMappedBacktrackRecord(None, link_mapping_rec)
    self.manager.link_mapping.add_edge(vnf1, vnf2, key=reqlinkid,
                                       mapped_to=path, path_link_ids=linkids)

  def _resolveLinkMappingRecord (self, c, link_bt_record):
    """
    Undo link reservation.
    """
    self.log.debug("Redoing link resources due to LinkMappingRecord handling.")
    self._updateGraphResources(link_bt_record['bw_req'],
                               link_bt_record['path'],
                               link_bt_record['linkids'],
                               redo=True)
    self.manager.updateChainLatencyInfo(c['id'],
                                        -1 * link_bt_record['used_lat'],
                                        link_bt_record['path'][0])
    try:
      self.manager.link_mapping.remove_edge(link_bt_record['vnf1'],
                                            link_bt_record['vnf2'],
                                            key=link_bt_record['reqlinkid'])
    except nx.NetworkXError as nxe:
      raise uet.InternalAlgorithmException("Tried to remove edge from link "
                                           "mapping structure which is not "
                                           "mapped during LinkMappingRecord "
                                           "resolution!")

  def _resolveBacktrackRecord (self, c, bt_record):
    """
    Undo VNF resource reservetion on host and path leading to it.
    """
    self.log.debug("Redoing link and node resource due to Backtrack record "
                   "handling.")
    self._updateGraphResources(bt_record['bw_req'],
                               bt_record['path'],
                               bt_record['path_link_ids'],
                               bt_record['vnf_id'],
                               bt_record['target_infra'],
                               redo=True)
    try:
      self.manager.link_mapping.remove_edge(bt_record['prev_vnf_id'],
                                            bt_record['vnf_id'],
                                            key=bt_record['reqlinkid'])
    except nx.NetworkXError as nxe:
      raise uet.InternalAlgorithmException("Tried to remove edge from link "
                                           "mapping structure which is not "
                                           "mapped during Backtrack Record "
                                           "resolution!")
    if self.req.node[bt_record['vnf_id']].type != 'SAP':
      self.manager.vnf_mapping.remove((bt_record['vnf_id'],
                                       bt_record['target_infra']))
    self.manager.updateChainLatencyInfo(c['id'],
                                        -1 * bt_record['used_latency'],
                                        bt_record['last_used_node'])

  def _addFlowrulesToNFFGDerivatedFromReqLinks (self, v1, v2, reqlid, nffg):
    """
    Adds the flow rules of the path of the request link (v1,v2,reqlid)
    to the ports of the Infras.
    The required Port objects are stored in 'infra_ports' field of
    manager.link_mapping edges. Flowrules must be installed to the 'nffg's
    Ports, NOT self.net!! (Port id-s can be taken from self.net as well)
    Flowrule format is:
      match: in_port=<<Infraport id>>;flowclass=<<Flowclass of SGLink if
                     there is one>>;TAG=<<Neighboring VNF ids and linkid>>
      action: output=<<outbound port id>>;TAG=<<Neighboring VNF ids and
      linkid>>/UNTAG
    WARNING: If multiple SGHops starting from a SAP are mapped to paths whose 
    first infrastructure link is common, starting from the same SAP, the first
    Infra node can only identify which packet belongs to which SGHop based on 
    the FLOWCLASS field, which is considered optional.

    Flowrule ID-s are always reqlid, ID collision cannot happen, because these
    ID-s are unique in an Infra (loops cannot occur in SGHop's path).
    """
    helperlink = self.manager.link_mapping[v1][v2][reqlid]
    path = helperlink['mapped_to']
    linkids = helperlink['path_link_ids']
    if 'infra_ports' in helperlink:
      flowsrc = helperlink['infra_ports'][0]
      flowdst = helperlink['infra_ports'][1]
    else:
      flowsrc = None
      flowdst = None
    reqlink = self.req[v1][v2][reqlid]
    bw = reqlink.bandwidth
    delay = reqlink.delay
    # Let's use the substrate SAPs' ID-s for TAG definition.
    if self.req.node[v1].type == 'SAP':
      v1 = self.manager.getIdOfChainEnd_fromNetwork(v1)
    if self.req.node[v2].type == 'SAP':
      v2 = self.manager.getIdOfChainEnd_fromNetwork(v2)
    # The action and match are the same format
    tag = "TAG=%s|%s|%s" % (v1, v2, reqlid)
    if len(path) == 1:
      # collocation happened, none of helperlink`s port refs should be None
      match_str = "in_port="
      action_str = "output="
      if flowdst is None or flowsrc is None:
        raise uet.InternalAlgorithmException(
          "No InfraPort found for a dynamic link of collocated VNFs")
      match_str += str(flowsrc.id)
      if reqlink.flowclass is not None:
        match_str += ";flowclass=%s" % reqlink.flowclass
      action_str += str(flowdst.id)
      self.log.debug("Collocated flowrule %s => %s added to Port %s of %s" % (
        match_str, action_str, flowsrc.id, path[0]))
      flowsrc.add_flowrule(match_str, action_str, bandwidth=bw, delay=delay,
                           id=reqlid)
    else:
      # set the flowrules for the transit Infra nodes
      for i, j, k, lidij, lidjk in zip(path[:-2], path[1:-1], path[2:],
                                       linkids[:-1], linkids[1:]):
        match_str = "in_port="
        action_str = "output="
        match_str += str(self.net[i][j][lidij].dst.id)
        if reqlink.flowclass is not None:
          match_str += ";flowclass=%s" % reqlink.flowclass
        action_str += str(self.net[j][k][lidjk].src.id)
        if not (
                 self.net.node[i].type == 'SAP' and self.net.node[k].type ==
               'SAP' \
              and len(path) == 3):
          # if traffic is just going through, we dont have to TAG at all.
          # Transit SAPs would mess it up pretty much, but it is not allowed.
          if self.net.node[i].type == 'SAP' and self.net.node[k].type != 'SAP':
            action_str += ";" + tag
          else:
            match_str += ";" + tag
        self.log.debug("Transit flowrule %s => %s added to Port %s of %s" % (
          match_str, action_str, self.net[i][j][lidij].dst.id, j))
        nffg.network[i][j][lidij].dst.add_flowrule(match_str, action_str,
                                                   bandwidth=bw, delay=delay,
                                                   id=reqlid)

      # set flowrule for the first element if that is not a SAP
      if nffg.network.node[path[0]].type != 'SAP':
        match_str = "in_port="
        action_str = "output="
        if flowsrc is None:
          raise uet.InternalAlgorithmException(
            "No InfraPort found for a dynamic link which starts a path")
        match_str += str(flowsrc.id)
        if reqlink.flowclass is not None:
          match_str += ";flowclass=%s" % reqlink.flowclass
        action_str += str(nffg.network[path[0]][path[1]][linkids[0]].src.id)
        action_str += ";" + tag
        self.log.debug("Starting flowrule %s => %s added to Port %s of %s" % (
          match_str, action_str, flowsrc.id, path[0]))
        flowsrc.add_flowrule(match_str, action_str, bandwidth=bw, delay=delay,
                             id=reqlid)

      # set flowrule for the last element if that is not a SAP
      if nffg.network.node[path[-1]].type != 'SAP':
        match_str = "in_port="
        action_str = "output="
        match_str += str(self.net[path[-2]][path[-1]][linkids[-1]].dst.id)
        if reqlink.flowclass is not None:
          match_str += ";flowclass=%s" % reqlink.flowclass
        match_str += ";" + tag
        if flowdst is None:
          raise uet.InternalAlgorithmException(
            "No InfraPort found for a dynamic link which finishes a path")
        action_str += str(flowdst.id) + ";UNTAG"
        self.log.debug("Finishing flowrule %s => %s added to Port %s of %s" % (
          match_str, action_str,
          self.net[path[-2]][path[-1]][linkids[-1]].dst.id, path[-1]))
        nffg.network[path[-2]][path[-1]][linkids[-1]].dst.add_flowrule(
          match_str, action_str, bandwidth=bw, delay=delay, id=reqlid)

  def _retrieveOrAddVNF (self, nffg, vnfid):
    # add the VNF from the request graph to update the resource requirements 
    # and instance! The new requirements are checked for VNFs which are left 
    # in place!
    if vnfid in nffg.network:
      nodenf_res = copy.deepcopy(self.req.node[vnfid].resources)
      nffg.network.node[vnfid].resources = nodenf_res
      nffg.network.node[vnfid].name = self.req.node[vnfid].name
      # Status is also updated in every case, it must be forwarded to lower
      # layer
      nffg.network.node[vnfid].status = self.req.node[vnfid].status
      nodenf = nffg.network.node[vnfid]
      self.log.debug("Retrieving VNF %s from output resource for output "
                    "generation"%vnfid)
    else:
      nodenf = copy.deepcopy(self.req.node[vnfid])
      nffg.add_node(nodenf)
      self.log.debug("Copying VNF %s from request to output resource"%vnfid)

    return nodenf

  '''
  # This was needed for adding output SGHops, maybe needed for their generation 
  # based on flowrule data.
  def _addSAPportIfNeeded(self, nffg, sapid, portid):
    """
    The request and substrate SAPs are different objects, the substrate does not
    neccessarily have the same ports which were used by the service graph.
    """
    if portid in [p.id for p in nffg.network.node[sapid].ports]:
      return portid
    else:
      return nffg.network.node[sapid].add_port(portid).id
  '''

  def _getSrcDstPortsOfOutputEdgeReq (self, nffg, sghop_id, infra, src=True,
                                      dst=True):
    """
    Retrieve the ending and starting infra port, where EdgeReq 
    should be connected. Raises exception if either of them is not found.
    If one of the ports is not requested, it remains None.
    NOTE: we can be sure there is only one flowrule with 'sghop_id' in this
    infra
    because we map SGHops based on shortest path algorithm and it would cut 
    loops from the shortest path (because there are only positive edge weights)
    """
    start_port_for_req = None
    end_port_for_req = None
    found = False
    for p in nffg.network.node[infra].ports:
      for fr in p.flowrules:
        if fr.id == sghop_id:
          if src:
            start_port_for_req = p
            if not dst:
              found = True
              break
          if dst:
            for action in fr.action.split(";"):
              comm_param = action.split("=")
              if comm_param[0] == "output":
                end_port_id = comm_param[1]
                try:
                  end_port_id = int(comm_param[1])
                except ValueError:
                  pass
                end_port_for_req = nffg.network.node[infra].ports[end_port_id]
                found = True
                break
        if found:
          break
      if found:
        break
    else:
      raise uet.InternalAlgorithmException("One of the ports was not "
                                           "found for output EdgeReq!")
    return start_port_for_req, end_port_for_req

  def _addEdgeReqToChainPieceStruct (self, e2e_chainpieces, cid, outedgereq):
    """
    Handles the structure for output EdgeReqs. Logs, helps avoiding code 
    duplication.
    """
    if cid in e2e_chainpieces:
      e2e_chainpieces[cid].append(outedgereq)
    else:
      e2e_chainpieces[cid] = [outedgereq]
    self.log.debug("Requirement chain added to BiSBiS %s with path %s and"
                   " latency %s." % (outedgereq.src.node.id, outedgereq.sg_path,
                                     outedgereq.delay))

  def _divideEndToEndRequirements (self, nffg):
    """
    Splits the E2E latency requirement between all BiSBiS nodes, which were used
    during the mapping procedure. Draws EdgeReqs into the output NFFG, saves the
    SGHop path where it should be satisfied, divides the E2E latency weighted by
    the offered latency of the affected BiSBiS-es.
    """
    # remove if there are any EdgeReqs in the graph
    for req in [r for r in nffg.reqs]:
      nffg.del_edge(req.src, req.dst, req.id)
    e2e_chainpieces = {}
    last_sghop_id = None
    last_sghop_obj = None
    last_cid = None
    for cid, first_vnf, infra in self.manager.genPathOfChains(nffg):
      if last_cid != cid:
        last_cid = cid
        for chain in self.manager.chains:
          if chain['id'] == cid:
            last_sghop_id = chain['link_ids'][0]
            self.log.debug("Starting E2E requirement division on chain %s with "
                           "path %s" % (cid, chain['link_ids']))
            break
      for i, j, k, d in self.req.edges_iter(data=True, keys=True):
        if last_sghop_id == k:
          last_sghop_obj = d
          break
      if nffg.network.node[infra].type == 'INFRA':
        mapped_req = self.req.subgraph((vnf.id for vnf in \
                                        nffg.running_nfs(infra)))
        if nffg.network.node[infra].infra_type == NFFG.TYPE_INFRA_BISBIS:
          outedgereq = None
          delay_of_infra = self._sumLatencyOnPath([infra], [])
          if len(mapped_req) == 0 or \
             self.manager.isItTransitInfraNow(infra, last_sghop_obj) or \
                first_vnf is None:
            # we know that 'cid' traverses 'infra', but if this chain has no 
            # mapped node here, then it olny uses this infra in its path
            # OR              
            # This can happen when this BiSBiS is only forwarding the traffic 
            # of this service chain, BUT only VNFs from another service chains 
            # has been mapped here
            # OR 
            # there is some VNF of 'cid' mapped here, but now we traverse this
            # infra as transit
            sghop_id = self.manager.getSGHopOfChainMappedHere(cid, infra,
                                                              last_sghop_id)
            src, dst = self._getSrcDstPortsOfOutputEdgeReq(nffg,
                                                           sghop_id, infra)
            # this is as much latency as we used for the mapping
            # 0 bandwith should be forwarded, because they are already taken
            # into
            # account in SGHop bandwith
            outedgereq = nffg.add_req(src, dst, delay=delay_of_infra,
                                      bandwidth=0,
                                      id=self.manager.getNextOutputChainId(),
                                      sg_path=[sghop_id])
            self._addEdgeReqToChainPieceStruct(e2e_chainpieces, cid, outedgereq)
          else:
            chain_piece, link_ids_piece = self.manager. \
              getNextChainPieceOfReqSubgraph(cid,
                                             mapped_req, last_sghop_id)
            src, _ = self._getSrcDstPortsOfOutputEdgeReq(nffg,
                                                         link_ids_piece[0],
                                                         infra, dst=False)
            _, dst = self._getSrcDstPortsOfOutputEdgeReq(nffg,
                                                         link_ids_piece[-1],
                                                         infra, src=False)
            # a chain part spends one time of delay_of_infra for every link 
            # mapped here, becuase it is valid between all the port pairs only.
            outedgereq = nffg.add_req(src, dst,
                                      delay=len(
                                        link_ids_piece) * delay_of_infra,
                                      bandwidth=0,
                                      id=self.manager.getNextOutputChainId(),
                                      sg_path=link_ids_piece)
            self._addEdgeReqToChainPieceStruct(e2e_chainpieces, cid,
                                               outedgereq)
          last_sghop_id = outedgereq.sg_path[-1]
        elif len(mapped_req) > 0 and not \
           self.manager.isItTransitInfraNow(infra, last_sghop_obj):
          # in this case a non-BiSBiS infra hosts a VNF, so the last_sghop_id
          # needs to be updated!
          chain_piece, link_ids_piece = self.manager. \
            getNextChainPieceOfReqSubgraph(cid,
                                           mapped_req, last_sghop_id)
          last_sghop_id = link_ids_piece[-1]
          self.log.debug("Stepping on non-BiSBiS infra node %s hosting chain "
                         "part %s and finishing in SGHop %s." %
                         (infra, chain_piece, last_sghop_id))

    # now iterate on the chain pieces
    for cid in e2e_chainpieces:
      # this is NOT equal to permitted minus remaining!
      sum_of_latency_pieces = sum((er.delay for er in e2e_chainpieces[cid]))
      # divide the remaining E2E latency equally among the e2e pieces
      # and add this to the propagated latency as extra.
      for er in e2e_chainpieces[cid]:
        er.delay += 1.0 / len(e2e_chainpieces[cid]) * \
                    self.manager.getRemainingE2ELatency(cid)
        self.log.debug("Output latency requirement increased to %s in %s for "
                       "path %s" % (er.delay, er.src.node.id, er.sg_path))

  def _addAntiAffinityDelegationToOutput (self, nffg):
    """
    Checks whether the Anti-affinity constraints are satisfied by the current 
    mapping, raises exception if not, indicating an impelemtation error. The 
    satisfied constraints are deleted.
    Retrieves the saved anti-affinity data for delegation purposes.
    """
    for nf in nffg.nfs:
      hosting_infra1 = next(nffg.infra_neighbors(nf.id))
      for anti_aff_pair in nf.constraints.antiaffinity.values():
        hosting_infra2 = next(nffg.infra_neighbors(anti_aff_pair))
        if hosting_infra1.id == hosting_infra2.id:
          raise uet.InternalAlgorithmException("Anti-affinity between NFs %s "
                                               "and %s is not satisfied by "
                                               "the given mapping! "
                                               "NotYetImplemented:"
                                               " correcting anti-affinity "
                                               "pairings for bidirectionality "
                                               "if they"
                                               " are only partially given." % (
                                                 nf.id, anti_aff_pair))
        else:
          # delete anti-affinity, in lower layers it would be invalid or 
          # already satisfied by this mapping.
          nf.constraints.antiaffinity = {}
    if hasattr(self, 'delegated_anti_aff_crit'):
      for vnf in self.delegated_anti_aff_crit:
        nf_obj = nffg.network.node[vnf]
        hosting_infra1 = next(nffg.infra_neighbors(vnf))
        for aff_id, anti_aff_pair in self.delegated_anti_aff_crit[
          vnf].iteritems():
          if anti_aff_pair in [n.id for n in
                               nffg.running_nfs(hosting_infra1.id)]:
            hosting_infra2 = next(nffg.infra_neighbors(anti_aff_pair))
            anti_aff_pair_obj = nffg.network.node[anti_aff_pair]
            if hosting_infra2.id != hosting_infra1.id:
              raise uet.InternalAlgorithmException("Delegation of anti-affinity"
                                                   " criterion between NFs %s "
                                                   "and %s is unsuccessful "
                                                   "due to "
                                                   "different hosting "
                                                   "infras." % (
                                                     vnf, anti_aff_pair))
            self.log.debug("Adding delegated (bidirectional) anti-affinity "
                           "criterion for BiSBiS node %s" % hosting_infra1.id)
            nf_obj.constraints.add_antiaffinity(aff_id, anti_aff_pair)
            anti_aff_pair_obj.constraints.add_antiaffinity(aff_id, vnf)

  def constructOutputNFFG (self):
    # use the unchanged input from the lower layer (deepcopied in the
    # constructor, modify it now)
    if self.mode == NFFG.MODE_REMAP:
      # use the already preprocessed network we don't need to append the VNF
      # mappings to the existing VNF mappings
      nffg = self.bare_infrastucture_nffg
    elif self.mode == NFFG.MODE_ADD:
      # the just mapped request should be appended to the one sent by the 
      # lower layer indicating the already mapped VNF-s.
      nffg = self.net0
    else:
      raise uet.InternalAlgorithmException("Invalid mapping operation mode "
                                           "shouldn't reach here!")

    self.log.debug("Constructing output NFFG...")

    for vnf, host in self.manager.vnf_mapping:

      # Save data of SAP port from SG to output NFFG.
      if self.req.node[vnf].type == 'SAP':
        if len(self.req.node[vnf].ports) > 1:
          self.log.warn(
            "SAP object %s has more than one Port in its container!" %
            self.req.node[vnf].id)
        for pn in self.req.node[vnf].ports:
          if pn.sap is not None and pn.role is not None:
            if len(nffg.network.node[host].ports) > 1:
              self.log.warn(
                "SAP object %s has more than one Port in its container!" %
                nffg.network.node[host].id)
            for ps in nffg.network.node[host].ports:
              ps.sap = pn.sap
              ps.role = pn.role
              break
          break

      # duplicate the object, so the original one is not modified.
      if self.req.node[vnf].type == 'NF':
        mappednodenf = self._retrieveOrAddVNF(nffg, vnf)

        for i, j, k, d in self.req.out_edges_iter([vnf], data=True, keys=True):
          # i is always vnf
          # Generate only ONE InfraPort for every Port of the NF-s with 
          # predictable port ID. Format: <<InfraID|NFID|NFPortID>>
          infra_port_id = "|".join((str(host), str(vnf), str(d.src.id)))
          # WARNING: PortContainer's "in" operator needs a Port object!!
          # We need to use try catch to test inclusion for port ID
          try:
            out_infra_port = nffg.network.node[host].ports[infra_port_id]
            self.log.debug("Port %s found in Infra %s leading to port %s of NF"
                           " %s." % (infra_port_id, host, d.src.id, vnf))
          except KeyError:
            out_infra_port = nffg.network.node[host].add_port(id=infra_port_id)
            self.log.debug("Port %s added to Infra %s to NF %s."
                           % (out_infra_port.id, host, vnf))
            # this is needed when an already mapped VNF is being reused from an 
            # earlier mapping, and the new SGHop's port only exists in the 
            # current request. WARNING: no function for Port object addition!
            try:
              mappednodenf.ports[d.src.id]
            except KeyError:
              mappednodenf.add_port(id=d.src.id, properties=d.src.properties)
            # use the (copies of the) ports between the SGLinks to
            # connect the VNF to the Infra node.
            # Add the mapping indicator DYNAMIC link only if the port was just
            # added. NOTE: _retrieveOrAddVNF() function already returns the 
            # right (updated in case of ADD operation mode) VNF instance!
            nffg.add_undirected_link(out_infra_port,
                                     mappednodenf.ports[d.src.id],
                                    p1p2id="dynlink1"+infra_port_id,
                                    p2p1id="dynlink2"+infra_port_id,
                                     dynamic=True)
          helperlink = self.manager.link_mapping[i][j][k]
          if 'infra_ports' in helperlink:
            helperlink['infra_ports'][0] = out_infra_port
          else:
            helperlink['infra_ports'] = [out_infra_port, None]

        for i, j, k, d in self.req.in_edges_iter([vnf], data=True, keys=True):
          # j is always vnf
          infra_port_id = "|".join((str(host), str(vnf), str(d.dst.id)))
          try:
            in_infra_port = nffg.network.node[host].ports[infra_port_id]
            self.log.debug("Port %s found in Infra %s leading to port %s of NF"
                           " %s." % (infra_port_id, host, d.dst.id, vnf))
          except KeyError:
            in_infra_port = nffg.network.node[host].add_port(id=infra_port_id)
            self.log.debug("Port %s added to Infra %s to NF %s."
                           % (in_infra_port.id, host, vnf))
            try:
              mappednodenf.ports[d.dst.id]
            except KeyError:
              mappednodenf.add_port(id=d.dst.id, properties=d.dst.properties)
            nffg.add_undirected_link(in_infra_port,
                                     mappednodenf.ports[d.dst.id],
                                     p1p2id="dynlink1" + infra_port_id,
                                     p2p1id="dynlink2" + infra_port_id,
                                     dynamic=True)
          helperlink = self.manager.link_mapping[i][vnf][k]
          if 'infra_ports' in helperlink:
            helperlink['infra_ports'][1] = in_infra_port
          else:
            helperlink['infra_ports'] = [None, in_infra_port]
            # Here a None instead of a port object means that the
            # SGLink`s beginning or ending is a SAP.

    # all VNFs are added to the NFFG, so now, req ids are valid in this
    # NFFG instance. Ports for the SG link ends are reused from the mapped NFFG.
    # SGHops are not added to the output NFFG anymore because they can be 
    # generated by the Flowrule data. (They had been added here latest: commit 
    # 8bdaf26cd3)
    for i, j, d in self.req.edges_iter(data=True):
      # if any Flowrule with d.id is present in the substrate NFFG, means this
      # link is under an update, so add it with the new attributes! and 
      # remove the old one!
      self.log.debug("Removing all flowrules belonging to SGHop %s of the "
                     "current request, in case this SGHop is an update to "
                     "an already mapped one!" % d.id)
      nffg.del_flowrules_of_SGHop(d.id)

    # adding the flowrules should be after deleting the flowrules of SGHops 
    # to be updated from the data of the Request (relevant in case of MODE_ADD)
    for vnf in self.req.nodes_iter():
      for i, j, k, d in self.req.out_edges_iter([vnf], data=True, keys=True):
        # i is always vnf
        self._addFlowrulesToNFFGDerivatedFromReqLinks(vnf, j, k, nffg)

    # NOTE: in case of dry_init the E2E req pieces are not delegated to he
    # lower orchestration layers!
    if not self.dry_init:
      self._addAntiAffinityDelegationToOutput(nffg)

    if self.propagate_e2e_reqs:
      # Add EdgeReqs to propagate E2E latency reqs.
      self._divideEndToEndRequirements(nffg)

    if self.keep_e2e_reqs_in_output:
      # Add the exact same E2E requirements to the output. Maybe needed if a
      # reoptimization is possible, in this case the requirements must be
      # preserved!
      for req in self.req0.reqs:
        if req.type == NFFG.TYPE_LINK_REQUIREMENT:
          # All SAPs are already checked in the substrate graph
          nffg.add_req(req.src, req.dst, req=req)

    return nffg

  def constructDelOutputNFFG (self):
    """
    Constructs an output NFFG, which can be used by the lower layered NFFG-s 
    for deletion. SG elements are matched exclusively by their ID-s.
    """
    self.log.debug("Constructing output delete NFFG...")
    nffg = self.net0
    # we need the original copy not to spoil the struct during deletion.
    original_nffg = copy.deepcopy(self.net0)
    # there should be only VNFs, SAPs, SGHops in the request graph. And all
    # of them should be in the substrate NFFG, otherwise they were removed.

    for vnf, d in self.req.nodes_iter(data=True):
      # make the union of out and inbound edges.
      # IF type == NF and operation == delete:
      if d.type == 'NF' and d.operation == NFFG.OP_DELETE:
        self.log.debug("NF with delete operation found in DELETE NFFG: %s."%vnf)
        cnt = [0, 0]
        for graph, idx in ((original_nffg.network, 0), (self.req, 1)):
          all_connected_sghops = set([(i, j, k) for i, j, k in \
                                      graph.out_edges_iter([vnf],
                                                           keys=True) if
                                      graph[i][j][k].type == 'SG']) | \
                                 set([(i, j, k) for i, j, k in \
                                      graph.in_edges_iter([vnf],
                                                          keys=True) if
                                      graph[i][j][k].type == 'SG'])
          # 0th is network, 1st is the request
          cnt[idx] = len(all_connected_sghops)
        if cnt[0] > cnt[1]:
          # it is maybe used by some other request.
          self.log.debug("Skipping deletion of VNF %s, it has not speficied edges"
                         " connected in the substrate graph!" % vnf)
        elif cnt[0] < cnt[1]:
          # by this time this shouldn't happen, cuz those edges were removed.
          raise uet.InternalAlgorithmException(
            "After delete request preprocessing"
            ", VNF %s has more edges than in the substrate graph! Are "
            "there any SGHops in the resource graph?" % vnf)
        else:
          self.log.debug("Deleting VNF %s and all of its connected SGHops from "
                         "output NFFG" % vnf)
          hosting_infra = next(nffg.infra_neighbors(vnf))
          for dyn_link in nffg.network[vnf][hosting_infra.id].itervalues():
            self.log.debug("Deleting port %s from Infra %s"%(dyn_link.dst.id,
                                                             hosting_infra))
            hosting_infra.del_port(dyn_link.dst.id)
          nffg.del_node(vnf)

    for i, j, k, d in self.req.edges_iter(data=True, keys=True):
      nffg.del_flowrules_of_SGHop(k)
      nffg.del_edge(d.src, d.dst, d.id)
      self.log.debug("SGHop %s with its flowrules are deleted from output NFFG"
                     % d.id)
      # Maybe the VNF ports should be deleted too?

    return nffg

  def start (self):
    if self.dry_init:
      raise uet.BadInputException(
        "With dry_init set True, mapping execution cannot proceed",
        "Initialization was in dry_init mode!")
    if self.mode == NFFG.MODE_DEL:
      return self.constructDelOutputNFFG()

    # breaking when there are no more BacktrackLevels forward, meaning the 
    # mapping is full. Or exception is thrown, when mapping can't be finished.
    self.log.info("Starting core mapping procedure...")
    c = None
    curr_vnf = None
    next_vnf = None
    linkid = None
    while True:
      # Mapping must be started with subchains derived from e2e chains,
      # with lower latency requirement. It is realized by the preprocessor,
      # because it adds the subchains in the appropriate order.
      # AND moveOneSubchainLevelForward() respects this order.
      ready_for_next_subchain = False
      if c is not None:
        ready_for_next_subchain = (curr_vnf == c['chain'][-2] and \
                                   next_vnf == c['chain'][-1]) and \
                                  (curr_vnf, next_vnf, linkid) in \
                                  self.manager.link_mapping.edges(keys=True)
      tmp = self.bt_handler.moveOneBacktrackLevelForward(
        ready_for_next_subchain)
      if tmp is None:
        break
      else:
        c, sub, curr_vnf, next_vnf, linkid = tmp
        bt_record = None
        last_used_node = self.manager.getIdOfChainEnd_fromNetwork(curr_vnf)
        # break when we can step forward a BacktrackLevel, in other words: don't
        # break when we have to do backtrack then substrate network state is 
        # restored and we shall try another mapping. MappingException is
        # reraised
        # when no backtrack is available.
        while True:
          try:
            # Last element of chain is already mapped or SAP, if not
            # mapped do it now!
            if self.req.node[
              next_vnf].type != 'SAP' and \
                  self.manager.getIdOfChainEnd_fromNetwork(
                    next_vnf) == -1:
              if bt_record is None:
                self._mapOneVNF(c['id'], sub, last_used_node,
                                curr_vnf, next_vnf, linkid)
              else:
                self._takeOneGreedyStep(c['id'], bt_record)

            else:
              # We are on the end of the (sub)chain, and all chain
              # elements are mapped except the last link.
              # Execution is here if the IF condition evaluated to false:
              #   - next_vnf is a SAP OR
              #   - next_vnf is already mapped
              self._mapOneRequestLink(c['id'], sub, curr_vnf, next_vnf,
                                      linkid)
            break
          except uet.MappingException as me:
            self.log.info("MappingException catched for backtrack purpose, "
                          "its message is: " + me.msg)
            if not me.backtrack_possible:
              if self._resolveAntiAffinityDelegationIfPossible(c['id'],
                                                               next_vnf):
                break
              # re-raise the exception, we have ran out of backrack 
              # possibilities.
              raise uet.MappingException(me.msg, False,
                                         peak_sc_cnt=me.peak_sc_cnt,
                                         peak_vnf_cnt=self.peak_mapped_vnf_count)
            else:
              try:
                c, sub, bt_record, link_bt_rec_list = \
                  self.bt_handler.getNextBacktrackRecordAndSubchainSubgraph([])
              except uet.MappingException as me2:
                if not me2.backtrack_possible:
                  if self._resolveAntiAffinityDelegationIfPossible(c['id'],
                                                                   next_vnf):
                    break
                  raise uet.MappingException(me2.msg, False,
                                             peak_sc_cnt=me2.peak_sc_cnt,
                                             peak_vnf_cnt=self.peak_mapped_vnf_count)
                else:
                  raise
              for c_prime, prev_bt_rec, link_mapping_rec in link_bt_rec_list:
                if link_mapping_rec is not None:
                  self._resolveLinkMappingRecord(c_prime, link_mapping_rec)
                if prev_bt_rec is not None:
                  self._resolveBacktrackRecord(c_prime, prev_bt_rec)
              # use this bt_record to try another greedy step
              curr_vnf = bt_record['prev_vnf_id']
              next_vnf = bt_record['vnf_id']
              linkid = bt_record['reqlinkid']
              last_used_node = bt_record['last_used_node']

    # construct output NFFG with the mapping of VNFs and links
    return self.constructOutputNFFG()

  def setBacktrackParameters (self, bt_limit=6, bt_branching_factor=3):
    """
    Sets the depth and maximal branching factor for the backtracking process on
    nodes. bt_limit determines how many request graph nodes should be remembered
    for backtracking purpose. bt_branching_factor determines how many possible 
    host-path pairs should be remembered at most for one VNF.
    """
    if bt_branching_factor < 1 or "." in str(bt_branching_factor) or \
          bt_limit < 1 or "." in str(bt_limit):
      raise uet.BadInputException("Branching factor and backtrack limit should "
                                  "be at least 1, integer values",
                                  "%s and %s were given." \
                                  % (bt_limit, bt_branching_factor))
    self.bt_branching_factor = bt_branching_factor
    self.bt_limit = bt_limit
    self.bt_handler = backtrack.BacktrackHandler( \
      self.bt_handler.subchains_with_subgraphs,
      self.bt_branching_factor, self.bt_limit)

  def setResourcePrioritiesOnNodes (self, cpu=0.0, mem=0.0,
                                    storage=0.0):
    """
    Sets what weights should be used for adding up the preference values of 
    resource utilization on nodes.
    """
    sumw = cpu + mem + storage
    if abs(sumw - 1) > 0.0000001:
      raise uet.BadInputException(
        "The sum of resource priorities should be 1.0",
        "the sum of resource priorities are %s" % sumw)
    self.resource_priorities = [cpu, mem, storage]

  def reset (self):
    """Resets the CoreAlgorithm instance to its initial (after preprocessor) 
    and   state. Links weights are also calculated by the preprocessor, so those
    are reset too. self.original_chains is the list of input chains."""
    self._preproc(copy.deepcopy(self.net0), copy.deepcopy(self.req0),
                  self.original_chains)
