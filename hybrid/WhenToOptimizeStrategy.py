from abc import ABCMeta, abstractmethod


class AbstractWhenToOptimizeStrategy:
    __metaclass__ = ABCMeta


    def __init__(self):
        super(AbstractWhenToOptimizeStrategy, self).__init__()

    @abstractmethod
    def optimize(self, resource_to_optimize):






class ModelBased(AbstractWhenToOptimizeStrategy):
    def optimize(self, resource_to_optimize):




class FixedReqCount(AbstractWhenToOptimizeStrategy):
    def optimize(self, resource_to_optimize):





class Fixedtime(AbstractWhenToOptimizeStrategy):
    def optimize(self, resource_to_optimize):






class PeriodicalModelBased(AbstractWhenToOptimizeStrategy):
    def optimize(self, resource_to_optimize):