# Copyright (c) 2016 Balazs Nemeth
#
# This file is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX. If not, see <http://www.gnu.org/licenses/>.

import copy
import logging
import time
import networkx as nx

try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

from milp.MIPBaseline import Scenario, ModelCreator, isFeasibleStatus, \
  convert_req_to_request, convert_nffg_to_substrate
from alg1.Alg1_Core import CoreAlgorithm
import alg1.Alg1_Helper as helper


log = logging.getLogger("MIP-NFFG-conv")
logging.basicConfig(format='%(levelname)s:%(name)s:%(message)s')
log.setLevel(logging.DEBUG)


def get_MIP_solution (reqnffgs, netnffg, migration_handler):
  """
  Executes the MIP mapping for the input requests and network NFFGs.
  Returns the mapped structure and the references to the mapped requests.
  """
  request_seq = []
  for req in reqnffgs:
    request = convert_req_to_request(req)
    request_seq.append(request)

  substrate = convert_nffg_to_substrate(netnffg)

  scen = Scenario(substrate, request_seq)
  mc = ModelCreator(scen, migration_handler)
  mc.init_model_creator()
  if isFeasibleStatus(mc.run_milp()):
    solution = mc.solution
    solution.validate_solution(debug_output=False)
    if len(solution.mapping_of_request) > 1:
      raise Exception(
        "MILP shouldn't have produced multiple mappings, because the input "
        "request NFFGs were merged together into one request NFFG")
    return solution.mapping_of_request.values()[0]


def get_edge_id (g, srcid, srcpid, dstpid, dstid):
  """
  Retrieves the edge ID from NFFG of an arbitrary link between two ports.
  (There should only be one link.)
  """
  """Retrieve objects.
  src = nffg.network.node[src]
  dst = nffg.network.node[dst]
  srcp = src.ports[srcpid]
  dstp = dst.ports[dstpid]
  """
  for i, j, k, d in g.edges_iter(data=True, keys=True):
    if i == srcid and j == dstid and d.src.id == srcpid and d.dst.id == dstpid:
      return k


def convert_mip_solution_to_nffg (reqs, net, file_inputs=False,
                                  mode=NFFG.MODE_REMAP, migration_handler=None):
  """
  At this point the VNFs of 'net' should only represent the occupied
  resources and reqs the request NFFGs to be mapped!
  :param reqs:
  :param net:
  :param file_inputs: may read the input NFFGs from files.
  :param mode:
  :param migration_handler:
  :return:
  """
  if file_inputs:
    request_seq = []
    for reqfile in reqs:
      with open(reqfile, "r") as f:
        req = NFFG.parse(f.read())
        request_seq.append(req)

    with open(net, "r") as g:
      net = NFFG.parse(g.read())
  else:
    request_seq = reqs

  # all input NFFG-s are obtained somehow

  current_time = time.time()
  ######################################################################
  ## This part is very similar to the MappingAlgorithms.MAP() function #
  ######################################################################

  request = request_seq[0]

  # a delay value which is assumed to be infinity in terms of connection RTT
  # or latency requirement (set it to 100s = 100 000ms)
  overall_highest_delay = 100000

  # batch together all nffgs
  for r in request_seq[1:]:
    log.critical(
      "MILP shouldn't receive multiple request NFFGs (correct merge with "
      "deepcopies takes too much time), although the MILP formulation can "
      "handle multiple request NFFGs and embed only a part of them")
    request = NFFGToolBox.merge_nffgs(request, r)

  # TEST to make heuristic and MILP even in number of large object deepcopies
  # This would also be required for correct behaviour (Maybe the mapping
  # shouldn't change the input NFFG)
  request = copy.deepcopy(request)
  net = copy.deepcopy(net)

  # Rebind EdgeReqs to SAP-to-SAP paths, instead of BiSBiS ports
  # So EdgeReqs should either go between SAP-s, or InfraPorts which are
  # connected to a SAP
  request = NFFGToolBox.rebind_e2e_req_links(request)

  chainlist = helper.retrieveE2EServiceChainsFromEdgeReqs(request)

  net = helper.substituteMissingValues(net)

  # create the class of the algorithm
  # unnecessary preprocessing is executed
  ############################################################################
  # HACK: We only want to use the algorithm class to generate an NFFG, we will 
  # fill the mapping struct with the one found by MIP
  alg = CoreAlgorithm(net, request, chainlist, mode, False,
                      overall_highest_delay, dry_init=True)

  # move 'availres' and 'availbandwidth' values of the network to maxres, 
  # because the MIP solution takes them as available resource.
  net = alg.bare_infrastucture_nffg
  for n in net.infras:
    n.resources = n.availres
  for d in net.links:
    # there shouldn't be any Dynamic links by now.
    d.bandwidth = d.availbandwidth

  log.debug("TIMING: %ss has passed during CoreAlgorithm initialization" % (
    time.time() - current_time))
  current_time = time.time()

  mapping_of_req = get_MIP_solution([request], net, migration_handler)

  log.debug("TIMING: %ss has passed with MILP calculation" % (
    time.time() - current_time))
  current_time = time.time()

  mappedNFFG = NFFG(id="MILP-mapped")
  if mapping_of_req.is_embedded:
    alg.manager.vnf_mapping = []
    alg.manager.link_mapping = nx.MultiDiGraph()
    for n, vlist in mapping_of_req.snode_to_hosted_vnodes.items():
      for v in vlist:
        alg.manager.vnf_mapping.append((v, n))
    trans_link_mapping = mapping_of_req.vedge_to_spath
    for trans_sghop in trans_link_mapping:
      vnf1 = trans_sghop[0]
      vnf2 = trans_sghop[3]
      reqlid = get_edge_id(alg.req, vnf1, trans_sghop[1],
                           trans_sghop[2], vnf2)
      mapped_path = []
      path_link_ids = []
      for trans_link in trans_link_mapping[trans_sghop]:
        n1 = trans_link[0]
        n2 = trans_link[3]
        lid = get_edge_id(alg.net, n1, trans_link[1], trans_link[2], n2)
        mapped_path.append(n1)
        path_link_ids.append(lid)
      if len(trans_link_mapping[trans_sghop]) == 0:
        mapped_path.append(alg.manager.getIdOfChainEnd_fromNetwork(vnf1))
      else:
        mapped_path.append(n2)

      alg.manager.link_mapping.add_edge(vnf1, vnf2, key=reqlid,
                                        mapped_to=mapped_path,
                                        path_link_ids=path_link_ids)

    mappedNFFG = alg.constructOutputNFFG()
  else:
    log.info("MILP didn't produce a mapping for request %s" % mapping_of_req)
    return None

  # replace Infinity values
  helper.purgeNFFGFromInfinityValues(mappedNFFG)

  log.debug("TIMING: %ss has passed with MILP output conversion" % (
    time.time() - current_time))

  # print mappedNFFG.dump()
  return mappedNFFG


def MAP (request, resource, optimize_already_mapped_nfs=True,
         migration_handler_name=None,
         **migration_handler_kwargs):
  """
  Starts an offline optimization of the 'resource', which may contain NFs for
  considering migration if optimize_already_mapped_nfs is set

  :param optimize_already_mapped_nfs:
  :param request:
  :param resource:
  :param migration_handler_name:
  :param migration_handler_kwargs:
  :return:
  """
  if optimize_already_mapped_nfs:
    # We only have to deal with migration in this case.
    if migration_handler_name is not None and type(migration_handler_name) is str:
      migration_cls = eval("migration_costs." + migration_handler_name)

      # This resource NFFG needs to include all VNFs, which may play any role in
      # migration or mapping. Migration need to know about all of them for
      # setting zero cost for not yet mapped VNFs
      nffg_with_all_nfs = resource
      tmp_vnfs_added = []
      mapped_nf_ids = [nf.id for nf in resource.nfs]
      for vnf in request.nfs:
        if vnf.id not in mapped_nf_ids:
          nffg_with_all_nfs.add_nf(nf=vnf)
          tmp_vnfs_added.append(vnf)

      migration_handler = migration_cls(nffg_with_all_nfs,
                                        migration_handler_kwargs)

      for vnf in tmp_vnfs_added:
        resource.del_node(vnf)
    else:
      migration_handler = None
    #TODO: add VNFs everything from resource to request for reoptimization!
  else:
    #TODO: what here?
    pass
  return convert_mip_solution_to_nffg([request], resource,
                                      migration_handler=migration_handler)


if __name__ == '__main__':
  convert_mip_solution_to_nffg(['../../examples/escape-mn-req.nffg'],
                               '../../examples/escape-mn-topo-duplicatedlinks.nffg',
                               file_inputs=True)
