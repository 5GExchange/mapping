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

class PicoResourceGetter(AbstractResourceGetter):

    def GetNFFG(self):
        network = CarrierTopoBuilder.getPicoTopo()
        return network

class GwinResourceGetter(AbstractResourceGetter):

    def GetNFFG(self):
        network = CarrierTopoBuilder.getSNDlib_dfn_gwin()
        return network
