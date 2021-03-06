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
Generates increasingly bigger/more Service Chain requirements for a 
network topology, reports how well the algorithm performed.
"""

import getopt
import logging
import math
import random
import sys
import traceback

import CarrierTopoBuilder
import MappingAlgorithms
import UnifyExceptionTypes as uet

from collections import OrderedDict

from nffg_lib.nffg import NFFG, NFFGToolBox

def gen_seq():
  while True:
    yield int(math.floor(random.random() * 999999999))

log = logging.getLogger("StressTest")
log.setLevel(logging.INFO)
logging.basicConfig(format='%(levelname)s:%(name)s:%(message)s')
# dictionary of newly added VNF-s keyed by the number of 'test_lvl' when it 
# was added.

helpmsg = """StressTest.py options are:
   -h                Print this message help message.
   -o                The output file where the result shall be printed.
   --loops           All Service Chains will be loops.
   --fullremap       Ignores all VNF mappings in the substrate network.
   --vnf_sharing=p   Sets the ratio of shared and not shared VNF-s.
   --request_seed=i  Provides seed for the random generator.

   --bw_factor=f     Controls the importance between bandwidth, infra resources
   --res_factor=f    and distance in latency during the mapping process. The
   --lat_factor=f    factors are advised to be summed to 3, if any is given the
                     others shall be given too!
   --bt_limit=i      Backtracking depth limit of the mapping algorithm (def.: 6).
   --bt_br_factor=i  Branching factor of the backtracking procedure of the 
                     mapping algorithm (default is 3).

   --multiple_scs           One request will contain at least 2 chains with vnf sharing
                            probability defined by "--vnf_sharing_same_sg" option.
   --vnf_sharing_same_sg=p  The conditional probablilty of sharing a VNF with the
                            current Service Graph, if we need to share a VNF 
                            determined by "--vnf_sharing"
   --max_sc_count=i         Determines how many chains should one request contain
                            at most.

   --batch_length=i  The number of Service Graphs, that should be batched and 
                     mapped together by the algorithm.
   --shareable_sg_count=i   The number of last 'i' Service Graphs which could
                            be used for sharing VNFs. Default value is unlimited.
   --sliding_share   If not set, the set of shareable SG-s is emptied after 
                     successfull batched mapping.
   --use_saps_once   If set, all SAPs can only be used once as SC origin and 
                     once as SC destination.
"""

def _shareVNFFromEarlierSG(nffg, running_nfs, nfs_this_sc, p):
  sumlen = sum([l*i for l,i in zip([len(running_nfs[n]) for n in running_nfs], 
                                   xrange(1,len(running_nfs)+1))])
  i = 0
  ratio = float(len(running_nfs.values()[i])) / sumlen
  while ratio < p:
    i += 1
    ratio += float((i+1)*len(running_nfs.values()[i])) / sumlen
  nf = random.choice(running_nfs.values()[i])
  if reduce(lambda a,b: a and b, [v in nfs_this_sc for v 
                                  in running_nfs.values()[i]]):
    # failing to add a VNF due to this criteria infuences the provided 
    # vnf_sharing_probabilty, but it is estimated to be insignificant, 
    # otherwise the generation can run into infinite loop!
    log.warn("All the VNF-s of the subchain selected for VNF sharing are"
             " already in the current chain under construction! Skipping"
             " VNF sharing...")
    return False, None
  else:
    while nf in nfs_this_sc:
      nf = random.choice(running_nfs.values()[i])
  if nf in nffg.nfs:
    return False, nf
  else:
    nffg.add_node(nf)
    return True, nf


def generateRequestForCarrierTopo(test_lvl, all_saps_beginning, 
                                  all_saps_ending,
                                  running_nfs, loops=False, 
                                  use_saps_once=True,
                                  vnf_sharing_probabilty=0.0,
                                  vnf_sharing_same_sg=0.0,
                                  shareable_sg_count=9999999999999999,
                                  multiSC=False, max_sc_count=2):
  """
  By default generates VNF-disjoint SC-s starting/ending only once in each SAP.
  With the 'loops' option, only loop SC-s are generated.
  'vnf_sharing_probabilty' determines the ratio of 
     #(VNF-s used by at least two SC-s)/#(not shared VNF-s).
  NOTE: some kind of periodicity is included to make the effect of batching 
  visible. But it is (and must be) independent of the batch_length.
  """
  chain_maxlen = 6
  sc_count=1
  # maximal possible bandwidth for chains
  max_bw = 7.0
  if multiSC:
    sc_count = random.randint(2,max_sc_count)
  while len(all_saps_ending) > sc_count and len(all_saps_beginning) > sc_count:
    nffg = NFFG(id="Benchmark-Req-"+str(test_lvl)+"-Piece")
    # newly added NF-s of one request
    current_nfs = []
    for scid in xrange(0,sc_count):
      # find two SAP-s for chain ends.
      nfs_this_sc = []
      sap1 = nffg.add_sap(id = all_saps_beginning.pop() if use_saps_once else \
                          random.choice(all_saps_beginning))
      sap2 = None
      if loops:
        sap2 = sap1
      else:
        tmpid = all_saps_ending.pop() if use_saps_once else \
                random.choice(all_saps_ending)
        while True:
          if tmpid != sap1.id:
            sap2 = nffg.add_sap(id = tmpid)
            break
          else:
            tmpid = all_saps_ending.pop() if use_saps_once else \
                    random.choice(all_saps_ending)
      sg_path = []
      sap1port = sap1.add_port()
      last_req_port = sap1port
      # generate some VNF-s connecting the two SAP-s
      vnf_cnt = next(gen_seq()) % chain_maxlen + 1
      for vnf in xrange(0, vnf_cnt):
        # in the first case p is used to determine which previous chain should 
        # be used to share the VNF, in the latter case it is used to determine
        # whether we should share now.
        vnf_added = False
        p = random.random()
        if random.random() < vnf_sharing_probabilty and len(running_nfs) > 0 \
           and not multiSC:
          vnf_added, nf = _shareVNFFromEarlierSG(nffg, running_nfs, nfs_this_sc,
                                                 p)
        elif multiSC and \
             p < vnf_sharing_probabilty and len(current_nfs) > 0 \
             and len(running_nfs) > 0:
          # this influences the the given VNF sharing probability...
          if reduce(lambda a,b: a and b, [v in nfs_this_sc for 
                                          v in current_nfs]):
            log.warn("All shareable VNF-s are already added to this chain! "
                     "Skipping VNF sharing...")
          elif random.random() < vnf_sharing_same_sg:
            nf = random.choice(current_nfs)
            while nf in nfs_this_sc:
              nf = random.choice(current_nfs)
            # the VNF is already in the subchain, we just need to add the links
            # vnf_added = True
          else:
            # this happens when VNF sharing is needed but not with the actual SG
            vnf_added, nf = _shareVNFFromEarlierSG(nffg, running_nfs, 
                                                   nfs_this_sc, p)
        else:
          nf = nffg.add_nf(id="-".join(("Test",str(test_lvl),"SC",str(scid),
                                        "VNF",str(vnf))),
                           func_type=random.choice(['A','B','C']), 
                           cpu=random.randint(1 + \
                                      (2*(test_lvl%4) if test_lvl%4 > 1 else 0),
                                              4 + \
                                      (3*(test_lvl%4) if test_lvl%4 > 1 else 0)),
                           mem=random.random()*1000 + \
                           (1000*(test_lvl%4) if test_lvl%4 > 1 else 0),
                           storage=random.random()*3 + \
                           (6*(test_lvl%4) if test_lvl%4 > 1 else 0),
                           delay=1 + random.random()*10,
                           bandwidth=random.random())
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
        # nfcnt = len([i for i in nffg.nfs])
        minlat = 40.0 - 10.0*(test_lvl%4)
        maxlat = 50.0 - 10.0*(test_lvl%4)
      nffg.add_req(sap1port, sap2port, delay=random.uniform(minlat,maxlat), 
                   bandwidth=random.random()*(max_bw + 2*(test_lvl%4)), 
                   sg_path = sg_path)
      log.info("Service Chain on NF-s added: %s"%[nf.id for nf in nfs_this_sc])
      # this prevents loops in the chains and makes new and old NF-s equally 
      # preferable in total for NF sharing
      new_nfs = [vnf for vnf in nfs_this_sc if vnf not in current_nfs]
      for tmp in xrange(0, scid+1):
        current_nfs.extend(new_nfs)
      if not multiSC:
        return nffg, all_saps_beginning, all_saps_ending
    if multiSC:
      return nffg, all_saps_beginning, all_saps_ending
  return None, all_saps_beginning, all_saps_ending

def StressTestCore(seed, loops, use_saps_once, vnf_sharing, multiple_scs, 
                   max_sc_count, vnf_sharing_same_sg, fullremap, 
                   batch_length, shareable_sg_count, sliding_share,
                   bw_factor, res_factor, lat_factor, bt_limit, bt_br_factor, 
                   outputfile, queue=None, shortest_paths_precalc=None, 
                   filehandler=None):
  """
  If queue is given, the result will be put in that Queue object too. Meanwhile
  if shortest_paths_precalc is not given, it means the caller needs the 
  shortest_paths, so we send it back. In this case the resulting test_lvl will
  be sent by the queue.
  NOTE: outputfile is only used inside the function if an exception is thrown 
  and than it is logged there.
  """
  total_vnf_count = 0
  mapped_vnf_count = 0
  network = CarrierTopoBuilder.getPicoTopo()
  max_test_lvl = 50000
  test_lvl = 1
  all_saps_ending = [s.id for s in network.saps]
  all_saps_beginning = [s.id for s in network.saps]
  running_nfs = OrderedDict() 
  random.seed(0)
  random.jumpahead(seed)
  random.shuffle(all_saps_beginning)
  random.shuffle(all_saps_ending)
  shortest_paths = shortest_paths_precalc
  ppid_pid = ""
  # log.addHandler(logging.StreamHandler())
  log.setLevel(logging.WARN)
  if filehandler is not None:
    log.addHandler(filehandler)
  if shortest_paths is not None and type(shortest_paths) != dict:
    excp = Exception("StressTest received something else other than shortest_"
                    "paths dictionary: %s"%type(shortest_paths))
    if queue is not None:
      queue.put(excp)
    raise excp
  if queue is not None:
    ppid_pid = "%s.%s:"%(os.getppid(), os.getpid())

  try:
    try:
      batch_count = 0
      batched_request = NFFG(id="Benchmark-Req-"+str(test_lvl))
      # built-in libs can change the state of random module during mapping.
      random_state = None
      while batched_request is not None:
        if test_lvl > max_test_lvl:
          break
        if (len(all_saps_ending) < batch_length or \
            len(all_saps_beginning) < batch_length) and use_saps_once:
          log.warn("Can't start batching because all SAPs should only be used"
                   " once for SC origin and destination and there are not "
                   "enough SAPs!")
          batched_request = None
        elif batch_count < batch_length:
          request, all_saps_beginning, all_saps_ending = \
                   generateRequestForCarrierTopo(test_lvl, all_saps_beginning, 
                                                 all_saps_ending, running_nfs,
                   loops=loops, use_saps_once=use_saps_once,
                   vnf_sharing_probabilty=vnf_sharing,
                   vnf_sharing_same_sg=vnf_sharing_same_sg,
                   multiSC=multiple_scs, max_sc_count=max_sc_count)
          if request is None:
            break
          else:
            batch_count += 1   
            running_nfs[test_lvl] = [nf for nf in request.nfs 
                                     if nf.id.split("-")[1] == str(test_lvl)]

            # using merge to create the union of the NFFG-s!
            batched_request = NFFGToolBox.merge_nffgs(batched_request, 
                                                      request)

            if len(running_nfs) > shareable_sg_count:
              # make the ordered dict function as FIFO
              running_nfs.popitem(last=False) 
            test_lvl += 1
            if not sliding_share and test_lvl % shareable_sg_count == 0:
              running_nfs = OrderedDict()
            log.debug("Batching Service Graph number %s..."%batch_count)
        else:
          batch_count = 0
          total_vnf_count += len([nf for nf in batched_request.nfs])
          random_state = random.getstate()
          network, shortest_paths = MappingAlgorithms.MAP(batched_request, network, 
                  full_remap=fullremap, enable_shortest_path_cache=True,
                  bw_factor=bw_factor, res_factor=res_factor,
                  lat_factor=lat_factor, shortest_paths=shortest_paths, 
                  return_dist=True,
                  bt_limit=bt_limit, bt_branching_factor=bt_br_factor)
          log.debug(ppid_pid+"Mapping successful on test level %s with batch"
                    " length %s!"%(test_lvl, batch_length))
          random.setstate(random_state)
          mapped_vnf_count += len([nf for nf in batched_request.nfs])
          batched_request = NFFG(id="Benchmark-Req-"+str(test_lvl))

    except uet.MappingException as me:
      log.info(ppid_pid+"Mapping failed: %s"%me.msg)
      if not me.backtrack_possible:
        # NOTE: peak SC count is only corret to add to test_lvl if SC-s are 
        # disjoint on VNFs.
        log.warn("Peak mapped VNF count is %s in the last run, test level: %s"%
                 (me.peak_mapped_vnf_count, 
                  test_lvl - batch_length + me.peak_sc_cnt))
        mapped_vnf_count += me.peak_mapped_vnf_count
        log.warn("All-time peak mapped VNF count: %s, All-time total VNF "
                 "count %s, Acceptance ratio: %s"%(mapped_vnf_count, 
                 total_vnf_count, float(mapped_vnf_count)/total_vnf_count))
      # break
    if request is None or batched_request is None:
      log.warn(ppid_pid+"Request generation reached its end!")
      # break
      
  except uet.UnifyException as ue:
    log.error(ppid_pid+ue.msg)
    log.error(ppid_pid+traceback.format_exc())
    with open(outputfile, "a") as f:
      f.write("\n".join(("UnifyException cought during StressTest: ",
                         ue.msg,traceback.format_exc())))
    if queue is not None:
      queue.put(str(ue.__class__))
      return test_lvl-1
  except Exception as e:
    log.error(ppid_pid+traceback.format_exc())
    with open(outputfile, "a") as f:
      f.write("\n".join(("Exception cought during StressTest: ",
                         traceback.format_exc())))
    if queue is not None:
      queue.put(str(e.__class__))
      return test_lvl-1
  # put the result to the queue
  if queue is not None:
    log.info(ppid_pid+"Putting %s to communication queue"%(test_lvl-1))
    queue.put(test_lvl-1)
    if shortest_paths_precalc is None:
      log.info(ppid_pid+"Returning shortest_paths!")
      return shortest_paths
  # if returned_test_lvl is 0, we failed at the very fist mapping!
  return test_lvl-1

def main(argv):
  try:
    opts, args = getopt.getopt(argv,"ho:",["loops", "fullremap", "bw_factor=",
                               "res_factor=", "lat_factor=", "request_seed=",
                               "vnf_sharing=", "multiple_scs", 
                               "vnf_sharing_same_sg=", "max_sc_count=",
                               "shareable_sg_count=", "batch_length=",
                               "bt_br_factor=", "bt_limit=",
                               "sliding_share", "use_saps_once"])
  except getopt.GetoptError:
    print helpmsg
    sys.exit()
  loops = False
  fullremap = False
  vnf_sharing = 0.0
  vnf_sharing_same_sg = 0.0
  seed = 3
  bw_factor = 1
  res_factor = 1
  lat_factor = 1
  outputfile = "paramsearch.out"
  multiple_scs = False
  sliding_share = False
  use_saps_once = False
  max_sc_count = 2
  shareable_sg_count = 99999999999999
  batch_length = 1
  bt_br_factor = 6
  bt_limit = 3
  for opt, arg in opts:
    if opt == '-h':
      print helpmsg
      sys.exit()
    elif opt == '-o':
      outputfile = arg
    elif opt == "--loops":
      loops = True
    elif opt == "--fullremap":
      fullremap = True
    elif opt == "--request_seed":
      seed = int(arg)
    elif opt == "--vnf_sharing":
      vnf_sharing = float(arg)
    elif opt == "--bw_factor":
      bw_factor = float(arg)
    elif opt == "--res_factor":
      res_factor = float(arg)
    elif opt == "--lat_factor":
      lat_factor = float(arg)
    elif opt == "--multiple_scs":
      multiple_scs = True
    elif opt == "--max_sc_count":
      max_sc_count = int(arg)
    elif opt == "--vnf_sharing_same_sg":
      vnf_sharing_same_sg = float(arg)
    elif opt == "--shareable_sg_count":
      shareable_sg_count = int(arg)
    elif opt == "--batch_length":
      batch_length = int(arg)
    elif opt == "--sliding_share":
      sliding_share = True
    elif opt == "--use_saps_once":
      use_saps_once = True
    elif opt == "--bt_limit":
      bt_limit = int(arg)
    elif opt == "--bt_br_factor":
      bt_br_factor = int(arg)
  params, args = zip(*opts)
  if "--bw_factor" not in params or "--res_factor" not in params or \
     "--lat_factor" not in params:
    print helpmsg
    raise Exception("Not all algorithm params are given!")
  
  returned_test_lvl = StressTestCore(seed, loops, use_saps_once, vnf_sharing,
           multiple_scs, max_sc_count, vnf_sharing_same_sg, fullremap, 
           batch_length, shareable_sg_count, sliding_share,
           bw_factor, res_factor, lat_factor, bt_limit, bt_br_factor, outputfile)
  
  log.info("First unsuccessful mapping was at %s test level."%
           (returned_test_lvl+1))
  if returned_test_lvl > 0:
    with open(outputfile, "a") as f:
      f.write("\nLast successful mapping was at %s test level.\n"%
              (returned_test_lvl))
  else:
    with open(outputfile, "a") as f:
      f.write("\nMapping failed at starting test level (%s)\n"%(returned_test_lvl+1))

if __name__ == '__main__':
  main(sys.argv[1:])
