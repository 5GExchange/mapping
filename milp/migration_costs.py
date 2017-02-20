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
from abc import abstractmethod, ABCMeta


class AbstractMigrationCostHandler(object):
  __metaclass__ = ABCMeta

  def __init__ (self, request, resource):
    """
    Provides interface for migration cost calculation of the MILP's objective
    function. Resource must contain the already mapped VNFs.

    :param resource: NFFG which represents the state before any migration.
    """
    self.request = request
    self.resource = resource
    self.migration_cost = {}
    for v in self.request.nfs:
      for i in self.resource.infras:
        if v.functional_type in i.supported:
          if v.id not in self.migration_cost:
            self.migration_cost[v.id] = {}
          # meaning migrating VNF v to Infra node i.
          self.migration_cost[v.id][i.id] = 0.0

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


class ZeroMigrationCost(AbstractMigrationCostHandler):

  def __init__(self, request, resource):
    super(ZeroMigrationCost, self).__init__(request, resource)
    self._create_migration_costs()

  def _create_migration_costs(self):
    pass

  def get_maximal_cost(self):
    return self.maximal_cost


class ConstantMigrationCost(AbstractMigrationCostHandler):

  def __init__ (self, request, resource, const_cost=1.0):
    """
    Creates all migration to be a constant value, equal to all migration
    combinations.

    :param initial_nffg:
    :param const_cost: cost of moving a single VNF.
    """
    super(ConstantMigrationCost, self).__init__(request, resource)
    self.const_cost = const_cost
    self._create_migration_costs()

  def _create_migration_costs (self):
    # migration cost should stay zero for unmapped NFs
    for nf in self.resource.nfs:
      for iid in self.migration_cost[nf.id].iterkeys():
        if nf not in self.resource.running_nfs(iid):
          self.migration_cost[nf.id][iid] = self.const_cost

    # the total possible cost is when all mapped VNFs are moved.
    for _ in self.resource.nfs:
      self.maximal_cost += self.const_cost

  def get_maximal_cost(self):
    return self.maximal_cost
