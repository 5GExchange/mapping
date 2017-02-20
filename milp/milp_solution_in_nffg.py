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

# This is used by eval("migration_costs." + migration_handler_name)
import migration_costs

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
    raise Exception("MILP shouldn't receive multiple request NFFGs (correct "
                    "merge with "
                    "deepcopies takes too much time), although the MILP "
                    "formulation can "
                    "handle multiple request NFFGs and embed only a part of them")
    request = NFFGToolBox.merge_nffgs(request, r)

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
                      overall_highest_delay, dry_init=True,
                      propagate_e2e_reqs=False, keep_e2e_reqs_in_output=True)

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
      reqlid = trans_sghop[4]
      mapped_path = []
      path_link_ids = []
      for trans_link in trans_link_mapping[trans_sghop]:
        n1 = trans_link[0]
        n2 = trans_link[3]
        lid = trans_link[4]
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
  considering migration if optimize_already_mapped_nfs is set.

  :param optimize_already_mapped_nfs:
  :param request:
  :param resource:
  :param migration_handler_name:
  :param migration_handler_kwargs:
  :return:
  """
  # Make heuristic and MILP even in number of large object deepcopies
  # This would also be required for correct behaviour (Maybe the mapping
  # shouldn't change the input NFFG)
  request = copy.deepcopy(request)
  resource = copy.deepcopy(resource)

  migration_handler = None
  if optimize_already_mapped_nfs:
    # This is a full reoptimization, add VNFs and everything from resource to
    # request for reoptimization!
    req_nf_ids = [nf.id for nf in request.nfs]
    for vnf in resource.nfs:
      if vnf.id not in req_nf_ids:
        request.add_nf(vnf)

    NFFGToolBox.recreate_all_sghops(resource)

    for sg in resource.sg_hops:
      if not request.network.has_edge(sg.src.node.id, sg.dst.node.id,
                                      key=sg.id):
        if sg.dst.node.type == 'SAP' and sg.dst.node.id not in request.network:
          request.add_sap(sap_obj=sg.dst.node)
        if sg.src.node.type == 'SAP' and sg.src.node.id not in request.network:
          request.add_sap(sap_obj=sg.src.node)
        request.add_sglink(sg.src, sg.dst, hop=sg)

    # reqs in the substrate (requirements satisfied by earlier mapping) needs
    #  to be respected by the reoptimization, and mogration can only be done
    # if it is not violated!
    for req in resource.reqs:
      # all possible SAPs are added already!
      request.add_req(req.src, req.dst, req=req)

    # We have to deal with migration in this case only.
    if migration_handler_name is not None and type(
       migration_handler_name) is str:
      migration_cls = eval("migration_costs." + migration_handler_name)

      # This resource NFFG needs to include all VNFs, which may play any role in
      # migration or mapping. Migration need to know about all of them for
      # setting zero cost for not yet mapped VNFs
      migration_handler = migration_cls(request, resource,
                                        **migration_handler_kwargs)
  else:
    # No migration can happen! We just map the given request and resource
    # with MILP.
    pass
  return convert_mip_solution_to_nffg([request], resource,
                                      migration_handler=migration_handler)


if __name__ == '__main__':
  req, net = None, None
  with open('../alg1/nffgs/escape-mn-req-extra.nffg') as f:
    req = NFFG.parse(f.read())
  with open('../alg1/nffgs/escape-mn-double-mapped.nffg', "r") as f:
    net = NFFG.parse(f.read())

  print "\nMIGRATION-TEST: Simple MILP: \n"
  with open("simple-milp.nffg", "w") as f:
    f.write(MAP(req, net, optimize_already_mapped_nfs=False).dump())

  print "\nMIGRATION-TEST: Optimize everything MILP: \n"
  with open("reopt-milp.nffg", "w") as f:
    f.write(MAP(req, net, optimize_already_mapped_nfs=True).dump())

  print "\nMIGRATION-TEST: Optimize everything with migration cost MILP"
  with open("reopt-milp-migr.nffg", "w") as f:
    f.write(MAP(req, net, optimize_already_mapped_nfs=True,
        migration_handler_name="ConstantMigrationCost", const_cost=24.0).dump())

  print "\nMIGRATION-TEST: Optimize everything with ZERO migration cost MILP"
  with open("reopt-milp-0migr.nffg", "w") as f:
    f.write(MAP(req, net, optimize_already_mapped_nfs=True,
                migration_handler_name="ZeroMigrationCost").dump())