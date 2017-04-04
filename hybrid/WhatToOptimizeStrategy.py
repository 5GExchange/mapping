import copy
from abc import ABCMeta, abstractmethod
import logging
import alg1.MappingAlgorithms as online_mapping
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

    def __init__(self, full_log_path):
        formatter = logging.Formatter(
            '%(asctime)s | WhatToOptStrat | %(levelname)s | \t%(message)s')
        hdlr = logging.FileHandler(full_log_path)
        hdlr.setFormatter(formatter)
        log.addHandler(hdlr)
        log.setLevel(logging.DEBUG)

    @abstractmethod
    def reqs_to_optimize(self, sum_req):
        # needs to return a copy of the to be optimized request graph (so
        # the HybridOrchestrator could handle sum_req independently of the offline optimization)!
        raise NotImplementedError("Abstract function!")

    def purge_to_be_expired_reqs(self):
        pass


class ReqsSinceLastOpt(AbstractWhatToOptimizeStrategy):

    def __init__(self, full_log_path):
        super(ReqsSinceLastOpt, self).__init__(full_log_path)
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
                    #nf.operation = NFFG.OP_DELETE
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

                self.optimized_reqs = need_to_optimize

                return copy.deepcopy(need_to_optimize)
        except Exception as e:
            log.error("reqs_to_optimize error" +
                      str(e.message) + str(e.__class__))
            raise


class AllReqsOpt(AbstractWhatToOptimizeStrategy):

    def reqs_to_optimize(self, sum_req):
       return copy.deepcopy(sum_req)
