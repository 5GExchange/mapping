from abc import ABCMeta, abstractmethod


class AbstractWhenToOptimizeStrategy:
    __metaclass__ = ABCMeta

    global req_counter

    #def __init__(self):
    #   super(AbstractWhenToOptimizeStrategy, self).__init__()

    @abstractmethod
    def need_to_optimize(self):
        pass

class ModelBased(AbstractWhenToOptimizeStrategy):
    def need_to_optimize(self):

        pass


class FixedReqCount(AbstractWhenToOptimizeStrategy):

    req_counter = 0

    def need_to_optimize(self,offline_status):
        self.req_counter += 1

        if offline_status and self.req_counter%5 == 0:
            self.req_counter -= 1
            return False

        elif offline_status:
            return False

        elif not offline_status and self.req_counter%5 == 0:
            return True

        else:
            return False


class Allways(AbstractWhenToOptimizeStrategy):
    global req_counter

    def __init__(self):
        #super(FixedReqCount, self).__init__()
        self.req_counter=0

    def need_to_optimize(self,offline_status):

        if offline_status:
            return False
        else:
            return True



class Fixedtime(AbstractWhenToOptimizeStrategy):
    def optimize(self):
        pass





class PeriodicalModelBased(AbstractWhenToOptimizeStrategy):
    def optimize(self):
        pass