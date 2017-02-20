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
from exceptions import Exception


class UnifyException(Exception):
  """
  Base class for all exceptions raised during the mapping process.
  """

  def __init__ (self, msg0):
    """Messages shall be constructed when raising the exception
    according to the actual circumstances."""
    self.msg = msg0


class InternalAlgorithmException(UnifyException):
  """
  Raised when the algorithm fails due to implementation error
  or conceptual error.
  """
  pass


class BadInputException(UnifyException):
  """
  Raised when the algorithm receives bad formatted, or unexpected input.
  Parameters shall be strings.
  """

  def __init__ (self, expected, given):
    self.msg = "The algorithm expected an input: %s, but the given input is: " \
               "%s" % (expected, given)


class MappingException(UnifyException):
  """
  Raised when a mapping could not be found for the request given from the
  upper layer. Not enough resources, no path found.

  :param peak_vnf_cnt: the peak number of VNFs mapped at the same time
  :type peak_vnf_cnt: int
  :param peak_sc_cnt: the number of subchain which couldn't be mapped last
  :type peak_sc_cnt: int
  :return: a MappingException object
  :rtype: :any:`MappingException`
  """

  def __init__(self, msg, backtrack_possible, 
               peak_vnf_cnt=None, peak_sc_cnt=None):
    super(MappingException, self).__init__(msg + " Backtrack available: %s"
                                           %backtrack_possible)
    self.backtrack_possible = backtrack_possible
    self.peak_mapped_vnf_count = peak_vnf_cnt
    self.peak_sc_cnt = peak_sc_cnt
