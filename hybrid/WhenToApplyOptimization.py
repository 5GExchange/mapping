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


class BaseWhenToApplyOptimization(object):

  def __init__(self, opt_ready_states, opt_pending_states, logger):
    """
    Return always true.

    :param opt_ready_states: iterable
    :param opt_pending_states: iterable
    """
    super(BaseWhenToApplyOptimization, self).__init__()
    self.opt_ready_states = opt_ready_states
    self.opt_pending_states = opt_pending_states
    self.log = logger

  def is_optimization_applicable (self, offline_state, just_check=False):
    return True

  def applied(self):
    return


class MaxNumberOfCalls (BaseWhenToApplyOptimization):
  """
  Enables applying the optimization when called at least 'number_of_calls' times
  and the optimization is finished.
  """

  def __init__(self, number_of_calls, opt_ready_states, opt_pending_states,
               logger):
    super(MaxNumberOfCalls, self).__init__(opt_ready_states,
                                           opt_pending_states, logger)
    self.number_of_required_calls = number_of_calls
    self.number_of_calls_happened = 0
    self.log.debug("Initialize AtLeastFixNumberOfCalls when_to_apply_opt "
                   "strategy.")

  def is_optimization_applicable(self, offline_state, just_check=False):
    if not just_check:
      self.number_of_calls_happened += 1
    self.log.debug(
      "Optimization applicability asked with offline state %s current number "
      "of calls happened: %s, just checking: %s" %
      (offline_state, self.number_of_calls_happened, just_check))
    is_number_reached = False
    if self.number_of_calls_happened == self.number_of_required_calls:
      is_number_reached = True
      if not just_check:
        self.number_of_calls_happened = 0
    return is_number_reached

  def applied(self):
    self.number_of_calls_happened = 0