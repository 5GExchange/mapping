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
from abc import ABCMeta, abstractmethod
import math
import time
import random as rnd
import string
import random
from collections import OrderedDict

try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

class AbstractRequestGenerator:
    __metaclass__ = ABCMeta

    def __init__(self):
        pass

    @abstractmethod
    def get_request(self, resource_graph, test_lvl):
        pass

    def _shareVNFFromEarlierSG(self, nffg, running_nfs, nfs_this_sc, p):
        sumlen = sum([ l * i for l, i in zip([ len(running_nfs[n]) for n in running_nfs ], xrange(1, len(running_nfs) + 1)) ])
        i = 0
        ratio = float(len(running_nfs.values()[i])) / sumlen
        while ratio < p:
            i += 1
            ratio += float((i + 1) * len(running_nfs.values()[i])) / sumlen

        nf = rnd.choice(running_nfs.values()[i])
        if reduce(lambda a, b: a and b, [ v in nfs_this_sc for v in running_nfs.values()[i] ]):
            return (False, None)
        else:
            while nf in nfs_this_sc:
                nf = rnd.choice(running_nfs.values()[i])

            if nf in nffg.nfs:
                return (False, nf)
            nffg.add_node(nf)
            return (True, nf)


class TestReqGen(AbstractRequestGenerator):

    nf_types = ['A']

    def get_request(self, resource_graph, test_lvl):
        all_saps_ending = [s.id for s in resource_graph.saps]
        all_saps_beginning = [s.id for s in resource_graph.saps]
        running_nfs = OrderedDict()
        multiSC = False
        loops = False
        use_saps_once = True
        vnf_sharing_probabilty = 0.0
        vnf_sharing_same_sg = 0.0
        vnf_cnt = 4
        sc_count = 1

        while len(all_saps_ending) > sc_count and len(all_saps_beginning) > sc_count:
            nffg = NFFG(id='Benchmark-Req-' + str(test_lvl) + '-Piece')
            current_nfs = []
            for scid in xrange(0, sc_count):
                nfs_this_sc = []
                sap1 = nffg.add_sap(id=all_saps_beginning.pop() if use_saps_once else rnd.choice(all_saps_beginning))
                sap2 = None
                if loops:
                    sap2 = sap1
                else:
                    tmpid = all_saps_ending.pop() if use_saps_once else rnd.choice(all_saps_ending)
                    while True:
                        if tmpid != sap1.id:
                            sap2 = nffg.add_sap(id=tmpid)
                            break
                        else:
                            tmpid = all_saps_ending.pop() if use_saps_once else rnd.choice(all_saps_ending)

                sg_path = []
                sap1port = sap1.add_port()
                last_req_port = sap1port


                for vnf in xrange(0, vnf_cnt):
                    vnf_added = False
                    p = rnd.random()
                    if rnd.random() < vnf_sharing_probabilty and len(running_nfs) > 0 and not multiSC:
                        vnf_added, nf = self._shareVNFFromEarlierSG(nffg, running_nfs, nfs_this_sc, p)
                    else:
                        nf = nffg.add_nf(id='-'.join(('Test',
                        str(test_lvl),
                        'SC',
                        str(scid),
                        'VNF',
                        str(vnf))), func_type=rnd.choice(self.nf_types), cpu=2, mem=1600, storage=5)
                        vnf_added = True
                    if vnf_added:
                        nfs_this_sc.append(nf)
                        newport = nf.add_port()
                        sglink = nffg.add_sglink(last_req_port, newport)
                        sg_path.append(sglink.id)
                        last_req_port = nf.add_port()

                sap2port = sap2.add_port()
                sglink = nffg.add_sglink(last_req_port, sap2port)
                sg_path.append(sglink.id)
                nffg.add_req(sap1port, sap2port, delay=140.0, bandwidth=4.0, sg_path=sg_path)
                new_nfs = [ vnf for vnf in nfs_this_sc if vnf not in current_nfs ]
                for tmp in xrange(0, scid + 1):
                    current_nfs.extend(new_nfs)

                life_time = random.randint(5, 15)
                return nffg, life_time

class SimpleReqGen(AbstractRequestGenerator):

    nf_types = list(string.ascii_uppercase)[:10]

    def get_request(self,resource_graph, test_lvl):
        all_saps_ending = [s.id for s in resource_graph.saps]
        all_saps_beginning = [s.id for s in resource_graph.saps]
        running_nfs = OrderedDict()
        multiSC = False
        chain_maxlen = 8
        loops = False
        use_saps_once = True
        vnf_sharing_probabilty = 0.0
        vnf_sharing_same_sg = 0.0
        sc_count = 1
        max_bw = 7.0

        #time.sleep(1)

        while len(all_saps_ending) > sc_count and len(all_saps_beginning) > sc_count:
            nffg = NFFG(id='Benchmark-Req-' + str(test_lvl) + '-Piece')
            current_nfs = []
            for scid in xrange(0, sc_count):
                nfs_this_sc = []
                sap1 = nffg.add_sap(id=all_saps_beginning.pop() if use_saps_once else rnd.choice(all_saps_beginning))
                sap2 = None
                if loops:
                    sap2 = sap1
                else:
                    tmpid = all_saps_ending.pop() if use_saps_once else rnd.choice(all_saps_ending)
                    while True:
                        if tmpid != sap1.id:
                            sap2 = nffg.add_sap(id=tmpid)
                            break
                        else:
                            tmpid = all_saps_ending.pop() if use_saps_once else rnd.choice(all_saps_ending)

                sg_path = []
                sap1port = sap1.add_port()
                last_req_port = sap1port
                vnf_cnt = next(gen_seq()) % chain_maxlen + 1
                for vnf in xrange(0, vnf_cnt):
                    vnf_added = False
                    p = rnd.random()
                    if rnd.random() < vnf_sharing_probabilty and len(running_nfs) > 0 and not multiSC:
                        vnf_added, nf = self._shareVNFFromEarlierSG(nffg, running_nfs, nfs_this_sc,
                                                                                        p)
                    else:
                        nf = nffg.add_nf(id='-'.join(('Test', str(test_lvl), 'SC', str(scid), 'VNF',
                                                          str(vnf))), func_type=rnd.choice(self.nf_types),
                                             cpu=rnd.randint(1, 4), mem=rnd.random() * 1600, storage=rnd.random() * 3)
                        vnf_added = True
                    if vnf_added:
                        nfs_this_sc.append(nf)
                        newport = nf.add_port()
                        sglink = nffg.add_sglink(last_req_port, newport)
                        sg_path.append(sglink.id)
                        last_req_port = nf.add_port()

                sap2port = sap2.add_port()
                sglink = nffg.add_sglink(last_req_port, sap2port)
                sg_path.append(sglink.id)
                minlat = 60.0
                maxlat = 220.0
                nffg.add_req(sap1port, sap2port, delay=rnd.uniform(minlat, maxlat), bandwidth=rnd.random() * max_bw,
                                 sg_path=sg_path)
                new_nfs = [vnf for vnf in nfs_this_sc if vnf not in current_nfs]
                for tmp in xrange(0, scid + 1):
                    current_nfs.extend(new_nfs)
                life_time = random.randint(10, 50)
                return nffg, life_time

class MultiReqGen(AbstractRequestGenerator):
    nf_types = list(string.ascii_uppercase)[:10]

    def get_request(self,resource_graph, test_lvl):
        all_saps_ending = [s.id for s in resource_graph.saps]
        all_saps_beginning = [s.id for s in resource_graph.saps]
        running_nfs = OrderedDict()
        multiSC = True
        max_sc_count = 10
        chain_maxlen = 8
        loops = False
        use_saps_once = True
        vnf_sharing_probabilty = 0.0
        vnf_sharing_same_sg = 0.0
        sc_count = rnd.randint(2, max_sc_count)
        max_bw = 7.0

        while len(all_saps_ending) > sc_count and len(all_saps_beginning) > sc_count:
            nffg = NFFG(id='Benchmark-Req-' + str(test_lvl) + '-Piece')
            current_nfs = []
            for scid in xrange(0, sc_count):
                nfs_this_sc = []
                sap1 = nffg.add_sap(id=all_saps_beginning.pop() if use_saps_once else rnd.choice(all_saps_beginning))
                sap2 = None
                if loops:
                    sap2 = sap1
                else:
                    tmpid = all_saps_ending.pop() if use_saps_once else rnd.choice(all_saps_ending)
                    while True:
                        if tmpid != sap1.id:
                            sap2 = nffg.add_sap(id=tmpid)
                            break
                        else:
                            tmpid = all_saps_ending.pop() if use_saps_once else rnd.choice(all_saps_ending)

                sg_path = []
                sap1port = sap1.add_port()
                last_req_port = sap1port
                vnf_cnt = next(gen_seq()) % chain_maxlen + 1
                for vnf in xrange(0, vnf_cnt):
                    vnf_added = False
                    p = rnd.random()
                    if multiSC and p < vnf_sharing_probabilty and len(current_nfs) > 0 and len(running_nfs) > 0:
                        if reduce(lambda a, b: a and b, [v in nfs_this_sc for v in current_nfs]):
                            pass
                        elif rnd.random() < vnf_sharing_same_sg:
                            nf = rnd.choice(current_nfs)
                            while nf in nfs_this_sc:
                                nf = rnd.choice(current_nfs)
                        else:
                            vnf_added, nf = self._shareVNFFromEarlierSG(nffg, running_nfs,nfs_this_sc, p)
                    else:
                        nf = nffg.add_nf(id='-'.join(('Test', str(test_lvl), 'SC', str(scid), 'VNF',
                                                          str(vnf))), func_type=rnd.choice(self.nf_types),
                                             cpu=rnd.randint(1, 4), mem=rnd.random() * 1600, storage=rnd.random() * 3)
                        vnf_added = True
                    if vnf_added:
                        nfs_this_sc.append(nf)
                        newport = nf.add_port()
                        sglink = nffg.add_sglink(last_req_port, newport)
                        sg_path.append(sglink.id)
                        last_req_port = nf.add_port()

                sap2port = sap2.add_port()
                sglink = nffg.add_sglink(last_req_port, sap2port)
                sg_path.append(sglink.id)
                minlat = 5.0 * (len(nfs_this_sc) + 2)
                maxlat = 13.0 * (len(nfs_this_sc) + 2)
                nffg.add_req(sap1port, sap2port, delay=rnd.uniform(minlat, maxlat), bandwidth=rnd.random() * max_bw,
                                 sg_path=sg_path)
                new_nfs = [vnf for vnf in nfs_this_sc if vnf not in current_nfs]
                for tmp in xrange(0, scid + 1):
                    current_nfs.extend(new_nfs)
                life_time = random.randint(10, 50)
                return nffg, life_time




def gen_seq():
    while True:
        yield int(math.floor(rnd.random() * 999999999))
