#!/usr/bin/python -u
#
# Copyright (c) 2015 Balazs Nemeth
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


"""
TODO Adapt text
"""
from networkx.algorithms.flow.mincost import cost_of_flow

__author__ = 'Matthias Rost (mrost@inet.tu-berlin.de)'

import traceback
import json

from pprint import pformat

try:
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  import sys, os
  sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                  "../escape/escape/nffg_lib/")))
  from nffg import NFFG, NFFGToolBox

#try:
import gurobipy
from gurobipy import GRB, Model, LinExpr
#except ImportError:
#    print "couldn't load gurobi!"

from Alg1_Core import CoreAlgorithm
import UnifyExceptionTypes as uet
import Alg1_Helper as helper

# object for the algorithm instance
alg = None



class Graph(object):
    """ representing a directed graph ( G = ( V , E) )
    """

    def __init__(self, id):
        self.id = id
        self.graph = {}
        self.nodes = set()
        self.edges = set()
        self.out_neighbors = {}
        self.in_neighbors = {}


        self.edge_id_to_edge = {}

        #for storing general data
        self.graph = {}
        #for storing node related data
        self.node = {}
        #for storing edge related data
        self.edge = {}

        self.shortest_paths_costs = None
        self._shortest_paths_attribute_identifier = "cost"

    def add_node(self, node, **kwargs):
        self.nodes.add(node)
        self.out_neighbors[node] = []
        self.in_neighbors[node] = []
        self.node[node] = {}
        for key,value in kwargs.items():
            self.node[node][key] = value
            #self.node[node] = {}
            #self.node[node][k] = v


    def add_edge(self, id, tail, tail_port, head_port, head, bidirected=False, **kwargs):
        if (not tail in self.nodes) or (not head in self.nodes):
            raise Exception("Either node {} or node {} was not found while adding edge; "
                            "current node set is {}".format(tail, head, self.nodes))

        self._add_edge_one_direction(id, tail=tail, tail_port=tail_port, head_port=head_port, head=head, **kwargs)
        if bidirected:
            self._add_edge_one_direction(id + "_back", tail=head, tail_port=head_port, head_port=tail_port, head=tail, **kwargs )

    def _add_edge_one_direction(self, id, tail, tail_port, head_port, head, **kwargs):

        if id in self.edge_id_to_edge.values():
            raise Exception("The edge id {} is not unique.".format(id))

        if not tail in self.out_neighbors:
            self.out_neighbors[tail] = []
        if not head in self.in_neighbors:
            self.in_neighbors[head] = []

        self.edge_id_to_edge[id] = (tail, tail_port, head_port, head)

        self.out_neighbors[tail].append((tail, tail_port, head_port, head))
        self.in_neighbors[head].append((tail, tail_port, head_port, head))
        self.edges.add((tail, tail_port, head_port, head))
        self.edge[(tail,tail_port, head_port, head)] = {}
        for key,value in kwargs.items():
            self.edge[(tail, tail_port, head_port, head)][key] = value
            #self.edge[(tail,head)] = {}
            #self.edge[(tail,head)][key] = value

    def get_nodes(self):
        return self.nodes

    def get_edges(self):
        return self.edges

    def get_out_neighbors(self, node):
        return self.out_neighbors[node]

    def get_in_neighbors(self, node):
        return self.in_neighbors[node]

    def get_name(self):
        return self.name

    def get_number_of_nodes(self):
        return len(self.nodes)

    def get_number_of_edges(self):
        return len(self.edges)

    def get_shortest_paths_cost(self, node, other):
        if self.shortest_paths_costs is None:
            self.initialize_shortest_paths_costs()
        return self.shortest_paths_costs[node][other]

    def get_shortest_paths_cost_dict(self):
        if self.shortest_paths_costs is None:
            self.initialize_shortest_paths_costs()
        return self.shortest_paths_costs

    def initialize_shortest_paths_costs(self):

        #this can only be used if costs are defined as such for each edge
        self.shortest_paths_costs = {}

        for edge in self.edges:
            if self._shortest_paths_attribute_identifier not in self.edge[edge]:
                raise Exception("cost not defined for edge {}".format(edge))

        for u in self.nodes:
            self.shortest_paths_costs[u] = {}
            for v in self.nodes:
                if u is v:
                    self.shortest_paths_costs[u][v] = 0
                else:
                    self.shortest_paths_costs[u][v] = None


        for (u,u_p, v_p, v) in self.edges:
            if self.shortest_paths_costs[u][v] is None:
                self.shortest_paths_costs[u][v] = self.edge[(u,u_p,v_p,v)][self._shortest_paths_attribute_identifier]
            elif self.shortest_paths_costs[u][v] > self.edge[(u,u_p,v_p,v)][self._shortest_paths_attribute_identifier]:
                self.shortest_paths_costs[u][v] = self.edge[(u,u_p,v_p,v)][self._shortest_paths_attribute_identifier]

        for k in self.nodes:
            for u in self.nodes:
                for v in self.nodes:
                    if self.shortest_paths_costs[u][k] is not None and self.shortest_paths_costs[k][v] is not None:
                        cost_via_k = self.shortest_paths_costs[u][k] + self.shortest_paths_costs[k][v]
                        if self.shortest_paths_costs[u][v] is None or cost_via_k < self.shortest_paths_costs[u][v]:
                            self.shortest_paths_costs[u][v] = cost_via_k


    def check_connectivity(self):
        if self.shortest_paths_costs is None:
            self.initialize_shortest_paths_costs()
        for u in self.nodes:
            for v in self.nodes:
                if self.shortest_paths_costs[u][v] is None:
                    return False

        return True

    #TODO print attributes of graph, nodes and edges iff data is set to True
    def print_it(self, including_shortest_path_costs=True, data=False):
        print "Graph {}".format(self.id)
        print "\tnodes: {}, edges: {}".format(self.nodes, self.edges)
        if data:
          print "additional data.."
          print "\tof graph: {}".format(self.graph)
          print "\tof nodes: {}".format(self.node)
          print "\tof edges: {}".format(self.edge)
        if including_shortest_path_costs:
            if self.shortest_paths_costs is None:
                self.initialize_shortest_paths_costs()
            print "Distances:"
            for u in self.nodes:
                for v in self.nodes:
                    print "\t{} to {}: {}".format(u,v,self.shortest_paths_costs[u][v])


class Substrate(Graph):
    """ representing a single substrate ( G_s = ( V_s , E_s) )
        Attributes :
    """
    def __init__(self, id):
        super(self.__class__, self).__init__(id)
        self.types = set()
        self.nodes_supporting_type = {}

    def add_node(self, id, type, types, delay, bandwidth, cpu, memory, storage, cost=1):
        super(self.__class__, self).add_node(id,
                                             type = type,
                                             supported_types = types,
                                             delay = delay,
                                             bandwidth = bandwidth,
                                             cpu = cpu,
                                             memory = memory,
                                             storage = storage,
                                             cost = cost)
        for supported_type in types:
            self.types.add(supported_type)

        for supported_type in types:
            if supported_type not in self.nodes_supporting_type:
                self.nodes_supporting_type[supported_type] = [id]
            else:
                self.nodes_supporting_type[supported_type].append(id)

    def add_edge(self, id, tail, tail_port, head_port, head, delay, bandwidth, cost=1):
        if(tail in self.nodes and head in self.nodes):
            #is always bidirected
            super(self.__class__, self).add_edge(id,
                                                 tail,
                                                 tail_port,
                                                 head_port,
                                                 head,
                                                 bidirected=True,
                                                 delay = delay,
                                                 bandwidth = bandwidth,
                                                 cost = cost)

    def reduce_available_resources_at_node(self, node, resources):
        #TODO CHECK THAT DELAY IS REALLY NOT TOUCHED
        self.node[node]['bandwidth'] -= resources.bandwidth
        self.node[node]['cpu']  -= resources.cpu
        self.node[node]['memory'] -= resources.mem
        self.node[node]['storage'] -= self.node[node]['storage']


    def get_path_delay(self, path):
        return sum(map(lambda x:self.get_edge_delay(x),path))

    def get_edge_delay(self, edge):
        return self.edge[edge]['delay']

    def get_edge_cost(self, edge):
        return self.edge[edge]['cost']

    def get_edge_bandwidth(self, edge):
        return self.edge[edge]['bandwidth']

    def get_nodes_supporting_type(self, type):
        return self.nodes_supporting_type[type]

class Request(Graph):
    """ represents a request graph ?
    """
    def __init__(self, id):
        super(self.__class__, self).__init__(id)
        self.graph['path_requirements'] = {}
        self.types = set()


    def add_node(self, id, ntype, cpu, memory, storage, allowed_snodes=None):
        super(self.__class__, self).add_node(id,
                                             type=ntype,
                                             cpu = cpu,
                                             memory = memory,
                                             storage = storage,
                                             allowed_nodes = allowed_snodes)
        self.types.add(ntype)


    def add_edge(self, id, tail, tail_port, head_port, head, bandwidth):
        if(tail in self.nodes and head in self.nodes):
            super(self.__class__, self).add_edge(id,
                                                 tail,
                                                 tail_port,
                                                 head_port,
                                                 head,
                                                 bidirected=False,
                                                 bandwidth=bandwidth)
        else:
            raise Exception("Either the tail ({}) or the head ({}) are not contained in the node set {}.".format(tail, head, self.nodes))

    def increase_bandwidth_requirement_edge(self, edge_id, bandwidth):
        edge = self.edge_id_to_edge[edge_id]
        self.edge[edge]['bandwidth'] += bandwidth

    def add_delay_requirement(self, id, path, delay):
        """ adds to a specific 'path' a delay requirement
            important: the order of edges must be respected """
        if(set(path) <= set(self.edge_id_to_edge.keys())):
            #translate ids to edges
            tuple_path = []
            for edge_id in path:
                tuple_path.append(self.edge_id_to_edge[edge_id])

            self.graph['path_requirements'][(id, tuple(tuple_path))] = delay
        else:
            raise Exception("Path contains edges which are NOT in request edges: {} vs. {}".format(path, self.edge_id_to_edge.keys()))

    def get_path_requirements(self):
        return self.graph['path_requirements']

    def get_required_types(self):
        return self.types

    def get_type_of_node(self, node):
        return self.node[node]['type']

    def get_allowed_nodes_for_node_raw(self, node):
        return self.node[node]['allowed_nodes']

class Scenario(object):

    def __init__(self, substrate, requests):
        self.substrate = substrate
        self.requests = requests

    def compute_allowed_nodes(self, request, vnode):
        substrate_nodes = self.substrate.get_nodes_supporting_type(request.get_type_of_node(vnode))
        allowed_nodes_raw = request.get_allowed_nodes_for_node_raw(vnode)
        if allowed_nodes_raw is None:
            return substrate_nodes
        else:
            if set(allowed_nodes_raw) <= set(substrate_nodes):
                return allowed_nodes_raw
            else:
                raise Exception("Couldn't resolve allowed nodes for node {} of request".format(vnode, request.id))


def construct_name(name, req_id=None, vnode=None, snode=None, vedge=None, sedge=None):
    if req_id is not None:
        name += "_req[{}]".format(req_id)
    if vnode is not None:
        name += "_vnode[{}]".format(vnode)
    if snode is not None:
        name += "_snode[{}]".format(snode)
    if vedge is not None:
        name += "_vedge[{}]".format(vedge)
    if sedge is not None:
        name += "_sedge[{}]".format(sedge)
    return name.replace(" ", "")

class ModelCreator(object):

    def __init__(self, scenario):
        self.scenario = scenario
        self.substrate = scenario.substrate
        self.requests = scenario.requests

        #for easier lookup which nfs can be placed onto which substrate nodes
        self.allowed_nodes_copy = {}

        #model

        self.model = None

        #variables
        self.var_embedding_decision = {}
        self.var_node_mapping = {}
        self.var_edge_mapping = {}



    def init_model_creator(self):

        self.preprocess()

        self.model = gurobipy.Model("test")
        self.create_variables()

        #necessary for accessing the variables after creation
        self.model.update()

        self.create_constraints()

        self.create_objective()


        self.plugin_objective_maximize_number_of_embedded_requests()

        self.model.update()


        self.model.optimize()

    def preprocess(self):
        for req in self.requests:
            self.allowed_nodes_copy[req] = {}
            for vnode in req.nodes:
                self.allowed_nodes_copy[req][vnode] = self.scenario.compute_allowed_nodes(request, vnode)


    def create_variables(self):

        #for each request a decision variable is created

        for req in self.requests:
            variable_id = construct_name("embedding_decision", req_id=req.id)
            self.var_embedding_decision[req] = self.model.addVar(lb=0.0, ub=1.0, obj=0.0, vtype=GRB.BINARY, name=variable_id)

        for req in self.requests:
            self.var_node_mapping[req] = {}
            for vnode in req.nodes:
                self.var_node_mapping[req][vnode] = {}
                allowed_nodes = self.allowed_nodes_copy[req][vnode]
                for snode in allowed_nodes:
                    variable_id = construct_name("node_mapping", req_id=req.id, vnode=vnode, snode=snode)
                    self.var_node_mapping[req][vnode][snode] = self.model.addVar(lb=0.0, ub=1.0, obj=0.0, vtype=GRB.BINARY, name=variable_id)

        for req in self.requests:
            self.var_edge_mapping[req] = {}
            #TODO the above assumes that arbitrary paths are possible. However, this is not the case as delay constraints need to hold.
            #TODO Some easy (presolving) optimizations would hence be applicable.
            for vedge in req.edges:
                self.var_edge_mapping[req][vedge] = {}
                for sedge in self.substrate.edges:
                    variable_id = construct_name("edge_mapping", req_id=req.id, vedge=vedge, sedge=sedge)
                    self.var_edge_mapping[req][vedge][sedge] = self.model.addVar(lb=0.0, ub=1.0, obj=0.0, vtype=GRB.BINARY, name=variable_id)


    def create_constraints(self):
        self.create_constraint_request_embedding_triggers_node_embeddings()
        self.create_constraint_induce_and_preserve_unit_flows()
        self.create_constraint_node_loads_standard()
        self.create_constraint_node_load_bandwidth()
        self.create_constraint_delay_requirements()


    def create_constraint_request_embedding_triggers_node_embeddings(self):
        for req in self.requests:
            for vnode in req.nodes:
                expr = LinExpr([(1.0, self.var_node_mapping[req][vnode][snode])
                                for snode in self.allowed_nodes_copy[req][vnode]]
                               +
                               [(-1.0, self.var_embedding_decision[req])])
                constr_name = construct_name("request_embedding_triggers_node_embeddings", req_id=req.id, vnode=vnode)
                self.model.addConstr(expr, GRB.EQUAL, 0.0, name=constr_name)


    def create_constraint_induce_and_preserve_unit_flows(self):
        for req in self.requests:
            for vedge in req.edges:
                for snode in self.substrate.nodes:
                    print "FOOO"
                    print self.substrate.in_neighbors[snode]
                    print self.substrate.out_neighbors[snode]


                    expr = LinExpr([(-1.0, self.var_edge_mapping[req][vedge][sedge]) for sedge in self.substrate.in_neighbors[snode]]
                                   +
                                   [(+1.0, self.var_edge_mapping[req][vedge][sedge]) for sedge in self.substrate.out_neighbors[snode]])

                    print expr

                    vtail,_,_,vhead = vedge

                    if snode in self.allowed_nodes_copy[req][vtail]:
                        expr.addTerms(-1.0, self.var_node_mapping[req][vtail][snode])

                    if snode in self.allowed_nodes_copy[req][vhead]:
                        expr.addTerms(+1.0, self.var_node_mapping[req][vhead][snode])

                    constr_name = construct_name("induce_and_preserve_unit_flows", req_id=req.id, vedge=vedge, snode=snode)

                    self.model.addConstr(expr, GRB.EQUAL, 0.0, name=constr_name)

    def create_constraint_node_loads_standard(self):
        node_properties = ["cpu", "memory", "storage"]

        for node_property in node_properties:
            for snode in self.substrate.nodes:

                expr = LinExpr([(req.node[vnode][node_property], self.var_node_mapping[req][vnode][snode])
                                for req in self.requests for vnode in req.nodes if snode in self.allowed_nodes_copy[req][vnode]])


                constr_name = construct_name("node_loads_standard", snode=snode) + "_{}".format(node_property)

                self.model.addConstr(expr, GRB.LESS_EQUAL, self.substrate.node[snode][node_property],  constr_name)

    def create_constraint_node_load_bandwidth(self):
        for snode in self.substrate.nodes:
            expr = LinExpr([(req.edge[vedge]['bandwidth'], self.var_edge_mapping[req][vedge][sedge])
                            for req in self.requests
                            for vedge in req.edges
                            for sedge in self.substrate.in_neighbors[snode]])

            constr_name = construct_name("node_load_bandwidth", snode=snode)

            self.model.addConstr(expr, GRB.LESS_EQUAL, self.substrate.node[snode]['bandwidth'], constr_name)

    def create_constraint_edge_load_bandwidth(self):
        for sedge in self.substrate.edges:
            expr = LinExpr([(req.edge[vedge]['bandwidth'], self.var_edge_mapping[req][vedge][sedge])
                            for req in self.requests
                            for vedge in req.edges])

            constr_name = construct_name("edge_load_bandwidth", sedge=sedge)

            self.model.addConstr(expr, GRB.LESS_EQUAL, self.substrate.edge[sedge]['bandwidth'], constr_name)

    def create_constraint_delay_requirements(self):
        for req in self.requests:

            for (id, tuple_path), delay_bound in req.get_path_requirements().iteritems():
                expr = LinExpr()
                for vedge in tuple_path:
                    sub_expr = LinExpr([(self.substrate.edge[(stail, stail_p, shead_p, shead)]['delay'] +
                                         self.substrate.node[shead]['delay'],
                                         self.var_edge_mapping[req][vedge][(stail, stail_p, shead_p, shead)])
                                         for (stail, stail_p, shead_p, shead) in self.substrate.edges
                                        ])

                    expr.add(sub_expr)

                constr_name = construct_name("delay_requirement", req_id=req.id) + "_id[{}]".format(id)

                self.model.addConstr(expr, GRB.LESS_EQUAL, delay_bound, constr_name)



    def create_objective(self):
        pass

    def plugin_objective_maximize_number_of_embedded_requests(self):
        expr = LinExpr([(1.0, self.var_embedding_decision[req]) for req in self.requests])
        self.model.setObjective(expr, GRB.MAXIMIZE)

def convert_req_to_request(req):


    print "creating request {}".format(req.id)
    result = Request(id=req.id)

    # ADD NODES
    # there exist three types: infras, saps, nfs

    #   infras: make sure that none of these exist
    for infra in req.infras:
        #Matthias: this is just to check that I got the concept right
        if infra.type != NFFG.TYPE_INFRA:
            raise Exception("infra node is no infra node: {} has type {}".format(infra.id, infra.type))
        raise Exception("request cannot contain infrastructure nodes: ".format(infra.id))

    #   saps
    for sap in req.saps:
        print "\t adding SAP node {} WITHOUT CONSIDERING CPU, MEMORY or STORAGE".format(sap.id)
        print "\t\t [" + ', '.join("%s: %s" % item for item in vars(sap).items()) + "]"

        if (sap.delay is not None and sap.delay > 0) or (sap.bandwidth is not None and sap.bandwidth > 0):
            raise Exception("Cannot handle SAP delay ({}) or bandwidth ({}).".format(sap.delay, sap.bandwidth))

        result.add_node(id=sap.id, ntype="SAP", cpu=0, memory=0, storage=0, allowed_snodes=[sap.name])

    #   nfs
    for nf in req.nfs:
        print "\t adding NF node {}".format(nf.id)

        print "\t\t [" + ', '.join("%s: %s" % item for item in vars(nf).items()) + "]"

        #check that bandwidth and delay are not used
        if nf.resources.delay is not None and nf.resources.delay > 0:
            raise Exception("Cannot handle NF delay requirements of NF {}".format(nf.id))

        if nf.resources.bandwidth is not None and nf.resources.bandwidth > 0:
            raise Exception("Cannot handle NF bandwidth requirements of NF {}".format(nf.id))

        result.add_node(id=nf.id, ntype=nf.functional_type, cpu=nf.resources.cpu, memory=nf.resources.mem, storage=nf.resources.storage, allowed_snodes=None)

    # ADD EDGES
    #   there exist four types: STATIC, DYNAMIC, SG and REQUIREMENT

    #   STATIC and DYNAMIC: make sure that these are not contained
    for link in req.links:
        #Matthias: this is just to check that I got the concept right
        if link.type != NFFG.TYPE_LINK_DYNAMIC and link.type != NFFG.TYPE_LINK_STATIC:
            raise Exception("link is neither dynamic nor static: {}".format(link.id))
        raise Exception("Request may not contain static or dynamic links: {}".format(link.id))

    #   SG
    for sg_link in req.sg_hops:

        print "\t adding edge {}".format(sg_link.id)

        print "\t\t [" + ', '.join("%s: %s" % item for item in vars(sg_link).items()) + "]"


        bw_req = sg_link.bandwidth
        if bw_req is None:
            bw_req = 0

        result.add_edge(id=sg_link.id, tail=sg_link.src.node.id, tail_port = sg_link.src.id, head_port=sg_link.dst.id, head=sg_link.dst.node.id, bandwidth=bw_req)

        if sg_link.delay is not None and sg_link.delay > 0:
            #add new novel constraint
            result.add_delay_requirement(id="sg_link_req_{}".format(sg_link.id), path=[sg_link.id], delay=sg_link.delay)

    for path_req in req.reqs:

        print "\t handling path requirement {}".format(path_req.id)

        print "\t\t [" + ', '.join("%s: %s" % item for item in vars(path_req).items()) + "]"

        result.add_delay_requirement(id=path_req.id, path=path_req.sg_path, delay=path_req.delay)

        if path_req.bandwidth is not None and path_req.bandwidth > 0:
            print "\t\t there exists an additional bandwidth requirement of {} units. Augmenting every contained link with the required bandwidth.".format(path_req.bandwidth)

            #TODO I AM UNSURE WHETHER THE FOLLOWING IS CORRECT
            for edge_id in path_req.sg_path:

                edge = result.edge_id_to_edge[edge_id]
                bw_req_before = result.edge[edge]['bandwidth']
                result.edge[edge]['bandwidth'] += path_req.bandwidth
                print "\t\t\t increasing bandwidth along edge {} (i.e. {}) from {} to {}".format(edge_id, edge, bw_req_before, result.edge[edge]['bandwidth'])


    print "created request looks like .."

    result.print_it(including_shortest_path_costs=False, data=True)

    print "\n\n"

    return result

def convert_nffg_to_substrate(nffg):



    print "creating substrate {}".format(nffg.id)
    result = Substrate(id=nffg.id)

    print "\t [" + ', '.join("%s: %s" % item for item in vars(nffg).items()) + "]"

    # ADD NODES
    # there exist three types: infras, saps, nfs

    #   infras: make sure that these are added with the right resources

    for infra in nffg.infras:

        print "\t adding node {}".format(infra.id)

        print "\t\t [" + ', '.join("%s: %s" % item for item in vars(infra).items()) + "]"

        delay = nffg.calculate_available_node_res('delay')

        result.add_node(id=infra.id,
                        type="INFRA",
                        types=infra.supported,
                        delay=infra.resources.delay,
                        bandwidth=infra.resources.bandwidth,
                        cpu=infra.resources.cpu,
                        memory=infra.resources.mem,
                        storage=infra.resources.storage)

        # taking into account allocations..
        for vnf in nffg.running_nfs(infra.id):
            print "\t\t\t reducing resources of node {} according to resources {} of VNF {}".format(infra.id, vnf.resources, vnf.id)
            result.reduce_available_resources_at_node(infra.id, vnf.resources)

        print "\t\t final resources of node {} are {}".format(infra.id, result.node[infra.id])



     #   saps
    for sap in nffg.saps:
        print "\t adding SAP node {} WITHOUT CONSIDERING CPU, MEMORY, BANDWIDTH OR DELAY".format(sap.id)
        print "\t\t [" + ', '.join("%s: %s" % item for item in vars(sap).items()) + "]"

        #if (sap.delay is not None and sap.delay > 0) or (sap.bandwidth is not None and sap.bandwidth > 0):
        #    raise Exception("Cannot handle SAP delay ({}) or bandwidth ({}).".format(sap.delay, sap.bandwidth))

        if sap.delay is not None and sap.delay > 0:
            print "\t\t ignoring {} delay at SAP {} as this is not of importance here; setting delay to 0 ".format(sap.delay, sap.id)
        print "\t\t ignoring {} bandwidth at SAP {} as this is not of importance here; setting bandwidth to inf".format(sap.bandwidth, sap.id)


        result.add_node(id=sap.id,
                        type="SAP",
                        types=["SAP"],
                        delay=0.0,
                        bandwidth=GRB.INFINITY,
                        cpu=0,
                        memory=0,
                        storage=0)

    #   nfs are not added to the substrate graph!


    # ADD EDGES

    for edge_link in nffg.links:

        if edge_link.type == "STATIC":

            print "\t adding static link {}".format(edge_link.id)
            print "\t\t [" + ', '.join("%s: %s" % item for item in vars(edge_link).items()) + "]"

            result.add_edge(id=edge_link.id,
                            tail=edge_link.src.node.id,
                            tail_port=edge_link.src.id,
                            head_port=edge_link.dst.id,
                            head=edge_link.dst.node.id,
                            delay=edge_link.delay,
                            bandwidth=edge_link.bandwidth)

        else:
            print "\t disregarding {} link {}".format(edge_link.type, edge_link.id)


    print "created substrate looks like .."

    result.print_it(including_shortest_path_costs=False, data=True)

    return result





if __name__ == '__main__':
  try:
    # req = _constructExampleRequest()
    # net = _constructExampleNetwork()

    # req = _example_request_for_fallback()
    # print req.dump()
    # req = _onlySAPsRequest()
    # print net.dump()
    # req = _testRequestForBacktrack()
    # net = _testNetworkForBacktrack()
    with open('../examples/escape-mn-req.nffg', "r") as f:
      req = NFFG.parse(f.read())

    request = convert_req_to_request(req)

    #print json.dumps(req, indent=2, sort_keys=False)
    with open('../examples/escape-mn-topo.nffg', "r") as g:
      net = NFFG.parse(g.read())
      #net.duplicate_static_links()

    substrate = convert_nffg_to_substrate(net)

    scen = Scenario(substrate, [request])
    mc = ModelCreator(scen)
    mc.init_model_creator()

    import sys
    sys.exit(0)

  except uet.UnifyException as ue:
    print ue, ue.msg
    print traceback.format_exc()
