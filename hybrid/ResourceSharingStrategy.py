from abc import ABCMeta, abstractmethod


class AbstractResourceSharingStrategy:
    __metaclass__ = ABCMeta

    @abstractmethod
    def share_resource(self,resource_graph):
        pass



class DynamicMaxOnlineToAll(AbstractResourceSharingStrategy):
    def share_resource(self,resource_graph):
        #TODO: dinamikus RG generálás
        #return toOffline, toOnline
        pass


class DoubleHundred(AbstractResourceSharingStrategy):
    def share_resource(self,resource_graph):
        toOnline = resource_graph
        toOffline = resource_graph

        return toOffline, toOnline