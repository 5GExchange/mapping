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
import os
import sys
import threading
import time
import subprocess
import logging

from configobj import ConfigObj

semaphore_logging = threading.Semaphore(1)
log = logging.getLogger()
logging.basicConfig(format='%(levelname)s:%(name)s:%(message)s',
                    level=logging.DEBUG)

class Simulation(threading.Thread):

  def __init__ (self, config, saving_folder, semaphore):
    threading.Thread.__init__(self)
    self.config = config
    self.semaphore = semaphore
    base_filename = config['simulation_number'] + config['orchestrator']
    self.config.filename = saving_folder + "/" + base_filename + ".cfg"
    os.system("touch %s"%self.config.filename)
    self.config.write()
    self.command = "nohup python MappingSimulationFrameWork.py %s/%s 2> %s/%s > " \
                   "/dev/null" % (saving_folder, base_filename+".cfg", saving_folder,
                                  base_filename + ".err")

  def run (self):
    semaphore_logging.acquire()
    # cleaning up if there were a folder with this name earlier.
    os.system("rm -rf test"+config['simulation_number']+config['orchestrator'])
    self.semaphore.acquire()
    log.info("\nSimulation started at: %s" % subprocess.check_output("date").\
             rstrip('\n'))
    log.info("Running simulation: %s" % self.command)
    semaphore_logging.release()
    os.system(self.command)
    self.semaphore.release()


if __name__ == '__main__':
  argv = sys.argv[1:]

  if "--help" in argv or "-h" in argv:
    print "Usage: python simulation_parameter_sweeper.py <<path_to_cfg_file>> " \
          "parallel=<<number of simultaneous simulations>> " \
          "folder=<<folder of .cfg and .err files to be saved to>> " \
          "simulation_number=<<comma separated sequence of simulation identifiers>> " \
          "<<parametername_of_configparam1>>=<<value1>>,<<value2>>,... " \
          "<<parametername_of_configparam2>>=*,<<value2>>,... \n" \
          "Awalys the same number of coma separated arguments should be given " \
          "to each configparam, if a value from the original cfg file shall be " \
          "used, use * instead of <<valueX>>.\n " \
          "Use: python simulation_parameter_sweeper.py   parallel= folder= " \
          "simulation_number= \n"
    sys.exit()

  default_config = ConfigObj(argv[0])
  parallel_simulations = int(argv[1].split("=")[1])
  folder = argv[2].split("=")[1]

  semaphore = threading.Semaphore(parallel_simulations)

  config_params = argv[3:]
  if config_params[0].split("=")[0] != "simulation_number":
    raise Exception("simulation_number config parameter must be the first one!")
  sweep = {}
  prev_value_cnt = None
  for config_param in config_params:
    name, values = config_param.split("=", 1)
    sweep[name] = values.split(",")
    value_cnt = len(sweep[name])
    if prev_value_cnt is not None:
      if prev_value_cnt != value_cnt:
        raise Exception("Not same number of values are given for every config "
                        "parameter!")
    prev_value_cnt = value_cnt

  log.info("Received parameter value sweep is %s \n"%sweep)

  for _ in xrange(0,prev_value_cnt):
    config = copy.deepcopy(default_config)
    for k, v in sweep.iteritems():
      if v[0] != "*":
        config[k] = v[0]
      sweep[k] = v[1:]
    Simulation(config, folder, semaphore).start()
    time.sleep(2)
