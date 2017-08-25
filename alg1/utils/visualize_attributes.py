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

"""
Provides functions to build a large network modeling a carrier topology.
This is the target parameter optimization topology for the mapping algorithm.
The topology is based on WP3 - Service Provider Scenario for Optimization.ppt
by Telecom Italia (UNIFY SVN repo)
Parameter names are also based on the .ppt file.

"""
import argparse
import site
import xml.etree.ElementTree as ET

import networkx as nx

site.addsitedir('../..')
from nffg_lib.nffg import NFFG

def main():
  parser = argparse.ArgumentParser(
    description="Reads and NFFG file calculates utilization parameters and "
                "writes the result to a .graphml file. This file can be "
                "opened with yEd and a layout can be calculated, if saved as "
                ".graphml again additional graphical infos are available to "
                "the newly modified file. This new file can be given back to "
                "this script, which graphically visualises the previously "
                "calculated utilization parameters in the output .graphml "
                "file.")
  parser.add_argument("--nffg", metavar='path', type=str,
                      help="NFFG file path to be processed.")
  parser.add_argument("--graphml", metavar='path', type=str,
                      help="GraphML file with edge graphics.")
  parser.add_argument("-o", metavar='output.graphml',
                      help="Name of graphml file to write to without extension.")
  parser.add_argument("--max_width", type=float, default=10.0,
                      help="Maximum width of an edge.")
  parser.add_argument("--min_width", type=float, default=1.0,
                      help="Minimum width of an edge.")
  args = parser.parse_args()

  outputfile = args.o + ".graphml" if args.o else "output.graphml"

  # NFFG processing mode.
  if args.nffg:
    with open(args.nffg, "r") as f:
      nffg = NFFG.parse(f.read())

      nffg.calculate_available_node_res({})
      nffg.calculate_available_link_res([])

      nffg.clear_nodes(NFFG.TYPE_NF)

      graphml_to_wrtie = nx.DiGraph()
      graphml_to_wrtie.add_nodes_from(nffg.network.nodes_iter())
      for i, j, d in nffg.network.edges_iter(data=True):
        graphml_to_wrtie.add_edge(i, j, attr_dict=dict(
          [(l, str(v)) for l, v in d.__dict__.iteritems() if v is not None]))

      for i, j, d in graphml_to_wrtie.edges_iter(data=True):
        graphml_to_wrtie[i][j]['utilization'] = 1.0 - float(
          d['availbandwidth']) / float(d['bandwidth'])

      nx.write_graphml(graphml_to_wrtie, outputfile)

  # GRAPHML processing mode
  elif args.graphml:
    G = nx.read_graphml(args.graphml)
    graphml_to_read_xml = ET.parse(open(args.graphml))
    graphml_to_read = graphml_to_read_xml.getroot()
    util_key = None
    graphic_key = None
    for child in graphml_to_read:
      if 'attr.name' in child.attrib:
        if child.attrib['attr.name'] == 'utilization':
          util_key = child.attrib['id']
      if 'yfiles.type' in child.attrib:
        if child.attrib['yfiles.type'] == 'edgegraphics':
          graphic_key = child.attrib['id']

    for child in graphml_to_read:
      if 'edgedefault' in child.attrib:
        for e_n in child:
          if 'source' in e_n.attrib:
            edge_util = None
            for edge_data in e_n:
              if 'key' in edge_data.attrib:
                if edge_data.attrib['key'] == util_key:
                  edge_util = float(edge_data.text)
                  break
            # find the edge graphic and use utilization to scale line width
            for edge_data in e_n:
              if 'key' in edge_data.attrib:
                if edge_data.attrib['key'] == graphic_key:
                  for child_of_polyedge in edge_data:
                    if 'PolyLineEdge' in child_of_polyedge.tag:
                      for graphic_element in child_of_polyedge:
                        if 'LineStyle' in graphic_element.tag:
                          graphic_element.set('width', str(args.min_width + (
                          args.max_width - args.min_width) * edge_util))

    # write back the modified xml formatted graphml file
    graphml_to_read_xml.write(outputfile)

if __name__ == '__main__':
  main()