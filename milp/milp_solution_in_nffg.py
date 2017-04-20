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
import alg1.UnifyExceptionTypes as uet

# This is used by eval("migration_costs." + migration_handler_name)
import migration_costs

log = logging.getLogger("MIP-NFFG-conv")
logging.basicConfig(format='%(levelname)s:%(name)s:%(message)s')
log.setLevel(logging.DEBUG)


def get_MIP_solution (reqnffgs, netnffg, migration_handler,
                      migration_coeff=None,
                      load_balance_coeff=None,
                      edge_cost_coeff=None):
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
  mc.init_model_creator(migration_coeff=migration_coeff,
                        load_balance_coeff=load_balance_coeff,
                        edge_cost_coeff=edge_cost_coeff)
  if isFeasibleStatus(mc.run_milp()):
    solution = mc.solution
    # TODO: throws undeterministic exception on node and link bandwitdth MILP variable checking with check_deviation
    # instead validate: use calcculate available resource functions on the mappedNFFG
    # solution.validate_solution(debug_output=False)
    if len(solution.mapping_of_request) > 1:
      raise Exception(
        "MILP shouldn't have produced multiple mappings, because the input "
        "request NFFGs were merged together into one request NFFG")
    return solution.mapping_of_request.values()[0]


def add_saps_if_needed_for_link (link, nffg):
  if link.dst.node.type == 'SAP' and link.dst.node.id not in nffg.network:
    added_sap1 = nffg.add_sap(sap_obj=link.dst.node)
    # log.debug("SAP added: %s, ports: %s" % (added_sap1,added_sap1.ports))
  if link.src.node.type == 'SAP' and link.src.node.id not in nffg.network:
    added_sap2 = nffg.add_sap(sap_obj=link.src.node)
    # log.debug("SAP added: %s" % added_sap2)


def convert_mip_solution_to_nffg (reqs, net, file_inputs=False,
                                  migration_handler=None,
                                  migration_coeff=None,
                                  load_balance_coeff=None,
                                  edge_cost_coeff=None,
                                  reopt=True):
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

  # Retrieve the e2e SCs only to remove them from the request after the MILP
  # has processed them, but they mustn't be in the request for output NFFG
  # consturction!
  request_for_milp = copy.deepcopy(request)
  chains = helper.retrieveE2EServiceChainsFromEdgeReqs(request)

  net = helper.substituteMissingValues(net)

  # create the class of the algorithm
  # unnecessary preprocessing is executed
  ############################################################################
  # HACK: We only want to use the algorithm class to generate an NFFG, we will 
  # fill the mapping struct with the one found by MIP
  # Path requirements are handled by the MILP, but Core has to know the
  # linkbandwidths to create the output NFFG properly
  alg = CoreAlgorithm(net, request, chains,
                      NFFG.MODE_REMAP if reopt else NFFG.MODE_ADD, False,
                      overall_highest_delay, dry_init=True,
                      propagate_e2e_reqs=False, keep_e2e_reqs_in_output=True)

  net = alg.bare_infrastucture_nffg
  # move 'availres' and 'availbandwidth' values of the network to maxres, 
  # because the MIP solution takes them as available resource.
  if not reopt:
    for n in net.infras:
      n.resources = n.availres
    for d in net.links:
      # there shouldn't be any Dynamic links by now.
      d.bandwidth = d.availbandwidth

  log.debug("TIMING: %ss has passed during CoreAlgorithm initialization" % (
    time.time() - current_time))
  current_time = time.time()

  mapping_of_req = get_MIP_solution([request_for_milp], net, migration_handler,
                                    migration_coeff=migration_coeff,
                                    load_balance_coeff=load_balance_coeff,
                                    edge_cost_coeff=edge_cost_coeff)

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

  # The CoreAlgorithm processing or the constructOutputNFFG cannot do it, we
  # have to add them manually.
  for req in request_for_milp.reqs:
    if not mappedNFFG.network.has_edge(req.src.node.id, req.dst.node.id,
                                       key=req.id):
      log.debug("Adding requirement link on path %s back to the output."%
                req.sg_path)
      log.debug("SAPs in mappedNFFG: %s"%[s for s in mappedNFFG.saps])
      add_saps_if_needed_for_link(req, mappedNFFG)
      mappedNFFG.add_req(req.src, req.dst, req=req)

  # replace Infinity values
  helper.purgeNFFGFromInfinityValues(mappedNFFG)

  log.debug("TIMING: %ss has passed with MILP output conversion" % (
    time.time() - current_time))

  # print mappedNFFG.dump()
  return mappedNFFG


def MAP (request, resource, optimize_already_mapped_nfs=True,
         migration_handler_name=None, migration_coeff=None,
         load_balance_coeff=None, edge_cost_coeff=None,
         **migration_handler_kwargs):
  """
  Starts an offline optimization of the 'resource', which may contain NFs for
  considering migration if optimize_already_mapped_nfs is set. 'request' should
  be new NF-s to be mapped during the reoptimization of 'resource'.
  If 'optimize_already_mapped_nfs' is set to false, 'request' should contain
  only NF-s which are net yet mapped to resource.

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
  req_nf_ids = [nf.id for nf in request.nfs]
  if optimize_already_mapped_nfs:
    # This is a full reoptimization, add VNFs and everything from resource to
    # request for reoptimization!
    for vnf in resource.nfs:
      if vnf.id not in req_nf_ids:
        # log.debug("Adding NF %s to request for reoptimization."%vnf.id)
        request.add_nf(vnf)

    NFFGToolBox.recreate_all_sghops(resource)

    for sg in resource.sg_hops:
      if not request.network.has_edge(sg.src.node.id, sg.dst.node.id,
                                      key=sg.id):
        # log.debug("Adding SGHop %s to request from resource."%sg.id)
        add_saps_if_needed_for_link(sg, request)
        request.add_sglink(sg.src, sg.dst, hop=sg)

    # reqs in the substrate (requirements satisfied by earlier mapping) needs
    #  to be respected by the reoptimization, and mogration can only be done
    # if it is not violated!
    log.debug("e2e reqs in request:%s, e2e reqs in resource, e.g: %s"%
              ([r.sg_path for r in request.reqs],
               [r.sg_path for r in resource.reqs][:20]))
    # log.debug("SAPs in resource: %s" % [s for s in resource.saps])
    for req in resource.reqs:
      # all possible SAPs should be added already!
      if not request.network.has_edge(req.src.node.id, req.dst.node.id,
                                       key=req.id):
        # log.debug("Adding requirement link on path %s between %s and %s to request to preserve it "
        #         "during reoptimization"%(req.sg_path, req.src, req.dst))
        add_saps_if_needed_for_link(req, request)
        # bandwidth requirement of the already mapped SGHops are stored by
        # the resource graph!
        req.bandwidth = 0.0
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
    # Fail if there is VNF which is mapped already!
    for vnf in resource.nfs:
      if vnf.id in req_nf_ids:
        raise uet.BadInputException("If 'optimize_already_mapped_nfs' is set to "
                                    "False, request shouldn't contain VNFs "
                                    "from resource", "VNF %s is both in request "
                                                     "and resource!"%vnf.id)
  mappedNFFG = convert_mip_solution_to_nffg([request], resource,
                                            migration_handler=migration_handler,
                                            migration_coeff=migration_coeff,
                                            load_balance_coeff=load_balance_coeff,
                                            edge_cost_coeff=edge_cost_coeff,
                                            reopt=optimize_already_mapped_nfs)
  if mappedNFFG is not None:
    try:
      mappedNFFG.calculate_available_node_res()
      mappedNFFG.calculate_available_link_res([])
    except RuntimeError as re:
      log.error("MILP's resulting NFFG is invalid: %s"%re.message)
      raise uet.InternalAlgorithmException("MILP's mapping is invalid!!")
    return mappedNFFG
  else:
    raise uet.MappingException("MILP couldn't map the given service request.",
                               False)


if __name__ == '__main__':
  req, net = None, None
  with open('dictwtf-req.nffg', "r") as f:
    req = NFFG.parse(f.read())
  with open('dictwtf-net.nffg', "r") as f:
    net = NFFG.parse(f.read())

  # print "\nMIGRATION-TEST: Simple MILP: \n"
  # with open("simple-milp.nffg", "w") as f:
  #   f.write(MAP(req, net, optimize_already_mapped_nfs=False, edge_cost_coeff=1.0).dump())

  # print "\nMIGRATION-TEST: Optimize everything MILP: \n"
  # with open("reopt-milp.nffg", "w") as f:
  #   f.write(MAP(req, net, optimize_already_mapped_nfs=True).dump())
  #
  # print "\nMIGRATION-TEST: Optimize everything with migration cost MILP"
  # with open("reopt-milp-migr.nffg", "w") as f:
  #   f.write(MAP(req, net, optimize_already_mapped_nfs=True,
  #       migration_handler_name="ConstantMigrationCost", const_cost=24.0).dump())
  #
  # print "\nMIGRATION-TEST: Optimize everything with ZERO migration cost MILP"
  # with open("reopt-milp-0migr.nffg", "w") as f:
  #   f.write(MAP(req, net, optimize_already_mapped_nfs=True,
  #               migration_handler_name="ZeroMigrationCost").dump())

  print "\nMIGRATION-TEST: Optimize everything with composite objective"
  with open("reopt-milp-lb.nffg", "w") as f:
    f.write(MAP(req, net, optimize_already_mapped_nfs=True, migration_coeff=1.0,
                load_balance_coeff=1.0, edge_cost_coeff=1.0,
                migration_handler_name="ConstantMigrationCost", const_cost=2.0).dump())
