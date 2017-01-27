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
    # TODO: create migration cost placeholder for all mapping pairs, keyed by references

  @abstractmethod
  def _create_migration_costs (self):
    pass

  def objective_migration_component (self):
    """
    Returns a the coefficients of all node mapping variables in terms of
    migration. The migration component should be always non-negative.

    :return: dict of dicts
    """
    return self.migration_cost


class ConstantMigrationCost(AbstractMigrationCostHandler):
  def _create_migration_costs (self):
    # TODO: fill up all migration cost with constant value if they are moved.
    pass
