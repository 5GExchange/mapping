import copy
from abc import ABCMeta, abstractmethod
import alg1.MappingAlgorithms as online_mapping
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
log.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s:%(message)s')
logging.basicConfig(filename='log_file.log', filemode='w', level=logging.DEBUG)
formatter = logging.Formatter('%(asctime)s |  Res sharing  | %(levelname)s | \t%(message)s')
hdlr = logging.FileHandler('../log_file.log')
hdlr.setFormatter(formatter)
log.addHandler(hdlr)
log.setLevel(logging.DEBUG)

class AbstractResourceSharingStrategy(object):
    __metaclass__ = ABCMeta

    def __init__(self, resource_grap):
      self.bare_resource_graph = resource_grap

    @abstractmethod
    def get_online_resource(self, res_online, res_offline):
        raise NotImplementedError("Abstract method")

    @abstractmethod
    def get_offline_resource(self, res_online, res_offline):
        raise NotImplementedError("Abstract method")


class DynamicMaxOnlineToAll(AbstractResourceSharingStrategy):

    def share_resource(self, resource_graph, res_online, res_offline):
        #TODO: dinamikus RG gen
        #return toOffline, toOnline
        pass


class DoubleHundred(AbstractResourceSharingStrategy):

    def get_offline_resource(self, res_online, res_offline):
        return copy.deepcopy(res_online)

    def get_online_resource(self, res_online, res_offline):
        # For first resource sharing
        #TODO: az if nem fut le sose mert a OrchAdap-ben van egy iylen:
        # self.concrete_hybrid_orchestrator.res_online = self.resource_graph
        if res_online == None:
            to_online = copy.deepcopy(self.bare_resource_graph)
            return to_online
        else:
            return res_online
