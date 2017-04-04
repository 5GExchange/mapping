from abc import ABCMeta, abstractmethod
import datetime
import logging
import time

log = logging.getLogger(" WhenToOpt ")


class AbstractWhenToOptimizeStrategy:
    __metaclass__ = ABCMeta

    def __init__(self, full_log_path):
        log.setLevel(logging.DEBUG)
        logging.basicConfig(format='%(levelname)s:%(message)s')
        logging.basicConfig(filename='log_file.log', filemode='w',
                            level=logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s |   WhenToOpt   | %(levelname)s | \t%(message)s')
        hdlr = logging.FileHandler(full_log_path)
        hdlr.setFormatter(formatter)
        log.addHandler(hdlr)
        log.setLevel(logging.DEBUG)

    @abstractmethod
    def need_to_optimize(self, offline_status, parameter):
        pass


class FixedReqCount(AbstractWhenToOptimizeStrategy):

    def __init__(self, full_log_path):
        super(FixedReqCount, self).__init__(full_log_path)
        self.call_counter = 0
        self.need_to_send_true = False

    def need_to_optimize(self, offline_status, parameter):
        """
        When call_counter is divisible by the parameter, then return True 
        as soon as the offline status becomes False.
        :param offline_status: bool
        :param parameter: optimization frequency in requests
        :return: 
        """
        self.call_counter += 1
        log.debug("FixedReqCounter param: " + str(parameter) +
                  "call_counter: " + str(self.call_counter))

        if self.call_counter % parameter == 0:
            self.need_to_send_true = True

        if self.need_to_send_true and not offline_status:
            log.debug("WhenToOpt: Need to optimize!")
            self.need_to_send_true = False
            return True
        else:
            log.debug("WhenToOpt: No need to optimize!")
            return False

class Always(AbstractWhenToOptimizeStrategy):

    def __init__(self, full_log_path):
        super(Always, self).__init__(full_log_path)

    def need_to_optimize(self, offline_status, parameter):
        """"
        Always return True if the offline status is False.

          :param offline_status: Offline running status. bool
          :param parameter: -
          :return: bool
          """
        if offline_status:
            log.debug("WhenToOpt: Offline still running ")
            return False
        else:
            log.debug("WhenToOpt: Need to optimize!")
            return True


class FixedTime(AbstractWhenToOptimizeStrategy):

    def __init__(self, full_log_path):
        super(FixedTime, self).__init__(full_log_path)
        self.start_time = time.time()

    def need_to_optimize(self, offline_status, parameter):
        """
        Calculate elapsed time and if it is greater than the parameter,
        than return True.

        :param offline_status: Offline running status. bool
        :param parameter: optimization frequency in seconds
        :return: bool
        """
        elapsed_time = time.time() - self.start_time
        if (elapsed_time > parameter) and not offline_status:
            self.start_time = time.time()
            log.debug("WhenToOpt: Need to optimize!")
            return True
        else:
            log.debug("WhenToOpt: No need to optimize!")
            return False


class PeriodicalModelBased(AbstractWhenToOptimizeStrategy):

    def need_to_optimize(self, offline_status, parameter):
        pass


class ModelBased(AbstractWhenToOptimizeStrategy):
    def need_to_optimize(self, offline_status, parameter):
        pass