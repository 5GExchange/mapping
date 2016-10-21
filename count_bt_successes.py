# Copyright (c) 2016 Balazs Nemeth
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
Calculates the average of how many SG-s could the Alg1 map with a specific
backtracking depth, measured with the 100 seeds.
"""

top_success = {}
mins = {}
maxs = {}
for bt in xrange(4,15):
  top_success[bt] = []
  mins[bt] = float("inf")
  maxs[bt] = 0
  base = "milp-tests/lab27/gw-small-4.0batched-seed0-100-bt%s-3.out"%bt
  with open(base, "r") as f:
    for line in f:
      line = line.split(" ")
      if line[0] == "Command":
        nextline = next(f).rstrip('\n').split(' ')
        if nextline[0] == "WARNING:StressTest:Peak":
          test_lvl = int(nextline[12].rstrip('.0'))
          top_success[bt].append(test_lvl)
          if mins[bt] > test_lvl:
            mins[bt] = test_lvl
          if maxs[bt] < test_lvl:
            maxs[bt] = test_lvl
       
# Find the limits around the average which contains p*100% of the elements.
p = 0.7
for bt in top_success:
  top_success[bt] = sorted(top_success[bt])
  mins[bt] = top_success[bt][int((0.5 - p/2.0)*len(top_success[bt]))]
  maxs[bt] = top_success[bt][int((0.5 + p/2.0)*len(top_success[bt]))]

avg_test_lvl = {}
for bt in top_success:
  avg_test_lvl[bt] = float(sum (top_success[bt])) / len(top_success[bt])

print "backtrack_depth, avg_test_lvl, %sth_percentile_test_lvl, "\
  "%sth_percentile_test_lvl"%(int((0.5 - p/2.0)*100), int((0.5 + p/2.0)*100))
for bt, test_lvl in avg_test_lvl.iteritems():
  print "%s, %s, %s, %s"%(bt, test_lvl, mins[bt], maxs[bt])
