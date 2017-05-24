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
    """
    Calculates the maximal resource utilization in every resource component,
    and sets all elements of the offline resource graph with this value.

    The online resource graph is with 100% resources.
        -- SHOULDN'T IT BE THE REMAINING FROM THE MAXRESOURCE?
    """
    # NOT READY YET !!!!!!!!!!

    def __init__(self, resource_grap, full_log_path):
        super(DynamicMaxOnlineToAll, self).__init__(resource_grap, full_log_path)

        self.link_bw_types = []
        self.max_avail_node_bw = 0.0
        self.max_avail_node_cpu = 0
        self.max_avail_node_mem = 0.0
        self.max_avail_node_storage = 0.0
        self.max_avail_link_bw = []
        self.max_avail_sw_bw = 0.0

    def set_rg_max_avail_node_and_link(self, rs):

        res_online = copy.deepcopy(rs)
        res_online.calculate_available_node_res()
        res_online.calculate_available_link_res([])

        for i in res_online.infras:
            if i.infra_type == 'EE':
                if i.resources.bandwidth - i.availres.bandwidth > self.max_avail_node_bw:
                    self.max_avail_node_bw = i.resources.bandwidth - i.availres.bandwidth

                if i.resources.cpu - i.availres.cpu > self.max_avail_node_cpu:
                    self.max_avail_node_cpu = i.resources.cpu - i.availres.cpu

                if i.resources.mem - i.availres.mem > self.max_avail_node_mem:
                    self.max_avail_node_mem = i.resources.mem - i.availres.mem

                if i.resources.storage - i.availres.storage > self.max_avail_node_storage:
                    self.max_avail_node_storage = i.resources.storage - i.availres.storage

            elif i.infra_type == 'SDN-SWITCH':
                if i.resources.bandwidth - i.availres.bandwidth > self.max_avail_sw_bw:
                    self.max_avail_sw_bw = i.resources.bandwidth - i.availres.bandwidth

            else:
                log.error("Invalid infra type!")
                raise

        #Calculate links
        for i, j, k, d in res_online.network.edges_iter(data=True, keys=True):
            if d.type == 'STATIC':
                if d.bandwidth not in self.link_bw_types:
                    self.link_bw_types.append(d.bandwidth)

        link = {}
        for i in self.link_bw_types:
            link[i] = 0
        for i, j, k, d in res_online.network.edges_iter(data=True, keys=True):
            if d.type == 'STATIC':
                if d.bandwidth - d.availbandwidth > link[d.bandwidth]:
                    link[d.bandwidth] = d.bandwidth - d.availbandwidth

        for i in self.link_bw_types:
            max_link = {'type':i,'used_bw':link[i]}
            self.max_avail_link_bw.append(max_link)

    def get_offline_resource(self, res_online, res_offline):
        self.set_rg_max_avail_node_and_link(res_online)
        to_offline = copy.deepcopy(self.bare_resource_graph)
        for i in to_offline.infras:
            new_resources = copy.deepcopy(i.resources)
            if i.infra_type == 'EE':
                new_resources.bandwidth = self.max_avail_node_bw
                new_resources.cpu = self.max_avail_node_cpu
                new_resources.mem = self.max_avail_node_mem
                new_resources.storage = self.max_avail_node_storage
                setattr(i, 'resource',new_resources)
            elif i.infra_type == 'SDN-SWITCH':
                new_resources.bandwidth = self.max_avail_sw_bw
                setattr(i, 'resource', new_resources)
            else:
                log.error("Invalid infra type!")
                raise
        for i, j, k, edge in to_offline.network.edges_iter(data=True, keys=True):
            for bw in self.max_avail_link_bw:
                if edge.bandwidth == bw['type']:
                    edge.bandwidth = bw['used_bw']
                    break
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