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

import getopt
import os
import sys
import threading

import numpy as np

helpmsg = """
Script to give start and give parameters to BatchTests.

   --stress_type=<<small>>           StressTest-*.py script to be
                           used.
   --seed_start=i          The starting seed for the test sequences
   --seed_end=i            The end seed for the test sequences
   -t                      If set, time is measured for each StressTest.
   --batch_length=f        The number of SG-s / time to wait to batch together.
   --bt_limit=i            Backtracking depth limit of mapping.
   --bt_br_factor=i        Branching factor of bactracking of mapping.
   --poisson               Make the StressTest run in poisson (not all of them 
                           supports it)

   --batch_length_end=f
   --batch_step=f

   --bt_limit_end=i

   --dump_nffgs=i         Dump every 'i'th NFFG of a test sequence.

   --topo_name=<<gwin|picotopo|gen>> Topology name to be used as Substrate
   Network, 'gen' uses the nffg network otpology generator.

   --gen_topo_size=<<begin,end,step>>  Starting and ending node count of the
   generated topo's size

   --gen_simultanious_incr    If set, the batch size and the generated
   topology size increases simultaniously. Gen_topo_size must be specified too!

   --single_test          Sets 'map_only_first_batch' to the StressTest-*.py
   --milp                 Use Mixed Integer Linear Programming instead of the
                          heuristic algorithm.
   --threads=i            Sets the maximal parallel thread count during testing.
"""

semaphore = None
sem_bt_batch = {}


class Test(threading.Thread):
  def __init__ (self, command, outputfile, i, bt, batch, gen_size):
    threading.Thread.__init__(self)
    self.command = command
    self.outputfile = outputfile
    self.i = i
    self.semkey = (bt, batch, gen_size)

  def run (self):
    semaphore.acquire()
    sem_bt_batch[self.semkey].acquire()

    with open(self.outputfile, "a") as f:
      f.write("\nCommand seed: %s\n" % self.i)
      f.write("Executing: %s\n" % self.command)

    os.system(self.command)

    with open(self.outputfile, "a") as f:
      f.write("\n============================================\n")

    sem_bt_batch[self.semkey].release()
    semaphore.release()


def main (argv):
  try:
    opts, args = getopt.getopt(argv, "ht", ["stress_type=", "seed_start=",
                                            "seed_end=", "batch_length=",
                                            "bt_limit=", "bt_br_factor=",
                                            "poisson", "batch_length_end=",
                                            "batch_step=", "bt_limit_end=",
                                            "dump_nffgs=", "topo_name=",
                                            "single_test", "milp", "threads=",
                                            "gen_simultanious_incr",
                                            "gen_topo_size="])
  except getopt.GetoptError as goe:
    print helpmsg
    raise
  stress_type = None
  seed_start = 0
  seed_end = 10
  time = False
  poisson = False
  batch_length = 1.0
  bt_limit = 6
  bt_br_factor = 3
  dump_nffgs = False
  dump_cnt = 1
  topo_name = "gwin"
  single_test = False
  milp = False
  max_thread_cnt = 4
  gen_simultanious_incr = False
  size_start = 35
  size_end = 35
  size_step = 5
  for opt, arg in opts:
    if opt == "-h":
      print helpmsg
      sys.exit()
    elif opt == "-t":
      time = True
    elif opt == "--stress_type":
      stress_type = arg
    elif opt == "--seed_start":
      seed_start = int(arg)
    elif opt == "--seed_end":
      seed_end = int(arg)
    elif opt == "--batch_length":
      batch_length = float(arg)
    elif opt == "--bt_limit":
      bt_limit = int(arg)
    elif opt == "--bt_br_factor":
      bt_br_factor = int(arg)
    elif opt == "--poisson":
      poisson = True
    elif opt == "--dump_nffgs":
      dump_nffgs = True
      dump_cnt = int(arg)
    elif opt == "--topo_name":
      topo_name = arg
    elif opt == "--single_test":
      single_test = True
    elif opt == "--milp":
      milp = True
    elif opt == "--threads":
      max_thread_cnt = int(arg)
    elif opt == "--gen_simultanious_incr":
      gen_simultanious_incr = True
      if "--gen_topo_size" not in zip(*opts)[0]:
        raise Exception(
          "If --gen_simultanious_incr is given, then --gen_topo_size must be "
          "given too!")
    elif opt == "--gen_topo_size":
      size_start, size_end, size_step = map(int, arg.split(','))

  batch_length_end = batch_length + 0.0000001
  batch_step = 1
  bt_limit_end = bt_limit + 1
  for opt, arg in opts:
    if opt == "--batch_step":
      batch_step = float(arg)
    elif opt == "--batch_length_end":
      batch_length_end = float(arg)
    elif opt == "--bt_limit_end":
      bt_limit_end = int(arg) + 1

  # batch_length_end += batch_step

  if stress_type is None:
    print "StressTest type must be given!"
    print helpmsg
    sys.exit()

  global semaphore
  semaphore = threading.Semaphore(max_thread_cnt)

  # ensures no files are written parallely by two or more processes
  for bt in xrange(bt_limit, bt_limit_end):
    for batch in np.arange(batch_length, batch_length_end, batch_step):
      for gen_size in xrange(size_start, size_end+size_step, size_step):
        sem_bt_batch[(bt, batch, gen_size)] = threading.Semaphore(1)

  for i in xrange(seed_start, seed_end):
    for bt in xrange(bt_limit, bt_limit_end):
      gen_size = size_start
      for batch in np.arange(batch_length, batch_length_end, batch_step):

        while gen_size <= size_end:

          outputfile = "batch_test_hybrid/" + (
            "milp-" if milp else "heur-") + topo_name + (
                       str(size_step) if gen_simultanious_incr else str(
                         gen_size)) + "-" + (
                         "poi-" if poisson else "") +\
                       "%s-%sbatched-seed%s-%s-bt%s-%s.out" \
                       % (stress_type, batch_step, seed_start, seed_end, bt,
                          bt_br_factor)
          commtime = "/usr/bin/time -o " + outputfile + " -a -f \"%U user," \
                                                        "\t%S sys,\t%E real\" "
          commbatch = "python StressTest-%s.py --bw_factor=1.0 " \
                      "--lat_factor=1.0 " \
                      "--res_factor=1.0 --shareable_sg_count=4 --topo_name=%s " \
                      "%s --batch_length=%s --bt_limit=%s --bt_br_factor=%s " \
                      "--gen_topo_params=sap_cnt:%s,n:%s,p:%s " \
                      "--request_seed=" % \
                      (stress_type, topo_name, (
                        "--dump_nffgs=" + str(dump_cnt) + ",nffgs-seed" + str(
                          i) + "-" + outputfile.rstrip(
                          ".out") if dump_nffgs else ""), batch, bt,
                       bt_br_factor, 33, gen_size, 0.45)

          if time:
            commbatch = commtime + commbatch

          command = commbatch + str(i) + (" --milp " if milp else "") + \
                    (" --map_only_first_batch " if single_test else "") + \
                    (" --poisson 2>> " if poisson else " 2>> ") + outputfile

          Test(command, outputfile, i, bt, batch, gen_size).start()

          if not gen_simultanious_incr:
            # if we want to increase the generation size step-by-step with
            # the current batching size, we iterate in this while cycle
            gen_size = size_end + size_step
          else:
            # in case of simultanious RG and SG size increasing we need to
            # break the loop after first execution and let the outer loop
            # increase the current generation size
            break

        if gen_simultanious_incr:
          gen_size += size_step


if __name__ == '__main__':
  main(sys.argv[1:])
