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
import io
import logging
import os
import time
from abc import ABCMeta, abstractmethod

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
import milp.milp_solution_in_nffg as offline_mapping

class AbstractOrchestratorAdaptor(object):
    __metaclass__ = ABCMeta

    def __init__(self, resource):
      self.__resource_graph = resource


    def del_service(self, request):
        mode = NFFG.MODE_DEL
        self.__resource_graph = online_mapping.MAP(request,
                                        self.__resource_graph,
                                        enable_shortest_path_cache=False,
                                        bw_factor=1, res_factor=1,
                                        lat_factor=1,
                                        shortest_paths=None,
                                        return_dist=False, mode=mode)

    @abstractmethod
    def MAP(self, request):
        return

    @abstractmethod
    def dump_mapped_nffg(self, calls, type, sim_number, orchest_type):

        dump_nffg = self.__resource_graph.dump()

        i = sim_number
        if not os.path.exists('test' + str(i) + orchest_type):
            os.mkdir('test' + str(i) + orchest_type)
            path = os.path.abspath('test' + str(i) + orchest_type)
            full_path = os.path.join(path, 'dump_nffg_' + str(calls) + "_"
                                + type + "_" + str(i) + "_" + str(time.ctime()))
            with io.FileIO(full_path, "w") as file:
                file.write(dump_nffg)
        else:
            path = os.path.abspath('test' + str(i) + orchest_type)
            full_path = os.path.join(path, 'dump_nffg_' + str(calls) + "_"
                                + type + "_" + str(i) + "_" + str(time.ctime()))
            with io.FileIO(full_path, "w") as file:
                file.write(dump_nffg)


class OnlineOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self, resource):
        super(OnlineOrchestratorAdaptor, self).__init__(resource)
        self.dump_suffix = "online"

    def MAP(self, request):
        mode = NFFG.MODE_ADD
        """""
        self.__resource_graph, shortest_paths = \
            online_mapping.MAP(request, self.__resource_graph,
                                            enable_shortest_path_cache=True,
                                            bw_factor=1, res_factor=1,
                                            lat_factor=1,
                                            shortest_paths=None,
                                            return_dist=True, mode=mode,
                                            bt_limit=6,
                                            bt_branching_factor=3)
        """
        print self.__dict__
        self.__resource_graph = online_mapping.MAP(request, self.__resource_graph,
                                             enable_shortest_path_cache=True,
                                             bw_factor=1, res_factor=1,
                                             lat_factor=1,
                                             shortest_paths=None,
                                             return_dist=False, mode=mode,
                                             bt_limit=6,
                                             bt_branching_factor=3)

class HybridOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self, resource):
        super(HybridOrchestratorAdaptor, self).__init__(resource)
        self.concrete_hybrid_orchestrator = \
            hybrid_mapping.HybridOrchestrator(resource, "./simulation.cfg")
        self.dump_suffix = "hybrid"

    def MAP(self, request):
        mode = NFFG.MODE_ADD
        self.concrete_hybrid_orchestrator.MAP(
            request, self.concrete_hybrid_orchestrator)

    def dump_mapped_nffg(self, calls, type, sim_number, orchest_type):

        dump_nffg = self.concrete_hybrid_orchestrator.res_online.dump()

        i = sim_number
        if not os.path.exists('test' + str(i) + orchest_type):
            os.mkdir('test' + str(i) + orchest_type)
            path = os.path.abspath('test' + str(i) + orchest_type)
            full_path = os.path.join(path, 'dump_nffg_' + str(calls) + "_"
                                + type + "_" + str(time.ctime()))
            with io.FileIO(full_path, "w") as file:
                file.write(dump_nffg)
        else:
            path = os.path.abspath('test' + str(i) + orchest_type)
            full_path = os.path.join(path, 'dump_nffg_' + str(calls) + "_"
                                + type + "_"  + str(time.ctime()))
            with io.FileIO(full_path, "w") as file:
                file.write(dump_nffg)

class OfflineOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self, resource, optimize_already_mapped_nfs,
                 migration_handler_name, migration_coeff,
                 load_balance_coeff, edge_cost_coeff,
                 **migration_handler_kwargs):
        super(OfflineOrchestratorAdaptor, self).__init__(resource)
        self.__resource_graph = resource
        self.optimize_already_mapped_nfs = optimize_already_mapped_nfs
        self.migration_handler_name = migration_handler_name
        self.migration_handler_kwargs = migration_handler_kwargs
        print migration_coeff
        self.migration_coeff = float(migration_coeff)
        self.load_balance_coeff = float(load_balance_coeff)
        self.edge_cost_coeff = float(edge_cost_coeff)
        self.dump_suffix = "offline"

    def MAP (self, request):
      print "# of VNFs: ", len([n for n in request.nfs])
      self.__resource_graph = offline_mapping.MAP(
        request, self.__resource_graph,
        optimize_already_mapped_nfs=self.optimize_already_mapped_nfs,
        migration_handler_name=self.migration_handler_name,
        migration_coeff=self.migration_coeff,
        load_balance_coeff=self.load_balance_coeff,
        edge_cost_coeff=self.edge_cost_coeff,
        **self.migration_handler_kwargs)
