from abc import ABCMeta, abstractmethod
import time
import logging

log = logging.getLogger(" WhenToOpt ")
log.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s:%(message)s')
logging.basicConfig(filename='log_file.log', filemode='w', level=logging.DEBUG)
formatter = logging.Formatter('%(asctime)s |   WhenToOpt   | %(levelname)s | \t%(message)s')
hdlr = logging.FileHandler('../log_file.log')
hdlr.setFormatter(formatter)
log.addHandler(hdlr)
log.setLevel(logging.DEBUG)

class AbstractWhenToOptimizeStrategy:
    __metaclass__ = ABCMeta

    @abstractmethod
    def need_to_optimize(self, offline_status, parameter):
        pass


class FixedReqCount(AbstractWhenToOptimizeStrategy):

    req_counter = 0

    def need_to_optimize(self, offline_status, parameter):
        self.req_counter += 1
        if self.req_counter % parameter == 0:
            return True
        else:
            return False


class Allways(AbstractWhenToOptimizeStrategy):

    def need_to_optimize(self, offline_status, parameter):
        if offline_status:
            log.info(" Offline still running ")
            return False
        else:
            return True


class Fixedtime(AbstractWhenToOptimizeStrategy):

    start_time = None

    def __init__(self):
        self.start_time = time.time()

    def need_to_optimize(self, offline_status, parameter):
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= parameter:
            self.start_time = time.time()
            return True
        else:
            return False


class PeriodicalModelBased(AbstractWhenToOptimizeStrategy):
    def need_to_optimize(self, offline_status, parameter):
        pass


class ModelBased(AbstractWhenToOptimizeStrategy):
    def need_to_optimize(self, offline_status, parameter):
        pass