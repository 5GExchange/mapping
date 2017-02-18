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
try:
    from escape.mapping.alg1 import MappingAlgorithms
except ImportError:
    import sys, os
    nffg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../alg1/'))
    sys.path.append(nffg_dir)
    import MappingAlgorithms

try:
    from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 "../nffg_lib/")))
    from nffg import NFFG, NFFGToolBox


class AbstractOrchestratorAdaptor:
    __metaclass__ = ABCMeta

    __resource_graph = None

    @abstractmethod
    def MAP(self, request):
        return

    @abstractmethod
    def del_service(self,request,resource):
        return

class OnlineOrchestrator(AbstractOrchestratorAdaptor):

    def __init__(self,resource):
        self.__resource_graph = resource

    def MAP(self, request):

        #Mik az alabbiak?
        #enable_shortest_path_cache
        #shortest paths

        #TODO: bw_factor, res_factor es lat_factor bekotese
        #TODO: fullremap parameter bekotese
        #TODO: bt_limit bekotese
        #TODO: bt_br_factor

        fullremap = False
        #mode = NFFG.MODE_REMAP if fullremap else NFFG.MODE_ADD
        mode = NFFG.MODE_ADD

        self.__resource_graph, shortest_paths = MappingAlgorithms.MAP(request,self.__resource_graph,
                                                        enable_shortest_path_cache=True,
                                                        bw_factor=1, res_factor=1,
                                                        lat_factor=1,
                                                        shortest_paths=None,
                                                        return_dist=True, mode=mode,
                                                        bt_limit=6,
                                                        bt_branching_factor=3)

    def del_service(self, request):

        #Mik az alabbiak?
        #enable_shortest_path_cache
        #shortest paths

        #TODO: bw_factor, res_factor es lat_factor bekotese
        #TODO: fullremap parameter bekotese
        #TODO: bt_limit bekotese
        #TODO: bt_br_factor

        mode = NFFG.MODE_DEL
        self.__resource_graph = MappingAlgorithms.MAP(request, self.__resource_graph,
                                        enable_shortest_path_cache=False,
                                        bw_factor=1, res_factor=1,
                                        lat_factor=1,
                                        shortest_paths=None,
                                        return_dist=False, mode=mode)

        asd = 0
