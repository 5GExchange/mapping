from abc import ABCMeta, abstractmethod
from nffg import NFFG, NFFGToolBox

class AbstractWhatToOptimizeStrategy:
    __metaclass__ = ABCMeta


    global last_optimalized
    @abstractmethod
    def reqs_to_optimize(self):
        pass


    def purge_to_be_expired_reqs(self):
        pass



class ReqsSinceLastOpt(AbstractWhatToOptimizeStrategy):
    def reqs_to_optimize(self):

        #S
        pass

class AllReqsOpt(AbstractWhatToOptimizeStrategy):
    def reqs_to_optimize(self):
        SUM_request = NFFG()
        last_optimalized = SUM_request

        batched_request = NFFG()
        while batched_request is not None:
            NFFGToolBox.merge_nffgs(SUM_request, batched_request)

        return SUM_request
