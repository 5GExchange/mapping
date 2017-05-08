# Copyright 2017 Balazs Nemeth
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

# Embedded file name: /home/dj/escape/mapping/simulation/ResourceGetter.py
import copy
import string
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

try:
    from generator import CarrierTopoBuilder
except ImportError:
    import site
    site.addsitedir('../generator')
    import CarrierTopoBuilder

class AbstractResourceGetter:
    __metaclass__ = ABCMeta

    @abstractmethod
    def GetNFFG(self):
        pass


class LoadedResourceGetter(AbstractResourceGetter):

    def __init__(self, log, resource_path):
        log.info("Reading loaded resource topology from file...")
        # WARNING: all IDs of SG components needs to be different from the
        # ID-s which will be used during the mapping! (it is a problem,
        # if a dumped NFFG is used from an earlier configuration)
        self.log = log
        self.loaded_resource_nffg = NFFG.parse_from_file(resource_path)
        self.log.info("Recreating SGhops based on flowrules in the loaded topology...")
        NFFGToolBox.recreate_all_sghops(self.loaded_resource_nffg)

    def getRunningSGs(self):
      """
      Retrieves the set of SGs which are mapped already.
      :return: list of NFFGs
      """
      running_sgs = []
      for req in self.loaded_resource_nffg.reqs:
        mapped_sg = NFFG()
        mapped_sg.add_sap(sap_obj=copy.deepcopy(req.src.node))
        if req.dst.node.id not in mapped_sg:
          mapped_sg.add_sap(sap_obj=copy.deepcopy(req.dst.node))

        for sg_hop_id in req.sg_path:
          # retrieve the SGHop objects
          for sghop in self.loaded_resource_nffg.sg_hops:
            if sghop.id == sg_hop_id:
              break
          else:
            raise Exception("SGHop with ID %s couldn't be found in loaded "
                            "resource topology!")
          # add both ends of an SG HOP
          if sghop.src.node.id not in mapped_sg:
            mapped_sg.add_nf(nf=copy.deepcopy(sghop.src.node))
          if sghop.dst.node.id not in mapped_sg:
            mapped_sg.add_nf(nf=copy.deepcopy(sghop.dst.node))

          # add the SGHop itself
          if not mapped_sg.network.has_edge(sghop.src.node.id,
                                            sghop.dst.node.id, key=sghop.id):
            mapped_sg.add_sglink(sghop.src, sghop.dst, hop=copy.deepcopy(sghop))

        # add the Edgereq Itself
        self.log.debug("Adding premapped SG to the system on path: %s"%req.sg_path)
        mapped_sg.add_req(req.src, req.dst, req=copy.deepcopy(req))
        running_sgs.append(mapped_sg)

      return running_sgs

    def GetNFFG(self):

        return self.loaded_resource_nffg


class PicoResourceGetter(AbstractResourceGetter):

    def GetNFFG(self):
        network = CarrierTopoBuilder.getPicoTopo()
        return network


class GwinResourceGetter(AbstractResourceGetter):

    def GetNFFG(self):
      network = CarrierTopoBuilder.getSNDlib_dfn_gwin(
                             "../generator/dfn-gwin.gml")
      return network


class CarrierTopoGetter(AbstractResourceGetter):

  def GetNFFG(self):
    """
    See parameter description in CarrierTopoBuilder module.
    :return:
    """
    topoparams = []
    topoparams.append({'Retail': (2, 3, 10), 'Business': (2, 2, 15),
                       'CloudNFV': (2, 2, 2, 16000, 100000,
                                    list(string.ascii_uppercase)[:10],
                                    [80, 120, 160], [32000, 64000], [150], 4000,
                                    4)})
    topoparams = 3 * topoparams
    return CarrierTopoBuilder.getCarrierTopo(topoparams, increment_port_ids=True)



if __name__ == "__main__":
  carrier = CarrierTopoGetter().GetNFFG()

  print "total: ", len(carrier)
  print "nfs: ", len([n for n in carrier.nfs])
  print "saps: ", len([n for n in carrier.saps])
  print "infras: ", len([n for n in carrier.infras])
  import networkx as nx
  carrier_gml = nx.MultiDiGraph()
  carrier_gml.add_nodes_from(carrier.network.nodes_iter())
  carrier_gml.add_edges_from(carrier.network.edges_iter())
  nx.write_gml(carrier_gml, "carrier"+str(len(carrier))+".gml")
