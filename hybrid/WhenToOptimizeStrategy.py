from abc import ABCMeta, abstractmethod


class AbstractWhenToOptimizeStrategy:
    __metaclass__ = ABCMeta


    def __init__(self):
        super(AbstractWhenToOptimizeStrategy, self).__init__()

    @abstractmethod
    def optimize(self, resource_to_optimize):
        pass





class ModelBased(AbstractWhenToOptimizeStrategy):
    def optimize(self, resource_to_optimize):

        pass


class FixedReqCount(AbstractWhenToOptimizeStrategy):
    def optimize(self, resource_to_optimize):
        pass



class Fixedtime(AbstractWhenToOptimizeStrategy):
    def optimize(self, resource_to_optimize):
        pass





class PeriodicalModelBased(AbstractWhenToOptimizeStrategy):
    def optimize(self, resource_to_optimize):
        pass