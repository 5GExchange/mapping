from abc import ABCMeta, abstractmethod
from nffg import NFFG, NFFGToolBox

class AbstractWhatToOptimizeStrategy:
    __metaclass__ = ABCMeta


    global last_optimalized
    @abstractmethod
    def reqs_to_optimize(self, sum_req):
        pass

    def purge_to_be_expired_reqs(self):
        pass


class ReqsSinceLastOpt(AbstractWhatToOptimizeStrategy):
    def reqs_to_optimize(self, sum_req):

        #S
        pass

class AllReqsOpt(AbstractWhatToOptimizeStrategy):
    def reqs_to_optimize(self, sum_req):
       return sum_req
