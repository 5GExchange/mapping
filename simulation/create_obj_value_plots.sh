#!/usr/bin/env bash

# usage: ./create_obj_value_plots.sh <<obj_values.csv>> <<simulation_log.err>> <<output file name>>

cat $2 | grep -e "DEBUG: Hybrid Orchestrator:Setting online resource based on reoptimized resource for request" |
cut -d ' ' -f12 | cut -d '-' -f3 | awk '{print $1,",",2}' > reopts.txt

gnuplot <<- EOF
    set xlabel "Number of simulation iterations"
    set ylabel "Objective function value"
    set term pdf
    set datafile separator ","
    set boxwidth 0.01
    set output "$3.pdf"
    plot "$1" using 1:4 with linespoint title "Total", "$1" using 1:2 with linespoint title "Link bandwidth component", \
    "$1" using 1:3 with linespoint title "Load balancing component", "reopts.txt" using 1:2 with boxes title "Reoptimizations"
EOF

rm reopts.txt