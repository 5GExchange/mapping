from abc import ABCMeta, abstractmethod


class AbstractResourceSharingStrategy:
    __metaclass__ = ABCMeta

    @abstractmethod
    def share_resource(self):




class DynamicMaxOnlineToAll(AbstractResourceSharingStrategy):
    def share_resource(self):


class DoubleHundred(AbstractResourceSharingStrategy):
    def share_resource(self):
