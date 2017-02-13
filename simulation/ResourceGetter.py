#Embedded file name: /home/dj/escape/mapping/simulation/ResourceGetter.py
from abc import ABCMeta, abstractmethod
# try:
#     from escape.mapping.alg1.misc import CarrierTopoBuilder
# except ImportError:
#     import sys, os
#     sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
#                                                  "../alg1/misc/")))
#     import CarrierTopoBuilder

try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

from generator import CarrierTopoBuilder


class AbstractResourceGetter:
    __metaclass__ = ABCMeta

    @abstractmethod
    def GetNFFG(self):
        pass

class PicoResourceGetter(AbstractResourceGetter):

    def GetNFFG(self):
        network = CarrierTopoBuilder.getPicoTopo()
        return network

class GwinResourceGetter(AbstractResourceGetter):

    def GetNFFG(self):
      network = CarrierTopoBuilder.getSNDlib_dfn_gwin(
        "../generator/dfn-gwin.gml")
      return network
