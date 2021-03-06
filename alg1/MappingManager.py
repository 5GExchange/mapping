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
import copy

import networkx as nx

import Alg1_Helper as helper
import UnifyExceptionTypes as uet


class MappingManager(object):
  """
  Administrates the mapping of links and VNFs
  TODO: Connect subchain and chain requirements, controls dynamic objective
  function parametrization based on where the mapping process is in an
  (E2E) chain.
  """

  def __init__ (self, net, req, chains, overall_highest_delay, dry_init):
    self.log = helper.log.getChild(self.__class__.__name__)
    self.log.setLevel(helper.log.getEffectiveLevel())

    self.log.info("Initializing MappingManager object...")

    # list of tuples of mapping (vnf_id, node_id)
    self.vnf_mapping = []
    if not dry_init:
      # SAP mapping can be done here based on their ID-s
      try:
        for vnf, dv in req.network.nodes_iter(data=True):
          if dv.type == 'SAP':
            sapid = dv.id
            sapfound = False
            for n, dn in net.network.nodes_iter(data=True):
              if dn.type == 'SAP':
                if dn.id == sapid:
                  self.vnf_mapping.append((vnf, n))
                  sapfound = True
                  break
            if not sapfound:
              self.log.error("No SAP found in network with ID: %s" % sapid)
              raise uet.MappingException(
                "No SAP found in network with ID: %s. SAPs are mapped "
                "exclusively by their ID-s." % sapid,
                backtrack_possible=False)
      except AttributeError as e:
        raise uet.BadInputException("Node data with name %s" % str(e),
                                    "Node data not found")

    # same graph structure as the request, edge data stores the mapped path
    self.link_mapping = nx.MultiDiGraph()

    # bandwidth is not yet summed up on the links
    # AND possible Infra nodes and DYNAMIC links are not removed
    self.req = req
    # all chains are included, not only SAP-to-SAPs
    self.chains = chains

    # the delay value which is considered to be infinite (although it should be
    # a constant not to zero out the latency component of objective function
    # calculation)
    self.overall_highest_delay = overall_highest_delay

    # chain - subchain pairing, stored in a bipartie graph
    self.chain_subchain = nx.Graph()
    for c in chains:
      if c['delay'] is None:
        c['delay'] = self.overall_highest_delay
    self.chain_subchain.add_nodes_from(
      (c['id'], {'avail_latency': c['delay'], 'permitted_latency': c['delay'] \
        if c['delay'] > 1e-8 else 1e-3,
                 'chain': c['chain'], 'link_ids': c['link_ids']}) \
      for c in chains)

  def getIdOfChainEnd_fromNetwork (self, _id):
    """
    If the chain is between VNFs, those must be already mapped.
    Input is an ID from the request graph. Return -1 if the node is not
    mapped.
    """
    ret = -1
    for v, n in self.vnf_mapping:
      if v == _id:
        ret = n
        break
    return ret

  def addChain_SubChainDependency (self, subcid, chainids, subc, link_ids):
    """Adds a link between a subchain id and all the chain ids that are
    contained subcid. If the first element of subc is a SAP add its network
    pair to last_used_host attribute.
    (at this stage, only SAPs are inside the vnf_mapping list)
    'subchain' attribute of a subchain data dictionary
    is a list of (vnf1,vnf2,linkid) tuples where the subchain goes.
    """
    # TODO: not E2E chains are also in self.chains, but we don`t find
    # subchains for them, so their latency is not checked, the not E2E
    # chain nodes in this graph always stay the same so far.
    self.chain_subchain.add_node(subcid,
                                 last_used_host=self
                                 .getIdOfChainEnd_fromNetwork(
                                   subc[0]),
                                 subchain=zip(subc[:-1], subc[1:], link_ids))
    if len(chainids) == 0:
      self.chain_subchain.add_edge(self.max_input_chainid, subcid)
    for cid in chainids:
      # the common chain ID for all best-effort subchains
      # (self.max_input_chainid) shouldn't be in chainids in any case!
      if cid >= self.max_input_chainid:
        raise uet.InternalAlgorithmException(
          "Invalid chain identifier given to MappingManager!")
      else:
        self.chain_subchain.add_edge(cid, subcid)

  def getLocalAllowedLatency (self, subchain_id, vnf1=None, vnf2=None,
                              linkid=None):
    """
    Checks all sources/types of latency requirement, and identifies
    which is the strictest. The smallest 'maximal allowed latency' will be
    the strictest one. We cannot use paths with higher latency value than
    this one.
    The request link is ordered vnf1, vnf2. This reqlink is part of
    subchain_id subchain.
    This function should only be called on SG links.
    """
    # if there is latency requirement on a request link
    link_maxlat = float("inf")
    if vnf1 is not None and vnf2 is not None and linkid is not None:
      if self.req.network[vnf1][vnf2][linkid].type != 'SG':
        raise uet.InternalAlgorithmException(
          "getLocalAllowedLatency  function should only be called on SG links!")
      if hasattr(self.req.network[vnf1][vnf2][linkid], 'delay'):
        if self.req.network[vnf1][vnf2][linkid].delay is not None:
          link_maxlat = self.req.network[vnf1][vnf2][linkid].delay
    try:
      # find the strictest chain latency which applies to this link
      chain_maxlat = float("inf")
      for c in self.chain_subchain.neighbors_iter(subchain_id):
        if c > self.max_input_chainid:
          raise uet.InternalAlgorithmException(
            "Subchain-subchain connection is not allowed in chain-subchain "
            "bipartie graph!")
        elif self.chain_subchain.node[c]['avail_latency'] < chain_maxlat:
          chain_maxlat = self.chain_subchain.node[c]['avail_latency']

      if min(chain_maxlat, link_maxlat) > self.overall_highest_delay:
        raise uet.InternalAlgorithmException("Local allowed latency should"
                                             " never exceed the "
                                             "overall_highest_delay")
      latreq_to_return = min(chain_maxlat, link_maxlat)
      if latreq_to_return < 1e-8:
        latreq_to_return = 1e-3
        # this should be the ideal operation, but most of the cases the latency
        # parameters from the resources are missing, so we substitute them with
        # zero in order they do not ruin anything with the missing resources...
        # raise uet.BadInputException("End-to-end delay requirement shouldn't
        #  be "
        # "zero!","Local allowed latency for chain %s is %f"
        #                             %(chain_link_ids, lal))
      return latreq_to_return

    except KeyError as e:
      raise uet.InternalAlgorithmException(
        "Bad construction of chain-subchain bipartie graph!")

  def areChainEndsReachableInLatency (self, used_lat, potential_host, subcid):
    """
    Does a forward checking to determine whether the ending SAPs of the involved
    E2E chains of this subchain are still reachable in terms of latency if we
    map the current VNF to 'potential_host' during the mapping of 'subcid'.
    """
    for c in self.chain_subchain.neighbors_iter(subcid):
      #
      if c < self.max_input_chainid:
        # Chain end should always be available because they are E2E chains.
        chainend = self.getIdOfChainEnd_fromNetwork( \
          self.chain_subchain.node[c]['chain'][-1])
        if self.shortest_paths_lengths[potential_host][chainend] > \
              self.getLocalAllowedLatency(subcid) - used_lat:
          self.log.debug(
            "Potential mapping of a VNF to host %s was too far from"
            " chain end %s because of E2E latency requirement." %
            (potential_host, chainend))
          return False
      elif c == self.max_input_chainid:
        if len(self.chain_subchain.neighbors(subcid)) != 1:
          raise uet.InternalAlgorithmException("If a subchain is already "
                                               "connected to the common "
                                               "best-effort chain, then it "
                                               "shouldn't "
                                               "have other neighbors!")
        return True
      else:
        raise uet.InternalAlgorithmException("Invalid connection in Chain-"
                                             "Subchain graph!")
    return True

  def isVNFMappingDistanceGood (self, vnf1, vnf2, n1, n2):
    """
    Mapping vnf2 to n2 shouldn`t be further from n1 (vnf1`s host) than
    the strictest latency requirement of all the links between vnf1 and vnf2
    """
    # this equals to the min of all latency requirements (req link local OR
    # remaining E2E) that is given for any SGHop between vnf1 and vnf2.
    max_permitted_vnf_dist = float("inf")
    for i, j, linkid, d in self.req.network.edges_iter([vnf1], data=True,
                                                       keys=True):
      if self.req.network[i][j][linkid].type != 'SG':
        self.log.warn(
          "There is a not SG link left in the Service Graph, but now it "
          "didn`t cause a problem.")
        continue
      if j == vnf2:
        # i,j are always vnf1,vnf2
        for c, chdata in self.chain_subchain.nodes_iter(data=True):
          if 'subchain' in chdata.keys():
            if (vnf1, vnf2, linkid) in chdata['subchain']:
              lal = self.getLocalAllowedLatency(c, vnf1, vnf2, linkid)
              if lal < max_permitted_vnf_dist:
                max_permitted_vnf_dist = lal
              break
    if self.shortest_paths_lengths[n1][n2] > max_permitted_vnf_dist:
      self.log.debug("Potential node mapping was too far from last host because"
                     " of link or remaining E2E latency requirement!")
      return False
    else:
      return True

  def updateChainLatencyInfo (self, subchain_id, used_lat, last_used_host):
    """Updates how much latency does the mapping process has left which
    applies for this subchain.
    """
    for c in self.chain_subchain.neighbors_iter(subchain_id):
      # feasibility already checked by the core algorithm
      self.chain_subchain.node[c]['avail_latency'] -= used_lat
      new_avail_lat = self.chain_subchain.node[c]['avail_latency']
      permitted = self.chain_subchain.node[c]['permitted_latency']
      if new_avail_lat > 1.01 * permitted or \
            new_avail_lat <= -0.01 * permitted:
        raise uet.InternalAlgorithmException("MappingManager error: End-to-End"
                                             " available latency cannot "
                                             "exceed maximal permitted or got "
                                             "below zero!")
    self.chain_subchain.node[subchain_id]['last_used_host'] = last_used_host

  def addShortestRoutesInLatency (self, sp):
    """Shortest paths are between physical nodes. These are needed to
    estimate the importance of laltency in the objective function.
    """
    self.shortest_paths_lengths = sp

  def setMaxInputChainId (self, maxcid):
    """Sets the maximal chain ID given by the user. Every chain with lower
    ID-s are given by the user, higher ID-s are subchains generated by
    the preprocessor.
    """
    # Give a spare chain ID for all the best effort subchains, so connect all
    # the subchains to this (self.max_input_chainid) chain in the helper graph
    self.max_input_chainid = maxcid
    self.chain_subchain.add_node(self.max_input_chainid,
                                 {'avail_latency': self.overall_highest_delay,
                                  'permitted_latency':
                                    self.overall_highest_delay})
    # we can't use the same ID-s for the output chains, because they will be
    # splitted into pieces.
    self.max_output_chainid = self.max_input_chainid + 1

  def addReqLink_ChainMapping (self, colored_req):
    """
    SGHop -> E2E chain mapping is required to calculate the splitted EdgeReqs
    for the lower layer orchestration algorithm. The graph should be deepcopied
    because the preprocessor changes it!
    """
    self.colored_req = copy.deepcopy(colored_req)

  def getSGHopOfChainMappedHere (self, cid, infra, last_sghop_id):
    """
    Returns an SGHop ID which is part of 'cid' chain and its path traverses
    'infra'. Should be used when this infra is only used as forwarding infra,
    but not as for hosting VNF for 'cid'. last_sghop_id indicates where is the
    requirement division process in the chain.
    WTF? always returns last_sghop_id??
    """
    for c in self.chains:
      if cid == c['id']:
        for vnf1, vnf2, lid in zip(c['chain'][:-1], c['chain'][1:],
                                   c['link_ids']):
          if infra in self.link_mapping[vnf1][vnf2][lid]['mapped_to']:
            if last_sghop_id in c['link_ids']:
              if lid == last_sghop_id:
                return lid
            else:
              return lid
    else:
      raise uet.InternalAlgorithmException("SGHop for chain %s couldn't be "
                                           "found in infra %s" % (cid, infra))

  def genPathOfChains (self, nffg):
    """
    Returns a generator of the mapped stucture starting from the beginning of
    chains and finding which Infra nodes are used during the mapping. Generates
    (chain_id, entering_sghop_id, infra_id) tuples, and iterates on all chains.
    The 2nd item is the ID of the first VNF of the chain path part which is
    mapped to this infra OR None if no VNF is mapped here (just transit infra).
    Returns also SAPs on the path!
    """
    for c in self.chains:
      prev_infra_of_path = None
      for vnf1, vnf2, lid in zip(c['chain'][:-1], c['chain'][1:],
                                 c['link_ids']):
        # iterate on 'mapped_to' attribute of vnf1,vnf2,lid link of
        # link_mapping structure
        path_of_lid = self.link_mapping[vnf1][vnf2][lid]['mapped_to']
        for forwarding_infra in path_of_lid:
          if prev_infra_of_path is None or \
                forwarding_infra != prev_infra_of_path:
            prev_infra_of_path = forwarding_infra
            yield c['id'], vnf2 if \
              self.getIdOfChainEnd_fromNetwork(vnf2) == forwarding_infra or \
              self.getIdOfChainEnd_fromNetwork(
                vnf1) == forwarding_infra else None, \
                  forwarding_infra
            # VNF2 is handled by the iteration on link mapping structure (
            # because
            # 'mapped_to' contains the hosting infra of vnf1 and vnf2 as well)

  def getNextOutputChainId (self):
    self.max_output_chainid += 1
    return self.max_output_chainid

  def isItTransitInfraNow (self, infra, sg_hop_obj):
    """
    Checks whether this infra routes the traffic of the chain only at this part
    (indicated by sg_hop) of the chain. The infra may host other parts of the
    chain where it also hosts VNFs.
    """
    sghop_hosting_path = self.link_mapping[sg_hop_obj.src.node.id] \
                           [sg_hop_obj.dst.node.id][sg_hop_obj.id]['mapped_to'][
                         1:-1]
    return infra in sghop_hosting_path

  def getNextChainPieceOfReqSubgraph (self, cid, subgraph, sg_hop):
    """
    Iterates on all the "inbound" SGHops of this subgraph (these are not part
    of the subgraph, they were the bordering edges in the request graph) and
    finds the part of the given chain (cid) which starts from sg_hop and is
    mapped here.
    We don't need the BiSBiS directly but all the VNF-s of subgraph should be
    mapped to the same BiSBiS.
    """
    # A structure for storing SGHop
    # store list, there can be multiple disjoint chain parts mapped
    # here (if an internal VNF is mapped elsewhere)
    for i, j, k, d in self.colored_req.edges_iter(data=True, keys=True):
      if i not in subgraph.nodes_iter() and j in subgraph.nodes_iter() \
         and k == sg_hop:
        # i,j,k is an inbound SGHop from the (implicitly) given BiSBiS
        if cid in d['color']:
          for c in self.chains:
            if cid == c['id'] and j in c['chain']:
              found_beginnig = False
              # i is not mapped to this Infra, but to the previous Infra.
              chain_piece = [i, j]
              link_ids_piece = [k]
              # find which part of the chain is mapped here
              for vnf1, vnf2, lid in zip(c['chain'][:-1], c['chain'][1:],
                                         c['link_ids']):
                if (vnf1 != j or lid != c['link_ids'][c['link_ids']. \
                   index(sg_hop) + 1]) \
                   and not found_beginnig:
                  continue
                elif not found_beginnig:
                  found_beginnig = True
                if found_beginnig:
                  if subgraph.has_edge(vnf1, vnf2, key=lid):
                    chain_piece.append(vnf2)
                    link_ids_piece.append(lid)
                    continue
                  else:
                    break
              # vnf2 is mapped to the next Infra
              # the subgraph CAN'T have SAP-s, so vnf2 can be a SAP if
              # this infra is the last to host a VNF for this chain
              chain_piece.append(vnf2)
              link_ids_piece.append(lid)
              return chain_piece, link_ids_piece
    else:
      raise uet.InternalAlgorithmException("Mapped chain part couldn't be found"
                                           " on a given infra for chain %s!"
                                           % cid)

  def getRemainingE2ELatency (self, chain_id):
    """
    Returns the remaining latency of a given E2E chain.
    """
    return self.chain_subchain.node[chain_id]['avail_latency']

  def cmpBasedOnDelayDist (self, h1, h2, origin):
    """
    Determines wether h1 or h2 is closer to origin based on distance measured
    in latency.
    """
    if self.shortest_paths_lengths[origin][h1] < \
       self.shortest_paths_lengths[origin][h2]:
      return -1
    elif self.shortest_paths_lengths[origin][h1] > \
       self.shortest_paths_lengths[origin][h2]:
      return 1
    else:
      return 0

  def calcDelayPrefValues (self, hosts, vnf1, vnf2, reqlid, cid, subg,
                           node_id):
    """
    Sorts potential hosts in the network based on a composite key:
    Firstly, based on how far is the host from the shortest path between the
    (sub)chain ends, creates sets.
    Secondly, based on distance from the current host, measured in delay.
    Also calculates their latency component value, and returns a list of tuples:
    (host, lat_pref_value).
    """
    # should always be mapped already
    self.log.debug("Calculating latency preference values for placing VNF %s "
                   "for hosts %s." % (vnf2, hosts))
    strictest_cid = min(self.chain_subchain[cid].keys(),
                        key=lambda sc, graph=self.chain_subchain: \
                          graph.node[sc]['avail_latency'])
    end_sap = None
    if strictest_cid == self.max_input_chainid:
      # If this is a best-effort link, we have to inspect latency until the
      # subchain's end.
      end_of_besteffort_subc = self.chain_subchain.node[cid]['subchain'][-1][1]
      # This VNF should always be mapped due to Best-effort subchain retrieval
      # This is already checked by the best-effort subchain finding procedure.
      if self.getIdOfChainEnd_fromNetwork(end_of_besteffort_subc) == -1:
        raise uet.InternalAlgorithmException("Last VNF of best-effort subchain "
                                             "should already be mapped "
                                             "temporarily!")
      else:
        end_sap = end_of_besteffort_subc
    else:
      end_sap = self.chain_subchain.node[strictest_cid]['chain'][-1]
    chainend = self.getIdOfChainEnd_fromNetwork(end_sap)
    paths, _ = helper.shortestPathsBasedOnEdgeWeight(subg, node_id,
                                                     weight='delay',
                                                     target=chainend)
    sh_path = paths[chainend]
    sh_path_lat = self.shortest_paths_lengths[node_id][chainend]
    chain_link_ids = None
    if strictest_cid == self.max_input_chainid:
      chain_link_ids = list(zip(*self.chain_subchain.node[cid]['subchain'])[2])
    else:
      chain_link_ids = self.chain_subchain.node[strictest_cid]['link_ids']
    remaining_chain_len = len(chain_link_ids[chain_link_ids.index(reqlid):])
    if remaining_chain_len == 1:
      raise uet.InternalAlgorithmException("Sorting based on latency preference"
                                           " value shouldn't be called when "
                                           "only one request link is left!")
    # If the current cid is a best-effort subchain, lal will be around the
    # self.overall_highest_delay (maybe decremented a bit already) -> which
    # means almost surely only one distance layer in the structure.
    lal = self.getLocalAllowedLatency(cid)
    dist_layer_step = float(lal) / \
                      remaining_chain_len
    dist_layers = {}
    for h, sumlat in hosts:
      if h in sh_path:
        if 0 in dist_layers:
          dist_layers[0].append((h, sumlat))
        else:
          dist_layers[0] = [(h, sumlat)]
      else:
        k = 2
        placed_h_in_dist_layer = False
        while sh_path_lat + (k - 1) * dist_layer_step < lal:
          if self.shortest_paths_lengths[node_id][h] + \
             self.shortest_paths_lengths[h][chainend] < \
                sh_path_lat + k * dist_layer_step:
            if k - 1 in dist_layers:
              dist_layers[k - 1].append((h, sumlat))
            else:
              dist_layers[k - 1] = [(h, sumlat)]
            placed_h_in_dist_layer = True
            break
          k += 1
        if not placed_h_in_dist_layer:
          self.log.debug(
            "Host %s was filtered from subgraph of chain %s because it"
            " was too far from current and destination hosts!" %
            (h, chain_link_ids))
    # sort host inside distance layers and calculate the pref values.
    hosts_with_lat_values = []
    lat_value_step_cnt = (lal - sh_path_lat) / \
                         dist_layer_step
    self.log.debug("Dist layers: %s" % dist_layers)
    for k in dist_layers:
      current_layer = sorted(dist_layers[k], cmp=lambda h1, h2,
                                                        origin=node_id: \
        self.cmpBasedOnDelayDist(h1[0], h2[0], origin))
      i = 0.0
      for h, sumlat in current_layer:
        # TODO: add capability to eliminate average calculation with previous
        # latency pref value
        hosts_with_lat_values.append(
          (h, sumlat, (float(k) / lat_value_step_cnt + \
                       i / float(len(current_layer)) / lat_value_step_cnt + \
                       float(sumlat) / lal) / 2.0))
        i += 1.0
      self.log.debug(
        "Processed distance layer %s for mapping VNF %s" % (k, vnf2))
    return hosts_with_lat_values
