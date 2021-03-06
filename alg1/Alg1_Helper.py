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
import logging
from collections import defaultdict
from heapq import heappush, heappop
from itertools import count

import UnifyExceptionTypes as uet

try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

# Basic logger for mapping
log = logging.getLogger("mapping")
# Default log level
# Change this constant to set logging level outside of ESCAPE
DEFAULT_LOG_LEVEL = logging.WARNING
# print "effective level", log.getEffectiveLevel()
# print "log level", log.level
# ESCAPE uses INFO and DEBUG levels. The default level of a logger is WARNING.
if log.getEffectiveLevel() >= logging.WARNING:
  # If the RootLogger is not configured, setup a basic config here
  logging.basicConfig(format='%(levelname)s:%(name)s:%(message)s',
                      level=DEFAULT_LOG_LEVEL)


def retrieveFullDistMtx (dist, G_full):
  # this fix access latency is used by CarrierTopoBuilder.py
  log.debug("Retrieving path lengths of SAP-s excepted because "
            "of cutting...")
  access_lat = 0.5
  for u in G_full:
    if G_full.node[u].type == 'SAP':
      u_switch_id = "-".join(tuple(u.split("-")[:1] + u.split("-")[-4:]))
      for v in G_full:
        if u == v:
          dist[u][v] = 0
        elif G_full.node[v].type == 'SAP':
          v_switch_id = "-".join(tuple(v.split("-")[:1] + \
                                       v.split("-")[-4:]))
          dist[u][v] = 2 * access_lat + dist[u_switch_id][v_switch_id]
          dist[v][u] = 2 * access_lat + dist[v_switch_id][u_switch_id]
        else:
          dist[u][v] = access_lat + dist[u_switch_id][v]
          dist[v][u] = access_lat + dist[v][u_switch_id]
  return dist


def shortestPathsInLatency (G_full, enable_shortest_path_cache,
                            enable_network_cutting=False, bidirectional=True):
  """
  Wrapper function for Floyd`s algorithm to calculate shortest paths
  measured in latency, using also nodes` forwarding latencies.
  Modified source code taken from NetworkX library.
  HACK: if enable_network_cutting=True, then all the SAP-s are cut from the 
  network and their distances are recalculated based on where they are 
  connected, which is determined by their ID-s. Its goal is to descrease the 
  running time of Floyd. This hack can only be used if the substrate network is
  generated by CarrierTopoBuilder.py
  """
  # dictionary-of-dictionaries representation for dist and pred
  # use some default dict magic here
  # for dist the default is the floating point inf value
  dist = defaultdict(lambda: defaultdict(lambda: float('inf')))

  if enable_network_cutting:
    G = copy.deepcopy(G_full)
    for n, d in G.nodes(data=True):
      if d.type == 'SAP':
        G.remove_node(n)
  else:
    G = G_full
  filename = "shortest_paths_cut.txt" if enable_network_cutting \
    else "shortest_paths.txt"
  if enable_shortest_path_cache:
    try:
      with open(filename) as sp:
        log.debug("Reading previously calculated shortest paths...")
        for line in sp:
          line = line.split(" ")
          dist[line[0]][line[1]] = float(line[2])
      if enable_network_cutting:
        return dict(retrieveFullDistMtx(dist, G_full))
    except IOError:
      log.warn("No input %s found, calculating shortest paths..." % filename)
    except ValueError:
      raise uet.BadInputException("Bad format in shortest_paths.txt",
                                  "In every line: src_id dst_id "
                                  "<<float distance in ms>>")

  for u in G:
    if G.node[u].type != 'SAP':
      dist[u][u] = G.node[u].resources['delay']
    else:
      dist[u][u] = 0
  try:
    for u, v, d in G.edges(data=True):
      e_weight = d.delay
      dist[u][v] = min(e_weight, dist[u][v])
      if G.node[u].type != 'SAP':
        dist[u][v] += G.node[u].resources['delay']
      if G.node[v].type != 'SAP':
        dist[u][v] += G.node[v].resources['delay']
  except KeyError as e:
    raise uet.BadInputException("Edge attribure(s) missing " + str(e),
                                "{'delay': VALUE}")
  try:
    for w in G:
      if G.node[w].type != 'SAP':
        for u in G:
          for v in G:
            # subtract: because the latency of node 'w' would be added twice.
            if dist[u][v] > dist[u][w] - G.node[w].resources['delay'] + dist[w][
              v]:
              dist[u][v] = dist[u][w] - G.node[w].resources['delay'] + dist[w][
                v]
              if bidirectional:
                dist[v][u] = dist[v][w] - G.node[w].resources['delay'] + \
                             dist[w][
                               u]
            # Links are always considered bidirectional?!
            if u == v and bidirectional:
              break
  except KeyError as e:
    raise uet.BadInputException("",
                                "Node attribute missing %s {'delay': VALUE}"
                                % e)
  if enable_shortest_path_cache:
    # write calclated paths to output for later use.
    log.debug("Saving calculated shorest paths to %s." % filename)
    sp = open(filename, "w")
    for u in G:
      for v in G:
        sp.write(" ".join((str(u), str(v), str(dist[u][v]), "\n")))
    sp.close()

  if enable_network_cutting:
    return dict(retrieveFullDistMtx(dist, G_full))
  else:
    return dict(dist)


def shortestPathsBasedOnEdgeWeight (G, source, weight='weight', target=None,
                                    cutoff=None):
  """
  Taken and modified from NetworkX source code,
  the function originally 'was single_source_dijkstra',
  now it returns the key edge data too.
  If a weight doesn't exist let's be permissive and give it 0 weight.
  """
  if source == target:
    return {source: [source]}, {source: []}
  push = heappush
  pop = heappop
  dist = {}  # dictionary of final distances
  paths = {source: [source]}  # dictionary of paths
  # dictionary of edge key lists of corresponding paths
  edgekeys = {source: []}
  if weight == 'delay':
    selfweight = (G.node[source].resources[weight] if \
                    G.node[source].type != 'SAP' else 0)
  else:
    selfweight = (getattr(G.node[source], weight, 0) if \
                    G.node[source].type != 'SAP' else 0)
  seen = {source: selfweight}
  c = count()
  fringe = []  # use heapq with (distance,label) tuples
  push(fringe, (selfweight, next(c), source))
  while fringe:
    (d, _, v) = pop(fringe)
    if v in dist:
      continue  # already searched this node.
    dist[v] = d
    if v == target:
      break
    # for ignore,w,edgedata in G.edges_iter(v,data=True):
    # is about 30% slower than the following
    edata = []
    for w, keydata in G[v].items():
      neighbourdata = []
      for k, dd in keydata.items():
        if not hasattr(dd, weight):
          raise uet.BadInputException(
            "Link %s should have edge attribute %s" % k,
            "Link %s is %s" % (k, dd))
        neighbourdata.append((getattr(dd, weight), k))
      minweight, edgekey = min(neighbourdata, key=lambda t: t[0])
      edata.append((w, edgekey, {weight: minweight}))

    for w, ekey, edgedata in edata:
      if G.node[w].type == 'SAP':
        tempweight = 0
      elif weight == 'delay':
        tempweight = G.node[w].resources[weight]
      else:
        tempweight = getattr(G.node[w], weight, 0)
      vw_dist = dist[v] + tempweight + edgedata[weight]
      if cutoff is not None:
        if vw_dist > cutoff:
          continue
      if w in dist:
        if vw_dist < dist[w]:
          raise ValueError('Contradictory paths found:', 'negative weights?')
      elif w not in seen or vw_dist < seen[w]:
        seen[w] = vw_dist
        push(fringe, (vw_dist, next(c), w))
        paths[w] = paths[v] + [w]
        edgekeys[w] = edgekeys[v] + [ekey]
  log.debug("Calculated distances from %s based on %s: %s" %
            (source, weight, dist))
  return paths, edgekeys


def retrieveE2EServiceChainsFromEdgeReqs (request):
  """
  Processes the service graph to retrieve the SC information and deletes the
  corresponding EdgeReq links from the SG.

  :param request: The service graph which contains EdgeReqs
  :return: a list of SC-s in format used by Algorithm1
  """
  chainlist = []
  cid = 1
  edgereqlist = []
  for req in request.reqs:
    edgereqlist.append(req)
    request.del_edge(req.src, req.dst, req.id)

  # construct chains from EdgeReqs
  for req in edgereqlist:

    if len(req.sg_path) == 1:
      # then add it as linklocal req instead of E2E req
      log.info("Interpreting one SGHop long EdgeReq (id: %s) as link "
               "requirement on SGHop: %s." % (req.id, req.sg_path[0]))
      reqlink = None
      for sg_link in request.sg_hops:
        if sg_link.id == req.sg_path[0]:
          reqlink = sg_link
          break
      if reqlink is None:
        log.warn("EdgeSGLink object not found for EdgeSGLink ID %s! "
                 "(maybe ID-s stored in EdgeReq.sg_path are not the "
                 "same type as EdgeSGLink ID-s?)")
      if req.delay is not None:
        setattr(reqlink, 'delay', req.delay)
      if req.bandwidth is not None:
        setattr(reqlink, 'bandwidth', req.bandwidth)
    elif len(req.sg_path) == 0:
      raise uet.BadInputException(
        "If EdgeReq is given, it should specify which SGHop path does it "
        "apply to", "Empty SGHop path was given to %s EdgeReq!" % req.id)
    else:
      try:
        chain = {'id': cid, 'link_ids': req.sg_path,
                 'bandwidth': req.bandwidth if req.bandwidth is not None else 0,
                 'delay': req.delay if req.delay is not None else float("inf")}
      except AttributeError:
        raise uet.BadInputException(
          "EdgeReq attributes are: sg_path, bandwidth, delay",
          "Missing attribute of EdgeReq")
      # reconstruct NF path from EdgeSGLink path
      nf_chain = []
      for reqlinkid in req.sg_path:

        # find EdgeSGLink object of 'reqlinkid'
        reqlink = None
        for sg_link in request.sg_hops:
          if sg_link.id == reqlinkid:
            reqlink = sg_link
            break
        else:
          raise uet.BadInputException(
            "Elements of EdgeReq.sg_path should be EdgeSGLink.id-s.",
            "SG link %s couldn't be found in input request NFFG" % reqlinkid)
        # add the source node id of the EdgeSGLink to NF path
        nf_chain.append(reqlink.src.node.id)
        # add the destination node id of the last EdgeSGLink to NF path
        if reqlinkid == req.sg_path[-1]:
          if reqlink.dst.node.id != req.dst.node.id:
            raise uet.BadInputException(
              "EdgeReq.sg_path should select a path between its two ends",
              "Last NF (%s) of EdgeReq.sg_path and destination of EdgeReq ("
              "%s) are not the same!" % (reqlink.dst.node.id, req.dst.node.id))
          nf_chain.append(reqlink.dst.node.id)
        # validate EdgeReq ends.
        if reqlinkid == req.sg_path[0] and \
              reqlink.src.node.id != req.src.node.id:
          raise uet.BadInputException(
            "EdgeReq.sg_path should select a path between its two ends",
            "First NF (%s) of EdgeReq.sg_path and source of EdgeReq (%s) are "
            "not the same!" % (reqlink.src.node.id, req.src.node.id))
        chain['chain'] = nf_chain
      cid += 1
      chainlist.append(chain)
  return chainlist


def substituteMissingValues (net):
  """
  Checks all resource parameters in the substrate network and substitutes the
  missing ones with either infinity or zero depending on the resource type,
  which means permissive behaviour. Modifies the input NFFG

  :param net: substrate network NFFG to process
  :return: the modified NFFG
  """
  # if some resource value is not set (is None) then be permissive and set it
  # to a comfortable value.
  for respar in ('cpu', 'mem', 'storage', 'delay', 'bandwidth'):
    for n in net.infras:
      if n.resources[respar] is None:
        if respar == 'delay':
          log.warn("Resource parameter %s is not given in %s, "
                   "substituting with 0!" % (respar, n.id))
          n.resources[respar] = 0
        else:
          log.warn("Resource parameter %s is not given in %s, "
                   "substituting with infinity!" % (respar, n.id))
          n.resources[respar] = float("inf")
  # If link res is None or doesn't exist, replace it with a neutral value.
  for i, j, d in net.network.edges_iter(data=True):
    if d.type == 'STATIC':
      if getattr(d, 'delay', None) is None:
        if d.src.node.type != 'SAP' and d.dst.node.type != 'SAP':
          log.warn("Resource parameter delay is not given in link %s "
                   "substituting with zero!" % d.id)
        setattr(d, 'delay', 0)
      if getattr(d, 'bandwidth', None) is None:
        if d.src.node.type != 'SAP' and d.dst.node.type != 'SAP':
          log.warn("Resource parameter bandwidth is not given in link %s "
                   "substituting with infinity!" % d.id)
        setattr(d, 'bandwidth', float("inf"))
  return net


def purgeNFFGFromInfinityValues (nffg):
  """
  Before running the algorithm None values for resources were replaced by 
  Infinity value to ensure seamless mapping, in case of missing parameters.
  These values should be set back to None to cooperate with surrounding layers.
  (zero values do not cause errors, and they can't be placed back unabiguously)
  """
  purge = False
  for respar in ('cpu', 'mem', 'storage', 'bandwidth'):
    for n in nffg.infras:
      if hasattr(n.resources, respar):
        if n.resources[respar] == float("inf"):
          n.resources[respar] = None
          purge = True
  if purge:
    log.info("Purging node resource data of output NFFG from Infinity "
             "values was required.")
  purge = False
  for i, j, d in nffg.network.edges_iter(data=True):
    if d.type == 'STATIC':
      if hasattr(d, 'bandwidth'):
        if d.bandwidth == float("inf"):
          d.bandwidth = None
          purge = True
  if purge:
    log.info("Purging link resource of output NFFG from Infinity values"
             " was required.")


def processInputSAPAlias (nffg):
  """
  If a SAP port's ID equals to an NF port's ID, then it means they are 
  logically the same aliases of the same SAP. So they need to be connected and 
  mapped to the same Infra for the mapping processing.
  """
  # Handle the NF-SAP connections which represent SAP aliases.
  sap_alias_links = []
  for nf in nffg.nfs:
    for pn in nf.ports:
      for sap in nffg.saps:
        for ps in sap.ports:
          # This indicates that they are logically the same service access
          # points, which should be kept on the same infra after mapping.
          if pn.sap == ps.sap and pn.sap is not None and ps.sap is not None \
             and \
                pn.role == nffg.PORT_ROLE_PROVIDER and \
                ps.role == nffg.PORT_ROLE_PROVIDER:
            # id, bandwidth, flowclass are don't care
            log.debug("Adding fake SGHop for SAP alias handling between nodes"
                      " %s, %s with SAP value: %s" % (pn.node.id, ps.node.id,
                                                      pn.sap))
            sg1 = nffg.add_sglink(ps, pn, delay=0)
            sg2 = nffg.add_sglink(pn, ps, delay=0)
            sap_alias_links.append(sg1)
            sap_alias_links.append(sg2)
  return sap_alias_links


def processOutputSAPAlias (nffg):
  """
  The helper SGHops for SAP alias handling shouldn't leave the scope of 
  mapping module. If an SGHop is identified as logical alias connection, then 
  it should be removed together with its mapped path.
  """
  if hasattr(nffg, 'sap_alias_links'):
    for sg in nffg.sap_alias_links:
      log.debug("Deleting fake SGHop between nodes %s, %s with SAP value: %s"
                % (sg.src.node.id, sg.dst.node.id, sg.src.sap))
      nffg.del_flowrules_of_SGHop(sg.id)
      if nffg.network.has_edge(sg.src.node.id, sg.dst.node.id, key=sg.id):
        nffg.del_edge(sg.src, sg.dst, sg.id)


def countConsumerSAPPorts (nffg, infra):
  """
  Counts the consumer SAPs mapped to this Infra's hosted SAP provider NFs.
  """
  consumer_count = 0
  for nf in nffg.running_nfs(infra.id):
    for p in nf.ports:
      if p.sap is not None and p.role == nffg.PORT_ROLE_CONSUMER:
        consumer_count += 1
  return consumer_count


def mapConsumerSAPPort (req, net):
  """
  Iterates on NFs to look for consumer SAP ports whihc should be mapped to 
  (one of) the Infra, which hosts a SAPPort provider NF. The mapping decision
  is made here, this cannot be backtracked during the core mapping procedure.
  Returns the fake links which are added.
  """
  sap_total_consumer_counts = {}
  mapped_nfs_to_be_added = []
  for nf in req.nfs:
    for p in nf.ports:
      if p.sap is not None and p.role is not None:
        if p.role == req.PORT_ROLE_CONSUMER:
          sap_provider_ports = []
          for nf2 in net.nfs:
            for p2 in nf2.ports:
              if p.sap == p2.sap and p2.role == net.PORT_ROLE_PROVIDER:
                # there should be only one hosting infra
                hosting_infra = next(net.infra_neighbors(nf2.id))

                # NOTE: This should be checked! But in current version the 
                # calculate_available_link_res function can only be called 
                # later, but the graph structure cannot be updated later with 
                # these preprocessing steps for SAP cons/prov handling...

                # if hosting_infra.has_enough_resource(nf.resources):
                if nf.functional_type in hosting_infra.supported:
                  if hosting_infra.id not in sap_total_consumer_counts:
                    consumer_count = countConsumerSAPPorts(net, hosting_infra)
                    sap_total_consumer_counts[hosting_infra.id] = consumer_count
                  else:
                    consumer_count = sap_total_consumer_counts[hosting_infra.id]
                  sap_provider_ports.append((hosting_infra, nf2, p2,
                                             consumer_count))
                # don't add this NF multiple times if it has more provider SAPs 
                # for the same service, named 'sap'.
                break
          # we can choose the Infra/VNF which host the least consumer SAP ports 
          # so far. NOTE: the SAPconsumerNFs' resources are not subtracted 
          # greedily during this mapping, so this can cause mapping errors! If 
          # there is always only one SAPconsumer in the SG, this is not a
          # problem.
          try:
            infra, provider_nf, provider_port, cons_count = \
              min(sap_provider_ports, key=lambda t: t[3])
            sap_total_consumer_counts[infra.id] += 1
            mapped_nfs_to_be_added.append((provider_nf, provider_port,
                                           nf, p, infra))
          except ValueError:
            raise uet.MappingException("No provider SAP could be found for "
                                       "consumer SAP of VNF %s of service "
                                       "name %s" % (
                                         nf.id, p.sap),
                                       backtrack_possible=False)
  sap_alias_links = []
  # the SG is prerocessed with the addition of the SAPProviderVNFs.
  for provider_nf, provider_port, consumer_nf, consumer_port, infra in \
     mapped_nfs_to_be_added:
    log.debug(
      "Adding an already mapped NF to indicate the place of the provider"
      " SAP for service name %s." % provider_port.sap)
    provider_nf_copy = req.add_nf(nf=copy.deepcopy(provider_nf))

    # NOTE: This would be better instead of 0-delay links!
    # setattr(consumer_nf, 'placement_criteria', [infra.id])
    log.debug("Adding fake SGHops between %s and %s to indicate SAP provider-"
              "consumer connection for service %s." %
              (provider_nf.id, consumer_nf.id, provider_port.sap))
    sg1 = req.add_sglink(provider_nf_copy.ports[provider_port.id],
                         consumer_port,
                         delay=0)
    sg2 = req.add_sglink(consumer_port,
                         provider_nf_copy.ports[provider_port.id],
                         delay=0)
    sap_alias_links.append(sg1)
    sap_alias_links.append(sg2)

  # return the modified SG
  return req, sap_alias_links


def _addBackwardAntiAffinity (nffg, nf_id, aaff_pair_id, aaff_id):
  if nf_id not in nffg.network.node[aaff_pair_id].constraints. \
     antiaffinity.itervalues():
    log.debug("Add backward anti-affinity between VNFs %s and %s to "
              "make it symmetric." % (nf_id, aaff_pair_id))
    nffg.network.node[aaff_pair_id]. \
      constraints.antiaffinity[aaff_id + "-back"] = nf_id


def makeAntiAffinitySymmetric (req, net):
  """
  Checks all anti-affinity requirements and makes them symmetric so the greedy
  mapping pocess would see the requirement from each direction. If the anti-
  affinity pair is not in the request graph, but it is in the substrate NFFG, 
  then it is added to the request, so anti-affinity delegation could be resolved
  in case of embedding failure due to the unresolvable anti-affinity.

  These extra VNF-s are handled well as VNFs to be left in place both in terms 
  of vnf_mapping stucture and substrate resource handling.
  """
  for nf in req.nfs:
    if len(nf.constraints.antiaffinity) > 0:
      for aaff_id, aaff_pair_id in nf.constraints.antiaffinity.iteritems():
        if aaff_pair_id in req:
          _addBackwardAntiAffinity(req, nf.id, aaff_pair_id, aaff_id)
        elif aaff_pair_id in net:
          req.add_node(copy.deepcopy(net.network.node[aaff_pair_id]))
          _addBackwardAntiAffinity(req, nf.id, aaff_pair_id, aaff_id)
        else:
          raise uet.BadInputException("Anti-affinity should refer to a VNF "
                                      "which is in the request graph or "
                                      "mapped already in the "
                                      "substrate graph",
                                      "VNF %s not found for anti-affiny from %s"
                                      " to %s" % (
                                        aaff_pair_id, nf.id, aaff_pair_id))
