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
log.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s:%(message)s')
logging.basicConfig(filename='log_file.log', filemode='w', level=logging.DEBUG)
formatter = logging.Formatter('%(asctime)s |  Res sharing  | %(levelname)s | \t%(message)s')
hdlr = logging.FileHandler('../log_file.log')
hdlr.setFormatter(formatter)
log.addHandler(hdlr)
log.setLevel(logging.DEBUG)

class AbstractResourceSharingStrategy:
    __metaclass__ = ABCMeta

    @abstractmethod
    def share_resource(self, resource_graph):
        pass



class DynamicMaxOnlineToAll(AbstractResourceSharingStrategy):
    def share_resource(self, resource_graph):
        #TODO: dinamikus RG gen
        #return toOffline, toOnline
        pass


class DoubleHundred(AbstractResourceSharingStrategy):

    def del_service(self, what_nffg, from_nffg):

        mode = NFFG.MODE_DEL
        self.__res_online = online_mapping.MAP(what_nffg, from_nffg,
                                                          enable_shortest_path_cache=True,
                                                          bw_factor=1,
                                                          res_factor=1,
                                                          lat_factor=1,
                                                          shortest_paths=None,
                                                          return_dist=False,
                                                          mode=mode)
        asd = 0

    def share_resource(self, resource_graph, res_online, res_offline):

        #For first resourve sharing
        if res_online is None:
            to_online = resource_graph.copy()
            to_offline = resource_graph.copy()

        else:
            #Create NFFG without mapped requests by offline
            tempNetwork = res_online.copy()
            #TODO: del_service ertelmesebb lenne NFFGToolBox()-bol
            #tempNetwork = NFFGToolBox().remove_required_services(tempNetwork, res_offline)
            #tempNetwork = self.del_service(res_offline,tempNetwork)
            #Try to merge online and offline results
            NFFGToolBox().merge_nffgs(tempNetwork, res_offline)
            #TODO: Kell ide az asd? Letezik meg a calculate_link_res BUG?
            asd = tempNetwork.copy()
            try:
                asd.calculate_available_node_res()
                asd.calculate_available_link_res()
                to_online = tempNetwork.copy()
                to_offline = resource_graph.copy()

            except:
                log.warning("Link merge FAILED ")
                to_online = res_online
                to_offline = resource_graph.copy()

        return to_offline, to_online
