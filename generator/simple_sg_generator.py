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
Generates requests that which can be used as standard test SG-s to cover 
most/all functionalities of ESCAPE.
"""
from generator import NFFG
import random


def gen_8loop_tests (saps, vnfs, seed, add_req=True):
  """
  Generates simple request NFFGs in all combinations of sap1-->vnf1-->...-->
  vnfn-->sap1. With a loop requirement if add_req is set.

  :param saps: list of sap ID-s from the network
  :type saps: list
  :param vnfs: list of VNF **Types** which should be instantiated
  :type vnfs: list
  :param seed: seed for random generator
  :type seed: int
  :param add_req: If set EdgeReq objects are added
  :type add_req: bool
  :return: a generator over :any:`NFFG`
  :rtype: generator
  """
  random.seed(seed)
  for sap in saps:
    nffg = NFFG()
    sapo = nffg.add_sap(id=sap, name=sap+"_name")
    sapp = sapo.add_port()
    vnfs1 = random.sample(vnfs, random.randint(len(vnfs),len(vnfs)))
    vnfs2 = random.sample(vnfs, random.randint(len(vnfs),len(vnfs)))
    nfmiddle = nffg.add_nf(id="nf0", name="nf_middle", func_type=random.choice(vnfs1), 
                           cpu=1, mem=1, storage=1)
    vnfs1.remove(nfmiddle.functional_type)
    try:
      vnfs2.remove(nfmiddle.functional_type)
    except ValueError:
      pass
    i = 1
    once = True
    for vnf_list in (vnfs1, vnfs2):
      nf0 = nfmiddle
      for vnf in vnf_list:
        nf1 = nffg.add_nf(id="nf"+str(i), name="nf"+str(i)+"_"+vnf, func_type=vnf, 
                          cpu=1, mem=1, storage=1)
        nffg.add_sglink(src_port=nf0.add_port(), dst_port=nf1.add_port(), 
                        flowclass="HTTP", id=i)
        nf0 = nf1
        i+=1
      if once:
        nffg.add_sglink(src_port=nf0.add_port(), dst_port=nfmiddle.add_port(), 
                        flowclass="HTTP", id=i)
        once = False
      i+=1 
    nffg.add_sglink(src_port=nf1.add_port(), dst_port=sapp, 
                    flowclass="HTTP", id=i)
    nffg.add_sglink(src_port=sapp, dst_port=nfmiddle.add_port(), 
                    flowclass="HTTP", id=i+1)
    yield nffg

def gen_simple_oneloop_tests (saps, vnfs):
  """
  Generates simple request NFFGs in all combinations of sap1-->vnf1-->sap1.
  With a loop requirement

  :param saps: list of sap ID-s from the network
  :type saps: list
  :param vnfs: list of VNF **Types** which should be instantiated
  :type vnfs: list
  :return: a generator over :any:`NFFG`
  :rtype: generator
  """
  for sap in saps:
    for vnf in vnfs:
      nffg = NFFG()
      sapo = nffg.add_sap(id=sap, name=sap+"_name")
      nfo = nffg.add_nf(id="nf", name="nf_"+vnf, func_type=vnf,
                        cpu=1, mem=1, storage=1)
      sapp = sapo.add_port()
      nffg.add_sglink(src_port=sapp, dst_port=nfo.add_port(), 
                      flowclass="HTTP", id=1)
      nffg.add_sglink(src_port=nfo.add_port(), dst_port=sapp, 
                      flowclass="HTTP", id=2)

      nffg.add_req(src_port=sapp, dst_port=sapp, delay=50, bandwidth=1, 
                   sg_path=[1,2])
      yield nffg

if __name__ == '__main__':
  for nffg in gen_8loop_tests(saps=['SAP11'], 
              vnfs=['camtest:1.0', 'controller2:1.0', 
                    'controller1:1.0', 'javacontroller:1.0', 'mover:1.0', 'dal:1.0'], 
                              seed=4):
    print nffg.network.edges(keys=True)
    i = 600
    for sg in nffg.sg_hops:
      nffg.add_sglink(src_port=sg.dst, dst_port=sg.src, id=i, delay=sg.delay, 
                      bandwidth=sg.bandwidth)
      i+=1
    for sgprime in [sg for sg in nffg.sg_hops if sg.id < 600]:
      nffg.del_edge(src=sgprime.src, dst=sgprime.dst, id=sgprime.id)
    print nffg.dump()
  """
  for nffg in gen_simple_oneloop_tests (saps=['SAP1', 'SAP2', 'SAP3', 'SAP54'], 
              vnfs=['headerCompressor', 'headerDecompressor', 'simpleForwarder',
                    'splitter', 'nat', 'firewal', 'dpi', 'webserver', 
                    'balance_server', 'bridge']):
      print nffg.network.node
    
  """
