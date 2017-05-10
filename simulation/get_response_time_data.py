#!/usr/bin/python

import sys

# usage: ./get_response_time_data.py output_file_name <<space sepmarated list of stderr or log files>>

if __name__ == '__main__':
    output_data = {}
    for file in sys.argv[:2]:
        output_data[file] = []
        with open(file, "r") as f:
            for line in f:
                if "Time passed with one mapping response:" in line:
                    time_string = line.split(' ')[7]
                    time_float = sum(map(map(time_string.split(' '), float),
                                         (3600.0, 60.0, 1.0), lambda a,b: a*b))
                    output_data[file].append(time_float)

    output_file = sys.argv[1]
    with open(output_file, "w") as output:
        for k,v in output_data.iteritems():
