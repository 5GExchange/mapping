import copy
from abc import ABCMeta, abstractmethod

class AbstractWhatToOptimizeStrategy:
    __metaclass__ = ABCMeta


    global last_optimalized
    @abstractmethod
    def reqs_to_optimize(self, sum_req):
        # needs to return a copy of the to be optimized request graph (so
        # the HybridOrchestrator could handle sum_req independently of the offline optimization)!
        raise NotImplementedError("Abstract function!")

    def purge_to_be_expired_reqs(self):
        pass


class ReqsSinceLastOpt(AbstractWhatToOptimizeStrategy):
    def reqs_to_optimize(self, sum_req):
        pass


class AllReqsOpt(AbstractWhatToOptimizeStrategy):

    def reqs_to_optimize(self, sum_req):
       return copy.deepcopy(sum_req)
