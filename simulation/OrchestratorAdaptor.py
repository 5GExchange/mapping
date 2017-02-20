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
import logging
import os
import io
import time

log = logging.getLogger(" Orchestrator ")
log.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s:%(message)s')
logging.basicConfig(filename='log_file.log', filemode='w', level=logging.DEBUG)
formatter = logging.Formatter('%(asctime)s | Orchestrator | %(levelname)s |  \t%(message)s')
hdlr = logging.FileHandler('../log_file.log')
hdlr.setFormatter(formatter)
log.addHandler(hdlr)
log.setLevel(logging.DEBUG)
try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

import alg1.MappingAlgorithms as online_mapping
import hybrid.HybridOrchestrator as hybrid_mapping

class AbstractOrchestratorAdaptor:
    __metaclass__ = ABCMeta

    __resource_graph = None

    @abstractmethod
    def MAP(self, request):
        return

    @abstractmethod
    def del_service(self, request):
        return

    @abstractmethod
    def dump_mapped_nffg(self, calls, type):
        return

class OnlineOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self,resource):
        self.__resource_graph = resource

    def MAP(self, request):

        mode = NFFG.MODE_ADD
        self.__resource_graph, shortest_paths = online_mapping.MAP(request,self.__resource_graph,
                                                        enable_shortest_path_cache=True,
                                                        bw_factor=1, res_factor=1,
                                                        lat_factor=1,
                                                        shortest_paths=None,
                                                        return_dist=True, mode=mode,
                                                        bt_limit=6,
                                                        bt_branching_factor=3)

    def del_service(self, request):

        #TODO: bw_factor, res_factor es lat_factor bekotese
        #TODO: fullremap parameter bekotese
        #TODO: bt_limit bekotese
        #TODO: bt_br_factor

        mode = NFFG.MODE_DEL
        self.__resource_graph = online_mapping.MAP(request, self.__resource_graph,
                                        enable_shortest_path_cache=False,
                                        bw_factor=1, res_factor=1,
                                        lat_factor=1,
                                        shortest_paths=None,
                                        return_dist=False, mode=mode)

    def dump_mapped_nffg2(self, calls, type):
        dump_nffg = self.__resource_graph.dump()

        path = os.path.abspath('.')
        """"
        #ez vmiert nem akar mukodni :( igazabol sehova mashova nem enged irni csak a simulation mappaba
        full_path = os.path.join(path, '/results/dump_nffg_' + str(calls) + "_" + type +
                                 "_" + str(time.ctime()) + "online")
        """

        full_path = os.path.join(path, 'dump_nffg_' + str(calls) + "_" + type +
                                 "_" + str(time.ctime()) + "_online")

        with io.FileIO(full_path, "w") as file:
            file.write(dump_nffg)

        """try:
            f = open('dump_nffg', 'a')
            f.write("\n#######################################################################################\n"
                "-------------------------------Dump after the " + str(calls) + ". " + type + "-------------------------------\n"
                    "#######################################################################################\n" )
            f.write(dump_nffg)
            f.close()
        except:
            log.error("Dump_mapped_nffg file does not exist ")
        """

    def dump_mapped_nffg(self, calls, type):
        dump_nffg = self.__resource_graph.dump()

        #
        i = 1


        if not os.path.exists('test' + str(i) + "_online"):
            os.mkdir('test' + str(i) + "_online")
            path = os.path.abspath('test' + str(i) + "_online")
            print path
            full_path = os.path.join(path, 'dump_nffg_' + str(calls) + "_" + type +
                                "_" + str(time.ctime()) + "_online")
            with io.FileIO(full_path, "w") as file:
                file.write(dump_nffg)
        else:
            path = os.path.abspath('test' + str(i) + "_online")
            print path
            full_path = os.path.join(path,
                                     'dump_nffg_' + str(calls) + "_" + type +
                                     "_" + str(time.ctime()) + "_online")
            with io.FileIO(full_path, "w") as file:
                file.write(dump_nffg)


class HybridOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    concrete_hybrid_orchestrator = None

    def __init__(self, resource,what_to_opt_strat, when_to_opt_strat, resource_share_strat):
        self.concrete_hybrid_orchestrator = hybrid_mapping.HybridOrchestrator(resource, what_to_opt_strat, when_to_opt_strat, resource_share_strat)

    def MAP(self, request):

        mode = NFFG.MODE_ADD
        self.concrete_hybrid_orchestrator.MAP(request, self.concrete_hybrid_orchestrator)

    def del_service(self, request):
        pass

    def dump_mapped_nffg(self, calls, type):
        pass