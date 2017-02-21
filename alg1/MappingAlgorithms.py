#!/usr/bin/python -u
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
Interface for the Mapping Algorithms provided for ESCAPE.
Receives the service request and the resource information in the internal
(NetworkX based) NFFG model, and gives it to the algorithm covering its 
invocation details.
NOTE: Currently only SAP-to-SAP EdgeReqs, or link-local (which are parallel 
with an SGLink) EdgeReqs are supported. After generating the service chains
from the EdgeReqs, all SG links must be in one of the subchains. 
"""

import sys
import traceback
from pprint import pformat

import Alg1_Helper as helper
import UnifyExceptionTypes as uet
from Alg1_Core import CoreAlgorithm
from Alg1_Helper import NFFG, NFFGToolBox

# object for the algorithm instance
alg = None

def MAP (request, network, enable_shortest_path_cache=False,
         bw_factor=1, res_factor=1, lat_factor=1,
         shortest_paths=None, return_dist=False, propagate_e2e_reqs=True,
         bt_limit=6, bt_branching_factor=3, mode=NFFG.MODE_ADD, **kwargs):
  """
  The parameters are NFFG classes.
  Calculates service chain requirements from EdgeReq classes.
  enable_shortest_path_cache: whether we should store the calculated shortest 
  paths in a file for later usage.
  MODE_REMAP: the resources of the VNF-s contained in the resource
  NFFG are just deleted from the resource NFFG before mapping.
  MODE_ADD: The stored VNF information in the substrate graph is interpreted as
  reservation state. Their resource requirements are subtracted from the 
  available. If an ID is present in both the substrate and request graphs, the 
  resource requirements (and the whole instance) will be updated.
  MODE_DEL: Finds the elements of the request NFFG in the substrate NFFG and
  removes them.
  """

  # possible values are NFFG.MODE_ADD, NFFG.MODE_DELETE, NFFG.MODE_REMAP
  if mode is None:
    raise uet.BadInputException("Mapping operation mode should always be set",
                                "No mode specified for mapping operation!")

  try:
    # if there is at least ONE SGHop in the graph, we don't do SGHop retrieval.
    next(request.sg_hops)
    sg_hops_given = True
  except StopIteration:
    sg_hops_given = False
    helper.log.warn("No SGHops were given in the Service Graph! Could it "
                    "be retreived? based on the Flowrules?")
    NFFGToolBox.recreate_all_sghops(request)

    try:
      next(request.sg_hops)
      sg_hops_retrieved = True
    except StopIteration:
      sg_hops_retrieved = False

  # recreate SGHops in case they were not added before giving the substrate
  # NFFG to the mapping
  network = NFFGToolBox.recreate_all_sghops(network)

  sap_alias_links = []
  if not mode == NFFG.MODE_DEL:
    helper.makeAntiAffinitySymmetric(request, network)

    # add fake SGHops to handle logical SAP aliases.
    sap_alias_links = helper.processInputSAPAlias(request)
    request, consumer_sap_alias_links = helper.mapConsumerSAPPort(request,
                                                                  network)
    sap_alias_links.extend(consumer_sap_alias_links)
    if len(sap_alias_links) > 0:
      setattr(network, 'sap_alias_links', sap_alias_links)

  # if after recreation and SAP alias handling there are at least one SGHop in
  # the request we can proceed mapping.
  if not sg_hops_given and not sg_hops_retrieved and len(sap_alias_links) == 0:
    for nf in request.nfs:
      if nf.id not in network.network:
        raise uet.BadInputException("If SGHops are not given, flowrules should"
                                    " be in the NFFG",
                                    "No SGHop could be retrieved based on the "
                                    "flowrules of the NFFG. And there is a VNF"
                                    " which is not mapped yet!")
    else:
      # if all the NFs in the request are mapped already, then it is only 
      # an update on NF data.
      helper.log.warn("Updating only the status of NFs! Differences in other"
                      " attributes (resource, name, etc.) are ignored!")
      for nf in request.nfs:
        network.network.node[nf.id].status = nf.status

      # returning the substrate with the updated NF data
      return network

  # a delay value which is assumed to be infinity in terms of connection RTT
  # or latency requirement (set it to 100s = 100 000ms)
  overall_highest_delay = 100000

  # Rebind EdgeReqs to SAP-to-SAP paths, instead of BiSBiS ports
  # So EdgeReqs should either go between SAP-s, or InfraPorts which are 
  # connected to a SAP
  request = NFFGToolBox.rebind_e2e_req_links(request)

  chainlist = helper.retrieveE2EServiceChainsFromEdgeReqs(request)

  network = helper.substituteMissingValues(network)

  # create the class of the algorithm
  alg = CoreAlgorithm(network, request, chainlist, mode,
                      enable_shortest_path_cache, overall_highest_delay,
                      bw_factor=bw_factor, res_factor=res_factor,
                      lat_factor=lat_factor, shortest_paths=shortest_paths,
                      propagate_e2e_reqs=propagate_e2e_reqs)
  alg.setBacktrackParameters(bt_limit, bt_branching_factor)
  mappedNFFG = alg.start()

  if not mode == NFFG.MODE_DEL:
    # eliminate fake SGHops and their flowrules for SAP Alias handling.
    helper.processOutputSAPAlias(mappedNFFG)

  # replace Infinity values
  helper.purgeNFFGFromInfinityValues(mappedNFFG)
  # print mappedNFFG.dump()
  # The printed format is vnfs: (vnf_id, node_id) and links: MultiDiGraph, edge
  # data is the paths (with link ID-s) where the request links are mapped.
  if not mode == NFFG.MODE_DEL:
    helper.log.info("The VNF mappings are (vnf_id, node_id): \n%s" % pformat(
      alg.manager.vnf_mapping))
    helper.log.debug("The link mappings are: \n%s" % pformat(
      alg.manager.link_mapping.edges(data=True, keys=True)))

  if return_dist:
    return mappedNFFG, alg.preprocessor.shortest_paths
  else:
    return mappedNFFG


def _constructExampleRequest ():
  nffg = NFFG(id="BME-req-001")
  sap0 = nffg.add_sap(name="SAP0", id="sap0")
  sap1 = nffg.add_sap(name="SAP1", id="sap1")

  # add NF requirements.
  # Note: storage is used now for the first time, it comes in with the
  # NodeResource class
  # Note: internal latency is only forwarded to lower layer
  # Note: internal bw is untested yet, even before the NFFG support
  nf0 = nffg.add_nf(id="NF0", name="NetFunc0", func_type='A', cpu=2, mem=2,
                    storage=2, bandwidth=100)
  nf1 = nffg.add_nf(id="NF1", name="NetFunc1", func_type='B', cpu=1.5, mem=1.5,
                    storage=1.5, delay=50)
  nf2 = nffg.add_nf(id="NF2", name="NetFunc2", func_type='C', cpu=3, mem=3,
                    storage=3, bandwidth=500)
  nf3 = nffg.add_nf(id="NF3", name="NetFunc3", func_type='A', cpu=2, mem=2,
                    storage=2, bandwidth=100, delay=50)
  nf4 = nffg.add_nf(id="NF4", name="NetFunc4", func_type='C', cpu=0, mem=0,
                    storage=0, bandwidth=500)

  # directed SG links
  # flowclass default: None, meaning: match all traffic
  # some agreement on flowclass format is required.
  nffg.add_sglink(sap0.add_port(0), nf0.add_port(0))
  nffg.add_sglink(nf0.add_port(1), nf1.add_port(0), flowclass="HTTP")
  nffg.add_sglink(nf1.add_port(1), nf2.add_port(0), flowclass="HTTP")
  nffg.add_sglink(nf2.add_port(1), sap1.add_port(1))
  nffg.add_sglink(nf0.add_port(2), nf3.add_port(0), flowclass="non-HTTP")
  nffg.add_sglink(nf3.add_port(1), nf2.add_port(2), flowclass="non-HTTP")
  nffg.add_sglink(nf1.add_port(2), nf4.add_port(0), flowclass="index.com")
  nffg.add_sglink(nf4.add_port(1), nf2.add_port(3), flowclass="index.com")

  # add EdgeReqs
  nffg.add_req(sap0.ports[0], sap1.ports[1], delay=40, bandwidth=1500)
  nffg.add_req(nf1.ports[1], nf2.ports[0], delay=3.5)
  nffg.add_req(nf3.ports[1], nf2.ports[2], bandwidth=500)
  nffg.add_req(sap0.ports[0], nf0.ports[0], delay=3.0)
  # force collocation of NF0 and NF3
  # nffg.add_req(nf0.ports[2], nf3.ports[0], delay=1.0)
  # not SAP-to-SAP requests are not taken into account yet, these are ignored
  nffg.add_req(nf0.ports[1], nf2.ports[0], delay=1.0)

  # test Infra node removal from the request NFFG
  infra1 = nffg.add_infra(id="BiS-BiS1")
  infra2 = nffg.add_infra(id="BiS-BiS2")
  nffg.add_undirected_link(infra1.add_port(0), nf0.add_port(3), dynamic=True)
  nffg.add_undirected_link(infra1.add_port(1), nf0.add_port(4), dynamic=True)
  nffg.add_undirected_link(infra1.add_port(2), nf1.add_port(3), dynamic=True)
  nffg.add_undirected_link(infra2.add_port(0), nf2.add_port(4), dynamic=True)
  nffg.add_undirected_link(infra2.add_port(1), nf3.add_port(2), dynamic=True)
  nffg.add_undirected_link(infra1.add_port(3), infra2.add_port(2),
                           bandwidth=31241242)

  return nffg


def _onlySAPsRequest ():
  nffg = NFFG(id="BME-req-001")
  sap1 = nffg.add_sap(name="SAP1", id="sap1")
  sap2 = nffg.add_sap(name="SAP2", id="sap2")

  nffg.add_sglink(sap1.add_port(0), sap2.add_port(0))
  # nffg.add_sglink(sap1.add_port(1), sap2.add_port(1))

  nffg.add_req(sap1.ports[0], sap2.ports[0], bandwidth=1000, delay=24)
  nffg.add_req(sap1.ports[0], sap2.ports[0], bandwidth=1000, delay=24)

  return nffg


def _constructExampleNetwork ():
  nffg = NFFG(id="BME-net-001")
  uniformnoderes = {'cpu': 5, 'mem': 5, 'storage': 5, 'delay': 0.9,
                    'bandwidth': 5500}
  infra0 = nffg.add_infra(id="node0", name="INFRA0", **uniformnoderes)
  uniformnoderes['cpu'] = None
  infra1 = nffg.add_infra(id="node1", name="INFRA1", **uniformnoderes)
  uniformnoderes['mem'] = None
  infra2 = nffg.add_infra(id="node2", name="INFRA2", **uniformnoderes)
  uniformnoderes['storage'] = None
  switch = nffg.add_infra(id="sw0", name="FastSwitcher", delay=0.01,
                          bandwidth=10000)
  infra0.add_supported_type('A')
  infra1.add_supported_type(['B', 'C'])
  infra2.add_supported_type(['A', 'B', 'C'])
  sap0 = nffg.add_sap(name="SAP0", id="sap0innet")
  sap1 = nffg.add_sap(name="SAP1", id="sap1innet")

  unilinkres = {'delay': 1.5, 'bandwidth': 2000}
  # Infra links should be undirected, according to the currnet NFFG model
  # Infra link model is full duplex now.
  nffg.add_undirected_link(sap0.add_port(0), infra0.add_port(0), **unilinkres)
  nffg.add_undirected_link(sap1.add_port(0), infra1.add_port(0), **unilinkres)
  nffg.add_undirected_link(infra1.add_port(1), infra0.add_port(2), **unilinkres)
  unilinkres['bandwidth'] = None
  nffg.add_undirected_link(infra0.add_port(1), infra2.add_port(0), **unilinkres)
  nffg.add_undirected_link(infra1.add_port(2), infra2.add_port(1), **unilinkres)
  unilinkres['delay'] = 0.2
  unilinkres['bandwidth'] = 5000
  nffg.add_undirected_link(switch.add_port(0), infra0.add_port(3), **unilinkres)
  unilinkres['delay'] = None
  nffg.add_undirected_link(switch.add_port(1), infra1.add_port(3), **unilinkres)
  nffg.add_undirected_link(switch.add_port(2), infra2.add_port(2), **unilinkres)

  # test VNF mapping removal, and resource update in the substrate NFFG
  nf4 = nffg.add_nf(id="NF4inNet", name="NetFunc4", func_type='B', cpu=1, mem=1,
                    storage=1, bandwidth=100, delay=50)
  nffg.add_undirected_link(infra1.add_port(3), nf4.add_port(0), dynamic=True)
  nffg.add_undirected_link(infra1.add_port(4), nf4.add_port(1), dynamic=True)

  return nffg


def _example_request_for_fallback ():
  nffg = NFFG(id="FALLBACK-REQ", name="fallback-req")
  sap1 = nffg.add_sap(name="SAP1", id="sap1")
  sap2 = nffg.add_sap(name="SAP2", id="sap2")

  # add NF requirements.
  nf0 = nffg.add_nf(id="NF0", name="NetFunc0", func_type='B', cpu=2, mem=2,
                    storage=2, bandwidth=100)
  nf1 = nffg.add_nf(id="NF1", name="NetFunc1", func_type='A', cpu=1.5, mem=1.5,
                    storage=1.5, delay=50)
  nf2 = nffg.add_nf(id="NF2", name="NetFunc2", func_type='C', cpu=3, mem=3,
                    storage=3, bandwidth=500)
  nf3 = nffg.add_nf(id="NF3", name="NetFunc3", func_type='A', cpu=2, mem=2,
                    storage=2, bandwidth=100, delay=50)

  # add SG hops
  nffg.add_sglink(sap1.add_port(0), nf0.add_port(0), id="s1n0")
  nffg.add_sglink(nf0.add_port(1), nf1.add_port(0), id="n0n1")
  nffg.add_sglink(nf1.add_port(1), nf2.add_port(0), id="n1n2")
  nffg.add_sglink(nf1.add_port(2), nf3.add_port(0), id="n1n3")
  nffg.add_sglink(nf2.add_port(1), sap2.add_port(0), id="n2s2")
  nffg.add_sglink(nf3.add_port(1), sap2.add_port(1), id="n3s2")

  # add EdgeReqs
  # port number on SAP2 doesn`t count
  nffg.add_req(sap1.ports[0], sap2.ports[1], bandwidth=1000, delay=24)
  nffg.add_req(nf0.ports[1], nf1.ports[0], bandwidth=200)
  nffg.add_req(nf0.ports[1], nf1.ports[0], delay=3)

  # set placement criteria. Should be used to enforce the placement decision of
  # the upper orchestration layer. Placement criteria can contain multiple
  # InfraNode id-s, if the BiS-BiS is decomposed to multiple InfraNodes in this
  # layer.
  # setattr(nf1, 'placement_criteria', ['nc2'])

  return nffg


def _testNetworkForBacktrack ():
  nffg = NFFG(id="backtracktest", name="backtrack")
  sap1 = nffg.add_sap(name="SAP1", id="sap1")
  sap2 = nffg.add_sap(name="SAP2", id="sap2")

  uniformnoderes = {'cpu': 5, 'mem': 5, 'storage': 5, 'delay': 0.4,
                    'bandwidth': 5500}
  infra0 = nffg.add_infra(id="node0", name="INFRA0", **uniformnoderes)
  uniformnoderes2 = {'cpu': 9, 'mem': 9, 'storage': 9, 'delay': 0.4,
                     'bandwidth': 5500}
  infra1 = nffg.add_infra(id="node1", name="INFRA1", **uniformnoderes2)
  swres = {'cpu': 0, 'mem': 0, 'storage': 0, 'delay': 0.0,
           'bandwidth': 10000}
  sw = nffg.add_infra(id="sw", name="sw1", **swres)

  infra0.add_supported_type(['A'])
  infra1.add_supported_type(['A'])

  unilinkres = {'delay': 0.0, 'bandwidth': 2000}
  nffg.add_undirected_link(sap1.add_port(0), infra0.add_port(0),
                           **unilinkres)
  nffg.add_undirected_link(sap2.add_port(0), infra1.add_port(0),
                           **unilinkres)
  rightlink = {'delay': 10.0, 'bandwidth': 2000}
  leftlink = {'delay': 0.01, 'bandwidth': 5000}
  nffg.add_link(infra0.add_port(1), sw.add_port(0), id="n0sw", **rightlink)
  nffg.add_link(sw.add_port(1), infra1.add_port(1), id="swn1", **rightlink)
  nffg.add_link(sw.ports[0], infra0.ports[1], id="swn0", **leftlink)
  nffg.add_link(infra1.ports[1], sw.ports[1], id="n1sw", **leftlink)

  return nffg


def _testRequestForBacktrack ():
  nffg = NFFG(id="backtracktest-req", name="btreq")
  sap1 = nffg.add_sap(name="SAP1", id="sap1req")
  sap2 = nffg.add_sap(name="SAP2", id="sap2req")

  a = nffg.add_nf(id="a", name="NetFunc0", func_type='A', cpu=3, mem=3,
                  storage=3)
  b = nffg.add_nf(id="b", name="NetFunc1", func_type='A', cpu=3, mem=3,
                  storage=3)
  c = nffg.add_nf(id="c", name="NetFunc2", func_type='A', cpu=3, mem=3,
                  storage=3)

  nffg.add_sglink(sap1.add_port(0), a.add_port(0), id="sa")
  nffg.add_sglink(a.add_port(1), b.add_port(0), id="ab")
  nffg.add_sglink(b.add_port(1), c.add_port(0), id="bc")
  nffg.add_sglink(c.add_port(1), sap2.add_port(0), id="cs")

  nffg.add_req(a.ports[0], b.ports[1], delay=1.0, sg_path=["ab"])
  nffg.add_req(b.ports[0], c.ports[1], delay=1.0, sg_path=["bc"])
  nffg.add_req(c.ports[0], sap2.ports[0], delay=1.0, sg_path=["cs"])
  nffg.add_req(sap1.ports[0], sap2.ports[0], delay=50, bandwidth=10,
               sg_path=["sa", "ab", "bc", "cs"])

  return nffg


if __name__ == '__main__':
  try:
    argv = sys.argv[1:]
    if '-h' in argv or '--help' in argv:
      print "A single mapping can be run as \"python MappingAlgorithms.py " \
            "req.nffg net.nffg\" \nand the resulting NFFG is dumped to " \
            "console. " \
            "\nAll mapping algorithm parameters are default."
      sys.exit()
    with open(argv[0], "r") as f:
      req = NFFG.parse(f.read())
    with open(argv[1], "r") as g:
      net = NFFG.parse(g.read())
      # The following line must not be called if the input has already 
      # bidirectional links in the resource graph
      # net.duplicate_static_links()
    mapped = MAP(req, net, mode=req.mode)
    print mapped.dump()
  except uet.UnifyException as ue:
    print ue, ue.msg
    print traceback.format_exc()
