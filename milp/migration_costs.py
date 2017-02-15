# Copyright (c) 2017 Balazs Nemeth
#
# This file is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX. If not, see <http://www.gnu.org/licenses/>.
from abc import abstractmethod, ABCMeta


class AbstractMigrationCostHandler(object):
  __metaclass__ = ABCMeta

  def __init__ (self, initial_nffg):
    """
    Provides interface for migration cost calculation of the MILP's objective
    function.

    :param initial_nffg: NFFG which represents the state before any migration.
    """
    self.initial_nffg = initial_nffg
    self.migration_cost = {}
    for i in self.initial_nffg.infras:
      self.migration_cost[i] = {}
      for v in self.initial_nffg.nfs:
        # meaning migrating VNF v to Infra node i.
        self.migration_cost[i][v] = 0.0

    self.maximal_cost = 0.0

  @abstractmethod
  def _create_migration_costs (self):
    """
    Fills migration_cost component with the appropriate values.

    :return: dict of dicts of floats
    """
    pass

  @abstractmethod
  def get_maximal_cost (self):
    """
    Returns the possible maximal cost, which is the value in case when all
    VNFs are moved.

    :return: float
    """
    pass

  def objective_migration_component (self):
    """
    Returns a the coefficients of all node mapping variables in terms of
    migration. The migration component should be always non-negative.

    :return: dict of dicts
    """
    return self.migration_cost


class ConstantMigrationCost(AbstractMigrationCostHandler):

  def __init__ (self, initial_nffg, const_cost=1.0):
    """
    Creates all migration to be a constant value, equal to all migration
    combinations.

    :param initial_nffg:
    :param const_cost: cost of moving a single VNF.
    """
    super(ConstantMigrationCost, self).__init__(initial_nffg)
    self.const_cost = const_cost
    self._create_migration_costs()

  def _create_migration_costs (self):
    for i in self.initial_nffg.infras:
      for v in self.initial_nffg.nfs:
        if v not in self.initial_nffg.running_nfs(i):
          self.migration_cost[i][v] = self.const_cost

    print "Calculated Constant Migration Cost: \n", self.migration_cost
    # the total possible cost is when all VNFs are moved.
    for _ in self.initial_nffg.nfs:
      self.maximal_cost += self.const_cost

  def get_maximal_cost(self):
    return self.maximal_cost
