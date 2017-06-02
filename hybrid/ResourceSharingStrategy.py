# Copyright 2017 Balazs Nemeth, Mark Szalay, Janos Doka
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
    and sets all elements of the offline resource graph with this value as the
    available capacity.

    The online resource graph is with 100% resources.
        -- SHOULDN'T IT BE THE REMAINING FROM THE MAXRESOURCE?
    """
    # NOT READY YET !!!!!!!!!!

    def __init__(self, resource_grap, full_log_path):
        super(DynamicMaxOnlineToAll, self).__init__(resource_grap, full_log_path)

        self.link_bw_types = {}
        self.max_used_node_bw = 0.0
        self.max_used_node_cpu = 0
        self.max_used_node_mem = 0.0
        self.max_used_node_storage = 0.0
        self.max_used_sw_bw = 0.0

        self.float_uncertainty_addend = 1e-06

    def set_rg_max_avail_node_and_link(self, rs):

        res_online = copy.deepcopy(rs)
        res_online.calculate_available_node_res()
        res_online.calculate_available_link_res([])

        # TODO: Percentages should be set instead of absolute values!! (currently it may increase node resourse above the originally available!)
        for i in res_online.infras:
            if i.infra_type == 'EE':
                if i.resources.bandwidth - i.availres.bandwidth > self.max_used_node_bw:
                    self.max_used_node_bw = i.resources.bandwidth - i.availres.bandwidth

                if i.resources.cpu - i.availres.cpu > self.max_used_node_cpu:
                    self.max_used_node_cpu = i.resources.cpu - i.availres.cpu

                if i.resources.mem - i.availres.mem > self.max_used_node_mem:
                    self.max_used_node_mem = i.resources.mem - i.availres.mem

                if i.resources.storage - i.availres.storage > self.max_used_node_storage:
                    self.max_used_node_storage = i.resources.storage - i.availres.storage

            elif i.infra_type == 'SDN-SWITCH':
                if i.resources.bandwidth - i.availres.bandwidth > self.max_used_sw_bw:
                    self.max_used_sw_bw = i.resources.bandwidth - i.availres.bandwidth

            else:
                log.error("Invalid infra type!")
                raise

        self.max_used_node_bw += self.float_uncertainty_addend
        self.max_used_node_cpu += self.float_uncertainty_addend
        self.max_used_node_mem += self.float_uncertainty_addend
        self.max_used_node_storage += self.float_uncertainty_addend
        self.max_used_sw_bw += self.float_uncertainty_addend

        for tup in (
           ('cpu', self.max_used_node_cpu), ('node_bw', self.max_used_node_bw),
           ('mem', self.max_used_node_mem),
           ('storage', self.max_used_node_storage),
           ('sw_bw', self.max_used_sw_bw)):
            log.debug("Maximal used %s resource to set is %s" % tup)

        #Calculate links
        self.link_bw_types = {}
        for i, j, k, d in res_online.network.edges_iter(data=True, keys=True):
            if d.type == 'STATIC':
                if int(d.bandwidth) not in self.link_bw_types:
                    self.link_bw_types[int(d.bandwidth)] = 0.0

        for i, j, k, d in res_online.network.edges_iter(data=True, keys=True):
            if d.type == 'STATIC':
                if d.bandwidth - d.availbandwidth > self.link_bw_types[int(d.bandwidth)]:
                    self.link_bw_types[int(d.bandwidth)] = d.bandwidth - d.availbandwidth

        for i in self.link_bw_types:
            self.link_bw_types[i] += self.float_uncertainty_addend

        log.debug("Max used link bandwidths by link types: %s" %
                  self.link_bw_types)

    def get_offline_resource(self, res_online, res_offline):
        self.set_rg_max_avail_node_and_link(res_online)
        to_offline = copy.deepcopy(self.bare_resource_graph)
        for i in to_offline.infras:
            new_resources = copy.deepcopy(i.resources)
            if i.infra_type == 'EE':
                new_resources.bandwidth = self.max_used_node_bw
                new_resources.cpu = self.max_used_node_cpu
                new_resources.mem = self.max_used_node_mem
                new_resources.storage = self.max_used_node_storage
                i.resources = new_resources
            elif i.infra_type == 'SDN-SWITCH':
                new_resources.bandwidth = self.max_used_sw_bw
                i.resources = new_resources
            else:
                log.error("Invalid infra type!")
                raise
        for i, j, k, edge in to_offline.network.edges_iter(data=True, keys=True):
            edge.bandwidth = self.link_bw_types[int(edge.bandwidth)]
        # copy the actual NF mappings from res_online to the res_offline with
        # decreased maximal capacities.
        to_offline = NFFGToolBox.merge_nffgs(to_offline, res_online)
        try:
            to_offline.calculate_available_node_res()
            to_offline.calculate_available_link_res([])
        except RuntimeError as re:
            log.error("Offline resource would return invalid mapping after "
                      "copying the actual mapping state: %s"%re.message)
            raise
        return to_offline

    def get_online_resource(self, res_online, res_offline):
        return copy.deepcopy(res_online)


class DoubleHundred(AbstractResourceSharingStrategy):

    def get_offline_resource(self, res_online, res_offline):
        # clean the resource from any unnecessary objects
        to_offline = NFFGToolBox.strip_nfs_flowrules_sghops_ports(
            copy.deepcopy(res_online), log)
        to_offline = NFFGToolBox.merge_nffgs(to_offline, res_online)
        # the returned copy is independent of any other NFFG objects
        return to_offline

    def get_online_resource(self, res_online, res_offline):
        # For first resource sharing
        if self.called_for_first_time:
            to_online = copy.deepcopy(res_online)
            self.called_for_first_time = False
            return to_online
        else:
            return res_online