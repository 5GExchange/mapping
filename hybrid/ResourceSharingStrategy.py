import copy
from abc import ABCMeta, abstractmethod
try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

import logging
log = logging.getLogger(" Resource sharing")


class AbstractResourceSharingStrategy(object):
    __metaclass__ = ABCMeta

    def __init__(self, resource_grap, full_log_path):
        self.bare_resource_graph = resource_grap
        log.setLevel(logging.DEBUG)
        logging.basicConfig(format='%(levelname)s:%(message)s')
        logging.basicConfig(filename='log_file.log', filemode='w',
                      level=logging.DEBUG)
        formatter = logging.Formatter(
        '%(asctime)s |  Res sharing  | %(levelname)s | \t%(message)s')
        hdlr = logging.FileHandler(full_log_path)
        hdlr.setFormatter(formatter)
        log.addHandler(hdlr)
        log.setLevel(logging.DEBUG)
        # All strategies shall return a copy for the very first time it is
        # called (maybe other times too if it is necessary)
        self.called_for_first_time = True

    @abstractmethod
    def get_online_resource(self, res_online, res_offline):
        raise NotImplementedError("Abstract method")

    @abstractmethod
    def get_offline_resource(self, res_online, res_offline):
        raise NotImplementedError("Abstract method")


class DynamicMaxOnlineToAll(AbstractResourceSharingStrategy):
    # TODO: dinamikus RG gen

    def get_rg_max_node(self, rg):
        pass

    def get_rg_max_link(self, rg):
        pass

    def get_offline_resource(self, res_online, res_offline):
        max_node = self.get_rg_max_node(res_online)
        max_link = self.get_rg_max_link(res_online)

    def get_online_resource(self, res_online, res_offline):
        return res_online


class DoubleHundred(AbstractResourceSharingStrategy):

    def get_offline_resource(self, res_online, res_offline):
        return copy.deepcopy(res_online)

    def get_online_resource(self, res_online, res_offline):
        # For first resource sharing
        if self.called_for_first_time:
            to_online = copy.deepcopy(res_online)
            self.called_for_first_time = False
            return to_online
        else:
            return res_online