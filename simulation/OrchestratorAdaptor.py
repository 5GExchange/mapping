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
import os
import time
import copy
from configobj import ConfigObj
from abc import ABCMeta, abstractmethod

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

    def __init__(self, suffix):
      self.dump_suffix = suffix
      self.path = None

    def del_service(self, request, resource):
        for i in request.nfs:
            i.operation = NFFG.OP_DELETE
        for req in request.reqs:
          resource.del_edge(req.src.node.id, req.dst.node.id, id=req.id)
        return online_mapping.MAP(request, resource, mode=NFFG.MODE_DEL,
                                  keep_input_unchanged=True)

    @abstractmethod
    def MAP(self, request, resource):
        raise NotImplemented()

    def dump_mapped_nffg(self, calls, type, i, orchest_type, resource):

        dump_nffg = resource.dump()

        path = os.path.abspath('test' + str(i) + orchest_type)
        full_path = os.path.join(path, 'dump_nffg_' + str(calls) + "_"
                            + type + "_" + str(i) + "_" + str(time.ctime()).
                                replace(' ', '-').replace(':', '') + '.nffg')
        with io.FileIO(full_path, "w") as file:
                file.write(dump_nffg)


class OnlineOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self, deleted_services, full_log_path, config_file_path):
        super(OnlineOrchestratorAdaptor, self).__init__("online")
        self.config = ConfigObj(config_file_path)

    def MAP(self, request, resource):
        mode = NFFG.MODE_ADD
        return online_mapping.MAP(request, resource,
                                    bool(self.config['enable_shortest_path_cache']),
                                    float(self.config['bw_factor']),
                                    float(self.config['res_factor']),
                                    float(self.config['lat_factor']),
                                    None,
                                    bool(self.config['return_dist']),
                                    bool(self.config['propagate_e2e_reqs']),
                                    int(self.config['bt_limit']),
                                    int(self.config['bt_branching_factor']),
                                    mode=mode)


class HybridOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self, resource, deleted_services, full_log_path, config_file_path):
        super(HybridOrchestratorAdaptor, self).__init__("hybrid")
        self.concrete_hybrid_orchestrator = \
          hybrid_mapping.HybridOrchestrator(resource, config_file_path,
                                            deleted_services, full_log_path)

    def MAP(self, request, resource):
        return self.concrete_hybrid_orchestrator.MAP(request, resource)


class OfflineOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self, deleted_services, full_log_path,
                 config_file_path, optimize_already_mapped_nfs,
                 migration_handler_name, migration_coeff,
                 load_balance_coeff, edge_cost_coeff,
                 **migration_handler_kwargs):
        super(OfflineOrchestratorAdaptor, self).__init__("offline")
        self.optimize_already_mapped_nfs = optimize_already_mapped_nfs
        self.migration_handler_name = migration_handler_name
        self.migration_handler_kwargs = migration_handler_kwargs
        self.migration_coeff = float(migration_coeff)
        self.load_balance_coeff = float(load_balance_coeff)
        self.edge_cost_coeff = float(edge_cost_coeff)

    def MAP(self, request, resource):
        return offline_mapping.MAP(
            request, resource,
            optimize_already_mapped_nfs=self.optimize_already_mapped_nfs,
            migration_handler_name=self.migration_handler_name,
            migration_coeff=self.migration_coeff,
            load_balance_coeff=self.load_balance_coeff,
            edge_cost_coeff=self.edge_cost_coeff,
            **self.migration_handler_kwargs)
