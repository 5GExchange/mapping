#Embedded file name: /home/dj/escape/mapping/simulation/ResourceGetter.py
from abc import ABCMeta, abstractmethod
try:
    from escape.mapping.alg1.misc import CarrierTopoBuilder
except ImportError:
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 "../alg1/misc/")))
    import CarrierTopoBuilder


class AbstractResourceGetter:
    __metaclass__ = ABCMeta

    @abstractmethod
    def GetNFFG(self):
        pass

class PicoResouceGetter(AbstractResourceGetter):

    def GetNFFG(self):
        network = CarrierTopoBuilder.getPicoTopo()
        return network

class GwinResouceGetter(AbstractResourceGetter):

    def GetNFFG(self):
        network = CarrierTopoBuilder.getSNDlib_dfn_gwin()
        return network
