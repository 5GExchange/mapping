from abc import ABCMeta, abstractmethod


class AbstractWhenToOptimizeStrategy:
    __metaclass__ = ABCMeta

    global req_counter

    def __init__(self):
        super(AbstractWhenToOptimizeStrategy, self).__init__()


    @abstractmethod
    def optimize(self):
        pass





class ModelBased(AbstractWhenToOptimizeStrategy):
    def need_to_optimize(self):

        pass


class FixedReqCount(AbstractWhenToOptimizeStrategy):
    global req_counter

    def __init__(self):
        super(FixedReqCount, self).__init__()
        self.req_counter=0

    def need_to_optimize(self):
        req_counter += 1

        if req_counter%5 == 0:
            return True
        else:
            return False



class Fixedtime(AbstractWhenToOptimizeStrategy):
    def optimize(self):
        pass





class PeriodicalModelBased(AbstractWhenToOptimizeStrategy):
    def optimize(self):
        pass