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
    # NOT READY YET !!!!!!!!!!

    def __init__(self, resource_grap, full_log_path):
        super(DynamicMaxOnlineToAll, self).__init__(resource_grap, full_log_path)

        self.max_avail_node_bw = 0.0
        self.max_avail_node_cpu = 0
        self.max_avail_node_mem = 0.0
        self.max_avail_node_storage = 0.0
        self.max_avail_link_bw = 0.0
        self.max_avail_sw_bw = 0.0

    def set_rg_max_avail_node_and_link(self, rs):

        res_online = copy.deepcopy(rs)
        res_online.calculate_available_node_res()
        res_online.calculate_available_link_res([])

        for i in res_online.infras:
            if i.infra_type == 'EE':
                if i.availres.bandwidth > self.max_avail_node_bw:
                    self.max_avail_node_bw = i.availres.bandwidth

                if i.availres.cpu > self.max_avail_node_cpu:
                    self.max_avail_node_cpu = i.availres.cpu

                if i.availres.mem > self.max_avail_node_mem:
                    self.max_avail_node_mem = i.availres.mem

                if i.availres.storage > self.max_avail_node_storage:
                    self.max_avail_node_storage = i.availres.storage

            elif i.infra_type == 'SDN-SWITCH':
                if i.availres.bandwidth > self.max_avail_sw_bw:
                    self.max_avail_sw_bw = i.availres.bandwidth

            else:
                log.error("Invalid infra type!")
                raise

            for k in i.ports:
                for l in k.flowrules:
                    if l.bandwidth > self.max_avail_link_bw:
                            self.max_avail_link_bw = l.bandwidth

    def get_offline_resource(self, res_online, res_offline):
        self.set_rg_max_avail_node_and_link(res_online)
        to_offline = copy.deepcopy(self.bare_resource_graph)
        for i in to_offline.infras:
            if i.infra_type == 'EE':

                pass
        return copy.deepcopy(res_online)

    def get_online_resource(self, res_online, res_offline):
        return copy.deepcopy(res_online)


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