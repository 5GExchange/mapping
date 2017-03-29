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

import sys, os, getopt, subprocess, copy
import numpy as np
from collections import OrderedDict
import matplotlib.pyplot as plt
import math

# runs when mapping repo is cloned individually, and NFFG lib is in a
# sibling directory. WARNING: cicular import is not avioded by design.
import site
site.addsitedir('../..')
from nffg_lib.nffg import NFFG

helpmsg="""
Decompresses the NFFG-s given in command line, sorts them base on test level,
and calculates the average and deviation of link/node resources for all 
resource types. Prints them in ascending order of test levels in CSV format.
Removes the uncompressed NFFG after it is finished with its processing.
   -h                               Print this help message.
   -l <<NFFG location>>             Location of the *.nffg files.
   --prefix=<<string>>              File names should look like
   --suffix=<<string>>              "prefix<<NUM>>suffix<<optional variable string>>.nffg"
   --single_nffg=<<path>>           If given, a single uncompressed NFFG is
                                    processed.
   --hist=<<aggregation size>>      If given, draws the histogram
                                    for the utilization of resource 
                                    components aggregating the values by the 
                                    given size.
                                    WARN: histogram drawing doesn't work!
   --add_hist_values                If set, non-zero values are written above the
                                    bars on the histogram.
   --hist_format=<<pdf|png|...>>    The format of the saved histograms. 
                                    PNG by default
   --starting_lvl=i                 Start the analyzation only after the given 
                                    NFFG number.
   --one                            Exit after one NFFG processing
   --cdf_format=<<pdf|png|...>>     The format of the saved CDF, PNG by default.
   --cdf                            Produces images of Cumulative Distribution 
                                    Function in the format specified by
                                    --cdf_formatoption for each resource type.
   --print_avgs                     Print the average resource utilizations for 
                                    all processed NFFG-s in CSV format.
   --print_devs                     Print the deviations of resource utilizations
                                    for all processed NFFG-s in CSV format. 
                                    The --cdf option must be set too.
   --print_cdf_data=<<res|mem...>>  Print the data used to plot the CDF in CSV 
                                    format for the given resource types. The 
                                    --cdf option must be set too!
   --no_cdf_interpolation           If set, CDF is delignated in a step function
                                    manner, instead of linear interpolation 
                                    between points.
   --print_minmax                   Print the minimal and maximal utilization of 
                                    all resource types of the processed NFFG-s.
   --print_objective_value          Print the objective function value of each NFFG.
   --plot_aspect=<<float>>          Ratio of x/y axis.
"""

print_avgs = False
print_devs = False
print_cdf_data = False
draw_cdf = False
draw_hist = False
print_minmax = False
reskeys = ['cpu', 'mem', 'storage', 'bandwidth']
hist_aggr_size = 0.05

def increment_util_counter(d, u, aggr_size):
  # coudl be binary search...
  prev_aggr = aggr_size
  for aggr in d:
    if aggr > u:
      d[prev_aggr] += 1
      return
    prev_aggr = aggr

def autolabel(rects, ax):
  # attach some text labels
  for rect in rects:
    height = rect.get_height()
    if height > 0.0:
      ax.text(rect.get_x() + rect.get_width()/2., 1.05*height,
              '%.2f' % height,
              ha='center', va='bottom')

def gather_and_print_cdf_hist_data (nffg, empty_hist, empty_cdf, nffg_num=0):
  # calculate avg. res utils by resource types.
  avgs = {}
  cnts = {}
  mins = {}
  maxs = {}
  if draw_hist:
    hist = copy.deepcopy(empty_hist)
  if draw_cdf:
    cdf = copy.deepcopy(empty_cdf)
  for noderes in reskeys:
    avgs[noderes] = 0.0
    cnts[noderes] = 0
    for i in nffg.infras:
      # only count nodes which had these resources initially
      if i.resources[noderes] > 1e-10:
        util = float(i.resources[noderes] - i.availres[noderes]) / \
               i.resources[noderes]
        avgs[noderes] += util
        cnts[noderes] += 1

        # maintain max/min struct
        if noderes in mins:
          if mins[noderes] > util:
            mins[noderes] = util
        else:
          mins[noderes] = util
        if noderes in maxs:
          if maxs[noderes] < util:
            maxs[noderes] = util
        else:
          maxs[noderes] = util

        if draw_hist:
          increment_util_counter(hist[noderes], util, hist_aggr_size)
        if draw_cdf:
          cdf[noderes].append(util)
    avgs[noderes] /= cnts[noderes]
  avg_linkutil = 0.0
  linkcnt = 0
  for l in nffg.links:
    if l.type == 'STATIC':
      link_util = float(l.bandwidth - l.availbandwidth) / l.bandwidth
      avg_linkutil += link_util
      linkcnt += 1

      # maintain max/min struct
      if 'link_bw' in mins:
        if mins['link_bw'] > link_util:
          mins['link_bw'] = link_util
      else:
        mins['link_bw'] = link_util
      if 'link_bw' in maxs:
        if maxs['link_bw'] < link_util:
          maxs['link_bw'] = link_util
      else:
        maxs['link_bw'] = link_util

      if draw_hist:
        increment_util_counter(hist['link_bw'], link_util, hist_aggr_size)
      if draw_cdf:
        cdf['link_bw'].append(link_util)
  avg_linkutil /= linkcnt

  if print_avgs:
    to_print = [nffg_num, avg_linkutil]
    to_print.extend([avgs[res] for res in reskeys])
    print ",".join(map(str, to_print))

  if print_devs:
    avgs['link_bw'] = avg_linkutil
    devs = {}
    for res in cdf:
      devs[res] = math.sqrt(sum([(avgs[res] - u) ** 2 for u in cdf[res]])
                            / \
                            (len(cdf[res]) - 1))
    to_print = [nffg_num]
    to_print.extend([devs[res] for res in cdf])
    print ",".join(map(str, to_print))

  if print_minmax:
    to_print = [nffg_num]
    for res in reskeys + ['link_bw']:
      to_print.append(mins[res])
      to_print.append(maxs[res])
    print ",".join(map(str, to_print))

  return hist, cdf

def draw_histogram (hist, add_hist_values, hist_format, plot_aspect, loc_of_nffgs,
                                            prefix, suffix, variable_str="", nffg_num=0):
  # normalize the histogram to [0,1], so the resource types could be
  # plotted
  # on the same bar chart
  for res in hist:
    sum_util_cnt = sum(
      [hist[res][util_range] for util_range in hist[res]])
    for util_range in hist[res]:
      hist[res][util_range] = float(hist[res][util_range]) / sum_util_cnt

  # plot the histograms.
  fig, ax = plt.subplots()
  ax.set_ylim((0.00, 1.10))
  range_seq = np.array(
    [float("%.4f" % (aggr / hist_aggr_size)) for aggr in \
     np.arange(hist_aggr_size, 1.0, hist_aggr_size)])
  range_seq = np.append(range_seq, [1.0 / hist_aggr_size])
  width = range_seq[-1] / (len(hist) + 2) / len(range_seq)
  colors = iter(['r', 'g', 'b', 'c', 'y'])
  i = 0
  rects = []
  for res in hist:
    rect = ax.bar((range_seq - 1) * (len(hist) + 2) * width + \
                  (i + 4.5) * width,
                  [hist[res][util_range] for util_range in hist[res]],
                  width, color=next(colors))
    rects.append((res, rect))
    i += 1
    if add_hist_values:
      autolabel(rect, ax)
  ax.set_ylabel("Ratio of network element counts to total count")
  ax.set_xlabel("Resource utilization intervals [%]")
  ax.set_xticks(range_seq * (len(hist) + 2) * width)
  ax.set_xticklabels(
    [str(int(100 * util_range)) for util_range in hist['cpu']])
  ax.set_aspect(plot_aspect)
  ax.legend([r[0] for r in zip(*rects)[1]], zip(*rects)[0], ncol=5,
            loc='upper left', fontsize=8, bbox_to_anchor=(0, 1))
  plt.savefig('%s/hists/%s%s%s%s.%s' % (loc_of_nffgs, prefix, nffg_num,
                                     suffix, variable_str, hist_format),
              bbox_inches='tight')
  plt.close(fig)

def draw_cummulative_distribution_function (cdf, res_cdf_to_print,
                                            no_cdf_interpolation, cdf_format,
                                            plot_aspect, loc_of_nffgs,
                                            prefix, suffix, variable_str="", nffg_num=0):
  # sort util values incrementing in each resource type
  for res in cdf:
    cdf[res] = sorted(cdf[res])
  fig, ax = plt.subplots()
  ax.set_xlim((-0.05, 1.05))
  ax.set_ylim((-0.05, 1.19))
  colors = iter(['r', 'g', 'b', 'c', 'y'])
  styles = iter(
    [[8, 4, 2, 4, 2, 4], [4, 2], [8, 4, 4, 2], [8, 4, 2, 4], []])
  markers = iter(['o', 'v', '+', 's', ''])
  for res in cdf:
    last_point = (0, 0)
    vertical_step = 1.0 / len(cdf[res])
    rescolor = next(colors)
    resline = next(styles)
    resmarker = next(markers)
    reslab = res
    if print_cdf_data and res == res_cdf_to_print:
      cdf_plot_data = [last_point]
    for point in zip(cdf[res],
                     np.append(
                       np.arange(vertical_step, 1.0, vertical_step),
                       [1.0])):
      if no_cdf_interpolation:
        plt.plot((last_point[0], point[0]),
                 (last_point[1], last_point[1]),
                 color=rescolor, lw=1.5, label=reslab, dashes=resline,
                 marker=resmarker)
        plt.plot((point[0], point[0]), (last_point[1], point[1]),
                 color=rescolor, lw=1.5, dashes=resline, marker=resmarker)
      else:
        plt.plot((last_point[0], point[0]), (last_point[1], point[1]),
                 color=rescolor, lw=1.5, dashes=resline, label=reslab,
                 marker=resmarker)
      reslab = None
      if print_cdf_data and res == res_cdf_to_print:
        cdf_plot_data.append(point)
      last_point = point
    plt.plot((last_point[0], 1.0), (last_point[1], 1.0),
             color=rescolor, lw=1.5, dashes=resline, label=reslab,
             marker=resmarker)
    if print_cdf_data and res == res_cdf_to_print:
      cdf_plot_data.append((1.0, 1.0))
      print nffg_num, ",", ",".join(
        map(lambda t: "(%.6f; %.6f)" % (t[0], t[1]),
            cdf_plot_data))
  ax.set_ylabel("CDF")
  ax.set_xlabel("Resource utilization [%]")
  ax.set_aspect(plot_aspect)
  ax.set_xticks([float(i) / 100 for i in xrange(0, 101, 20)])
  ax.set_xticklabels([str(i) for i in xrange(0, 101, 20)])
  ax.legend(bbox_to_anchor=(0, 1), loc='upper left', ncol=5, fontsize=12,
            columnspacing=0.9)
  plt.savefig('%s/cdfs/%s%s%s%s.%s' % (loc_of_nffgs, prefix, nffg_num,
                                     suffix, variable_str, cdf_format),
              bbox_inches='tight')
  plt.close(fig)

def calc_objective_value (nffg):
  max_edge_cost = 0.0
  edge_cost = 0.0
  # find sum of used bandwidth and its max possible value
  for link in nffg.links:
    if link.type == NFFG.TYPE_LINK_STATIC:
      max_edge_cost += link.bandwidth
      edge_cost += link.bandwidth - link.availbandwidth

  # find the node with lowest utilization, balancing means maximizing
  # the lowest utilization
  node_resources_to_balance = ["cpu", "mem"]
  load_balance_component = 1.0
  for res in node_resources_to_balance:
    for node in nffg.infras:
      if node.resources[res] > 1e-30:
        node_load = float(node.resources[res] - node.availres[res]) / \
                    node.resources[res]
        if node_load < load_balance_component:
          load_balance_component = node_load

  return edge_cost/max_edge_cost, load_balance_component

def main(argv):
  global print_avgs, print_devs, print_minmax, draw_hist, draw_cdf
  try:
    opts, args = getopt.getopt(argv, "hl:", ["hist=", "add_hist_values",
                                             "hist_format=", "starting_lvl=",
                                             "one", "cdf_format=", "cdf",
                                             "print_devs", "print_avgs",
                                             "print_cdf_data=", "print_minmax", 
                                             "no_cdf_interpolation", "plot_aspect=",
                                               "single_nffg=", "prefix=", "suffix=",
                                             "print_objective_value"])
  except getopt.GetoptError as goe:
    print helpmsg
    raise
  loc_of_nffgs = ""
  add_hist_values = False
  hist_format = "png"
  starting_lvl = 0
  process_only_one = False
  cdf_format = "png"
  res_cdf_to_print = None
  no_cdf_interpolation = True
  plot_aspect = 1
  single_nffg_process = False
  nffg_prefix = None
  nffg_suffix = None
  nffg_name_variable_str = {}
  print_cdf_data = False
  print_devs = False
  print_avgs = False
  print_minmax = False
  print_objective_value = False
  for opt, arg in opts:
    if opt == "-h":
      print helpmsg
      sys.exit()
    elif opt == "-l":
      loc_of_nffgs = arg
    elif opt == "--hist":
      draw_hist = True
      hist_aggr_size = float(arg)
      hist = {}
      for res in reskeys + ['link_bw']:
        hist[res] = OrderedDict()
        for aggr in np.arange(hist_aggr_size, 1.0, hist_aggr_size):
          hist[res][float("%.4f"%aggr)] = 0
        hist[res][1.0] = 0
    elif opt == "--add_hist_values":
      add_hist_values = True
    elif opt == "--hist_format":
      hist_format = arg
    elif opt == "--starting_lvl":
      starting_lvl=int(arg)
    elif opt == "--one":
      process_only_one = True
    elif opt == "--cdf":
      draw_cdf = True
      cdf = {}
      for res in reskeys + ['link_bw']:
        cdf[res] = []
    elif opt == "--cdf_format":
      cdf_format = arg
    elif opt == "--print_devs":
      print_devs = True
    elif opt == "--print_avgs":
      print_avgs = True
    elif opt == "--print_cdf_data":
      print_cdf_data = True
      res_cdf_to_print = arg
    elif opt == "--no_cdf_interpolation":
      no_cdf_interpolation = True
    elif opt == "--print_minmax":
      print_minmax = True
    elif opt == "--plot_aspect":
      plot_aspect = float(arg)
    elif opt == "--single_nffg":
      single_nffg_process = True
      single_nffg_path = arg
    elif opt == "--prefix":
      nffg_prefix = arg
    elif opt == "--suffix":
      nffg_suffix = arg
    elif opt == "--print_objective_value":
      print_objective_value = True

  if not single_nffg_process and (nffg_suffix is None or nffg_prefix is None):
    raise Exception("If --single_process is not specified a location and "
                    "--prefix and --suffix must be specified!")

  # clean previously created plots
  os.system("rm -rf %s/hists %s/cdfs"%(loc_of_nffgs, loc_of_nffgs))
  os.system("mkdir %s/hists %s/cdfs"%(loc_of_nffgs, loc_of_nffgs))

  if not single_nffg_process:
    nffg_num_list = []
    bashCommand = "ls -x " + loc_of_nffgs
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    nffg_files = process.communicate()[0]
    for filen in nffg_files.replace("\n", " ").split(" "):
      if nffg_prefix in filen and nffg_suffix in filen:
        truncted_filen = filen.lstrip(nffg_prefix).rstrip(".nffg").split(nffg_suffix)
        number_of_nffg = int(truncted_filen[0])
        if len(truncted_filen) > 1:
          nffg_name_variable_str[number_of_nffg] = truncted_filen[1]
        else:
          nffg_name_variable_str[number_of_nffg] = ""
        nffg_num_list.append(number_of_nffg)
    nffg_num_list = sorted(filter(lambda x: x>=starting_lvl, nffg_num_list))
  
  if print_avgs:
    print "nffg_num, avg(link_bw), ",", ".join(["".join(["avg(",noderes,")"]) \
                                                for noderes in reskeys])
  if print_devs:
    print "nffg_num, ", ", ".join(["".join(["dev(",noderes,")"]) \
                                   for noderes in cdf])

  if print_minmax:
    print "nffg_num, ", ", ".join(["min(%s), max(%s)"%(res, res) for res in \
                                   reskeys + ['link_bw']])

  if print_objective_value:
    print "nffg_num, edge_cost_comp, load_balancing_comp, total"

  if draw_hist:
    empty_hist = copy.deepcopy(hist)
  if draw_cdf:
    empty_cdf = copy.deepcopy(cdf)

  if not single_nffg_process:
    for nffg_num in nffg_num_list:
      filename = "".join((nffg_prefix, str(nffg_num), nffg_suffix,
                          nffg_name_variable_str[nffg_num], ".nffg"))
      with open("".join((loc_of_nffgs, "/", filename)), "r") as f:
        nffg = NFFG.parse(f.read())
        nffg.calculate_available_node_res()
        nffg.calculate_available_link_res([])

      hist, cdf = gather_and_print_cdf_hist_data(nffg, empty_hist, empty_cdf, nffg_num)

      # we can only know the number of CDF points after the first processing.
      # this number should stay the same for all consequential NFFG-s.
      if print_cdf_data and nffg_num == nffg_num_list[0]:
        print ",".join(["nffg_num"] + \
                       [res_cdf_to_print + "_cdf_point" + str(i) \
                        for i in range(0, len(cdf[res_cdf_to_print]) + 2)])

      if print_objective_value:
        edge_comp, balancing_comp = calc_objective_value(nffg)
        print ",".join(map(str, (nffg_num, edge_comp, balancing_comp,
                                 edge_comp+balancing_comp)))
      # NOTE: Draw hist doesn't work but not needed for now.
      # if draw_hist:
      #   draw_histogram(hist, add_hist_values, hist_format, plot_aspect,
      #                  loc_of_nffgs, nffg_prefix, nffg_suffix,
      #                  nffg_name_variable_str[nffg_num], nffg_num)

      if draw_cdf:
        draw_cummulative_distribution_function(cdf, res_cdf_to_print,
                                               no_cdf_interpolation, cdf_format,
                                               plot_aspect, loc_of_nffgs,
                                               nffg_prefix, nffg_suffix,
                                               nffg_name_variable_str[nffg_num],
                                               nffg_num)
      # maybe finish after one iteration
      if process_only_one:
        break
  else:
    with open(single_nffg_path, "r") as f:
      nffg = NFFG.parse(f.read())
      nffg.calculate_available_node_res()
      nffg.calculate_available_link_res([])
      hist, cdf = gather_and_print_cdf_hist_data(nffg, empty_hist, empty_cdf)

      # if draw_hist:
      #   draw_histogram(hist, add_hist_values, hist_format, plot_aspect,
      #                  loc_of_nffgs, nffg_prefix, nffg_suffix)

      if draw_cdf:
        draw_cummulative_distribution_function(cdf, res_cdf_to_print,
                                               no_cdf_interpolation, cdf_format,
                                               plot_aspect, loc_of_nffgs,
                                               nffg_prefix, nffg_suffix)

if __name__ == '__main__':
  main(sys.argv[1:])
