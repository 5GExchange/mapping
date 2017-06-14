# Copyright 2017 Balazs Nemeth, Mark Szalay, Janos Doka
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

    def __init__(self, suffix, log):
      self.dump_suffix = suffix
      self.path = None
      self.log = log
      self.deleted_services = []

    def del_service(self, request, resource):
        for i in request.nfs:
            i.operation = NFFG.OP_DELETE
        for req in request.reqs:
          self.log.debug("Trying to delete EdgeReq %s on path %s"%(req, req.sg_path))
          resource.del_edge(req.src.node.id, req.dst.node.id, id=req.id)

        self.deleted_services.append(request)
        self.log.debug("Number of requests in the deleted_services list: %s"
                       % len(self.deleted_services))

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

    def __init__(self, full_log_path, config_file_path, log):
        super(OnlineOrchestratorAdaptor, self).__init__("online", log)
        self.config = ConfigObj(config_file_path)

    def MAP(self, request, resource):
        return online_mapping.MAP(request, resource,
                                    bw_factor=float(self.config['bw_factor']),
                                    res_factor=float(self.config['res_factor']),
                                    lat_factor=float(self.config['lat_factor']),
                                    return_dist=bool(self.config['return_dist']),
                                    propagate_e2e_reqs=bool(self.config['propagate_e2e_reqs']),
                                    bt_limit=int(self.config['bt_limit']),
                                    bt_branching_factor=int(self.config['bt_branching_factor']),
                                    mode=NFFG.MODE_ADD)


class HybridOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self, resource, full_log_path, config_file_path,
                 resource_type, remaining_request_lifetimes, log):
        super(HybridOrchestratorAdaptor, self).__init__("hybrid", log)
        self.concrete_hybrid_orchestrator = \
          hybrid_mapping.HybridOrchestrator(resource, config_file_path,
                                            full_log_path, resource_type,
                                            remaining_request_lifetimes)

    def MAP(self, request, resource):
        return self.concrete_hybrid_orchestrator.MAP(request, resource,
                                                     self.deleted_services)


class OfflineOrchestratorAdaptor(AbstractOrchestratorAdaptor):

    def __init__(self, full_log_path,
                 config_file_path, optimize_already_mapped_nfs,
                 migration_handler_name, migration_coeff,
                 load_balance_coeff, edge_cost_coeff, log,
                 **opt_params):
        super(OfflineOrchestratorAdaptor, self).__init__("offline", log)
        self.optimize_already_mapped_nfs = optimize_already_mapped_nfs
        self.migration_handler_name = migration_handler_name
        self.optional_params = opt_params
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
            edge_cost_coeff=self.edge_cost_coeff, logger=self.log,
            **self.optional_params)
