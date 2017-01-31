from abc import ABCMeta, abstractmethod
import getopt
import logging
import math
import random as rnd
import sys
import traceback
import string
import os
try:
  from escape.escape.escape.nffg_lib.nffg import NFFG
except ImportError:
  import sys, os
  sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                  "../nffg_lib/")))
  from nffg import NFFG

class AbstractRequestGenerator:
    __metaclass__ = ABCMeta



    def __init__(self):
        pass

    @abstractmethod
    def get_request(self, test_lvl, all_saps_beginning,
                                          all_saps_ending,
                                          running_nfs, loops=False,
                                          use_saps_once=True,
                                          vnf_sharing_probabilty=0.0,
                                          vnf_sharing_same_sg=0.0,
                                          shareable_sg_count=9999999999999999,
                                          multiSC=False, max_sc_count=2):
        pass


    def _shareVNFFromEarlierSG(self, nffg, running_nfs, nfs_this_sc, p):
        sumlen = sum([l * i for l, i in zip([len(running_nfs[n]) for n in running_nfs],
                                                xrange(1, len(running_nfs) + 1))])
        i = 0
        ratio = float(len(running_nfs.values()[i])) / sumlen
        while ratio < p:
                i += 1
                ratio += float((i + 1) * len(running_nfs.values()[i])) / sumlen
        nf = rnd.choice(running_nfs.values()[i])
        if reduce(lambda a, b: a and b, [v in nfs_this_sc for v
                                             in running_nfs.values()[i]]):
                # failing to add a VNF due to this criteria infuences the provided
                # vnf_sharing_probabilty, but it is estimated to be insignificant,
                # otherwise the generation can run into infinite loop!
            #log.warn("All the VNF-s of the subchain selected for VNF sharing are"
              #           " already in the current chain under construction! Skipping"
              #           " VNF sharing...")
            return False, None
        else:
            while nf in nfs_this_sc:
                nf = rnd.choice(running_nfs.values()[i])
        if nf in nffg.nfs:
            return False, nf
        else:
            nffg.add_node(nf)
            return True, nf





class RequestGenerator(AbstractRequestGenerator):

    nf_types = list(string.ascii_uppercase)[:10]


    def get_request(self, test_lvl, all_saps_beginning,
                                          all_saps_ending,
                                          running_nfs, loops=False,
                                          use_saps_once=True,
                                          vnf_sharing_probabilty=0.0,
                                          vnf_sharing_same_sg=0.0,
                                          shareable_sg_count=9999999999999999,
                                          multiSC=False, max_sc_count=2, simple_sc=False):

            """
            By default generates VNF-disjoint SC-s starting/ending only once in each SAP.
            With the 'loops' option, only loop SC-s are generated.
            'vnf_sharing_probabilty' determines the ratio of
               #(VNF-s used by at least two SC-s)/#(not shared VNF-s).
            NOTE: some kind of periodicity is included to make the effect of batching
            visible. But it is (and must be) independent of the batch_length.target = cls._copy_node_type(new.infras, target, log)

            WARNING!! batch_length meaining is changed if --poisson is set!

            Generate exponential arrival time for VNF-s to make Batching more reasonable.
            inter arrival time is Exp(1) so if we are batching for 4 time units, the
            expected SG count is 4, because the sum of 4 Exp(1) is Exp(4).
            BUT we wait for 1 SG at least, but if by that time 4 units has already passed,
            map the SG alone (unbatched).
            """

            if simple_sc:
                chain_maxlen = 4
            else:
                chain_maxlen = 8
            sc_count = 1
            # maximal possible bandwidth for chains
            max_bw = 7.0
            if multiSC:
                if simple_sc:
                    sc_count = 4
                else:
                    sc_count = rnd.randint(2, max_sc_count)
            while len(all_saps_ending) > sc_count and len(all_saps_beginning) > sc_count:
                nffg = NFFG(id="Benchmark-Req-" + str(test_lvl) + "-Piece")
                # newly added NF-s of one request
                current_nfs = []
                for scid in xrange(0, sc_count):
                    # find two SAP-s for chain ends.
                    nfs_this_sc = []
                    sap1 = nffg.add_sap(id=all_saps_beginning.pop() if use_saps_once else \
                        rnd.choice(all_saps_beginning))
                    sap2 = None
                    if loops:
                        sap2 = sap1
                    else:
                        tmpid = all_saps_ending.pop() if use_saps_once else \
                            rnd.choice(all_saps_ending)
                        while True:
                            if tmpid != sap1.id:
                                sap2 = nffg.add_sap(id=tmpid)
                                break
                            else:
                                tmpid = all_saps_ending.pop() if use_saps_once else \
                                    rnd.choice(all_saps_ending)
                    sg_path = []
                    sap1port = sap1.add_port()
                    last_req_port = sap1port
                    # generate some VNF-s connecting the two SAP-s
                    if simple_sc:
                        vnf_cnt = chain_maxlen
                    else:
                        vnf_cnt = next(gen_seq()) % chain_maxlen + 1
                    for vnf in xrange(0, vnf_cnt):
                        # in the first case p is used to determine which previous chain should
                        # be used to share the VNF, in the latter case it is used to determine
                        # whether we should share now.
                        vnf_added = False
                        p = rnd.random()
                        if rnd.random() < vnf_sharing_probabilty and len(running_nfs) > 0 \
                                and not multiSC:
                            vnf_added, nf = AbstractRequestGenerator._shareVNFFromEarlierSG(nffg, running_nfs, nfs_this_sc,
                                                                   p)
                        elif multiSC and \
                                        p < vnf_sharing_probabilty and len(current_nfs) > 0 \
                                and len(running_nfs) > 0:
                            # this influences the the given VNF sharing probability...
                            if reduce(lambda a, b: a and b, [v in nfs_this_sc for
                                                             v in current_nfs]):
                                pass
                                #log.warn("All shareable VNF-s are already added to this chain! "
                                         #"Skipping VNF sharing...")
                            elif rnd.random() < vnf_sharing_same_sg:
                                nf = rnd.choice(current_nfs)
                                while nf in nfs_this_sc:
                                    nf = rnd.choice(current_nfs)
                                    # the VNF is already in the subchain, we just need to add the links
                                    # vnf_added = True
                            else:
                                # this happens when VNF sharing is needed but not with the actual SG
                                vnf_added, nf = AbstractRequestGenerator._shareVNFFromEarlierSG(nffg, running_nfs,
                                                                       nfs_this_sc, p)
                        else:
                            if simple_sc:
                                nf = nffg.add_nf(id="-".join(("Test", str(test_lvl), "SC", str(scid), "VNF", str(vnf))),
                                                 func_type=rnd.choice(self.nf_types),
                                                 cpu=2,
                                                 mem=1600,
                                                 storage=5)
                            else:
                                nf = nffg.add_nf(id="-".join(("Test", str(test_lvl), "SC", str(scid), "VNF", str(vnf))),
                                                 func_type=rnd.choice(self.nf_types),
                                                 cpu=rnd.randint(1, 4),
                                                 mem=rnd.random() * 1600,
                                                 storage=rnd.random() * 3)
                            vnf_added = True
                        if vnf_added:
                            # add olny the newly added VNF-s, not the shared ones.
                            nfs_this_sc.append(nf)
                            newport = nf.add_port()
                            sglink = nffg.add_sglink(last_req_port, newport)
                            sg_path.append(sglink.id)
                            last_req_port = nf.add_port()

                    sap2port = sap2.add_port()
                    sglink = nffg.add_sglink(last_req_port, sap2port)
                    sg_path.append(sglink.id)

                    # WARNING: this is completly a wild guess! Failing due to this doesn't
                    # necessarily mean algorithm failure
                    # Bandwidth maximal random value should be min(SAP1acces_bw, SAP2access_bw)
                    # MAYBE: each SAP can only be once in the reqgraph? - this is the case now.
                    if multiSC:
                        minlat = 5.0 * (len(nfs_this_sc) + 2)
                        maxlat = 13.0 * (len(nfs_this_sc) + 2)
                    else:
                        if simple_sc == False:
                            # nfcnt = len([i for i in nffg.nfs])
                            minlat = 60.0
                            maxlat = 220.0
                            nffg.add_req(sap1port, sap2port, delay=rnd.uniform(minlat, maxlat),
                                         bandwidth=rnd.random() * max_bw,
                                         sg_path=sg_path)
                        else:
                            nffg.add_req(sap1port, sap2port, delay=140.0,
                                         bandwidth=4.0,
                                         sg_path=sg_path)
                    #log.info("Service Chain Request on NF-s added: %s" % [nf.id for nf in nfs_this_sc])
                    #writeToFile(outputfile, "Service Chain Request on NF-s added: %s" % [nf.id for nf in nfs_this_sc])
                    # this prevents loops in the chains and makes new and old NF-s equally
                    # preferable in total for NF sharing
                    new_nfs = [vnf for vnf in nfs_this_sc if vnf not in current_nfs]
                    for tmp in xrange(0, scid + 1):
                        current_nfs.extend(new_nfs)
                    if not multiSC:
                        return nffg #, all_saps_beginning, all_saps_ending
                if multiSC:
                    return nffg #, all_saps_beginning, all_saps_ending
            return None #, all_saps_beginning, all_saps_ending

def gen_seq():
    while True:
        yield int(math.floor(rnd.random() * 999999999))