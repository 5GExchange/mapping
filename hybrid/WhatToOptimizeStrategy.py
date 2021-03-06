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

import copy
from abc import ABCMeta, abstractmethod
import logging
from datetime import datetime, timedelta
from hybrid.OptimizationDataHandler import *
from simulation.OrchestratorAdaptor import *
try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox
log = logging.getLogger(" WhatToOptStrat")

class AbstractWhatToOptimizeStrategy:
    __metaclass__ = ABCMeta

    def __init__(self, full_log_path, config_file_path, resource_type,
                 remaining_request_lifetimes):
        formatter = logging.Formatter(
            '%(asctime)s | WhatToOptStrat | %(levelname)s | \t%(message)s')
        hdlr = logging.FileHandler(full_log_path)
        hdlr.setFormatter(formatter)
        log.addHandler(hdlr)
        log.setLevel(logging.DEBUG)
        self.opt_data_handler = OptimizationDataHandler(full_log_path, config_file_path,
                                                        resource_type)
        self.remaining_request_lifetimes = remaining_request_lifetimes

    @abstractmethod
    def reqs_to_optimize(self, sum_req):
        # needs to return a copy of the to be optimized request graph (so
        # the HybridOrchestrator could handle sum_req independently of the offline optimization)!
        raise NotImplementedError("Abstract function!")


class ReqsSinceLastOpt(AbstractWhatToOptimizeStrategy):

    def __init__(self, full_log_path, config_file_path, resource_type,
                 remaining_request_lifetimes):
        super(ReqsSinceLastOpt, self).__init__(full_log_path, config_file_path,
                                               resource_type, remaining_request_lifetimes)
        self.optimized_reqs = None

    def reqs_to_optimize(self, sum_req):
        """
        Return SUM_reqs - optimized requests
        :param sum_req: 
        :return: 
        """
        try:
            if self.optimized_reqs is None:
                self.optimized_reqs = copy.deepcopy(sum_req)
                return copy.deepcopy(sum_req)
            else:
                need_to_optimize = copy.deepcopy(sum_req)

                for nf in self.optimized_reqs.nfs:
                    need_to_optimize.del_node(nf.id)
                for req in self.optimized_reqs.reqs:
                    need_to_optimize.del_edge(req.src.node.id,
                                                req.dst.node.id,
                                                id=req.id)
                for sap in self.optimized_reqs.saps:
                    if sap.id in need_to_optimize.network:
                        if need_to_optimize.network.out_degree(sap.id) + \
                                need_to_optimize.network.in_degree(sap.id) == 0:
                            need_to_optimize.del_node(sap.id)

                self.optimized_reqs = copy.deepcopy(sum_req)

                return need_to_optimize
        except Exception as e:
            log.error("reqs_to_optimize error" +
                      str(e.message) + str(e.__class__))
            raise


class AllReqsOpt(AbstractWhatToOptimizeStrategy):

    def __init__(self, full_log_path, config_file_path, resource_type,
                 remaining_request_lifetimes):
        super(AllReqsOpt, self).__init__(full_log_path, config_file_path,
                                         resource_type, remaining_request_lifetimes)

    def reqs_to_optimize(self, sum_req):
       return copy.deepcopy(sum_req)


class ReqsBasedOnLifetime (AbstractWhatToOptimizeStrategy):

    def __init__(self, full_log_path, config_file_path, resource_type,
                 remaining_request_lifetimes):
        super(ReqsBasedOnLifetime, self).__init__(full_log_path, config_file_path,
                                                  resource_type, remaining_request_lifetimes)

    def reqs_to_optimize(self, sum_req):
        opt_time = self.opt_data_handler.get_opt_time(len(self.remaining_request_lifetimes))
        need_to_optimize = copy.deepcopy(sum_req)

        for service in self.remaining_request_lifetimes:
            if service['dead_time'] < (datetime.now() + timedelta(seconds=opt_time)):
                for nf in service['SG'].nfs:
                    need_to_optimize.del_node(nf.id)
                for req in service['SG'].reqs:
                    need_to_optimize.del_edge(req.src.node.id,
                                                req.dst.node.id,
                                                id=req.id)
                for sap in service['SG'].saps:
                    if sap.id in need_to_optimize.network:
                        if need_to_optimize.network.out_degree(sap.id) + \
                                need_to_optimize.network.in_degree(sap.id) == 0:
                            need_to_optimize.del_node(sap.id)

        return copy.deepcopy(need_to_optimize)
