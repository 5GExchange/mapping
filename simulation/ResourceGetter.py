#Embedded file name: /home/dj/escape/mapping/simulation/ResourceGetter.py
from abc import ABCMeta, abstractmethod
try:
    from escape.mapping.alg1.misc import CarrierTopoBuilder
except ImportError:
    import sys, os
    nffg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../alg1/misc/'))
    sys.path.append(nffg_dir)
    import CarrierTopoBuilder

class AbstractResourceGetter:
    __metaclass__ = ABCMeta

    @abstractmethod
    def GetNFFG(self, which):
        pass


class ResouceGetter(AbstractResourceGetter):

    def GetNFFG(self, which):
        if which == 'pico':
            network = CarrierTopoBuilder.getPicoTopo()
            return network
        else:
            network = CarrierTopoBuilder.getSNDlib_dfn_gwin()
            return network
