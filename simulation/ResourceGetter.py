from abc import ABCMeta, abstractmethod
from escape.mapping.alg1.misc.CarrierTopoBuilder import CarrierTopoBuilder

class AbstractResourceGetter:
    __metaclass__ = ABCMeta



class ResouceGetter(AbstractResourceGetter):


    def GetNFFG(self, which):

        if (which=='pico'):
            network = CarrierTopoBuilder.getPicoTopo()
            return network
        else:
            network = CarrierTopoBuilder.getSNDlib_dfn_gwin()
            return network
