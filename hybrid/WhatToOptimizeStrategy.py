from abc import ABCMeta, abstractmethod
from nffg import NFFG, NFFGToolBox

class AbstractWhatToOptimizeStrategy:
    __metaclass__ = ABCMeta

    @abstractmethod
    def reqs_to_optimize(self):



    def purge_to_be_expired_reqs(self):




class ReqsSinceLastOpt(AbstractWhatToOptimizeStrategy):
    def reqs_to_optimize(self):


class AllReqsOpt(AbstractWhatToOptimizeStrategy):
    def reqs_to_optimize(self):


