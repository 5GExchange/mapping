#!/usr/bin/python

import matplotlib.pyplot as plt
from matplotlib import *
import sys, getopt
import copy
import time
import datetime
import random
import sys
import os
import re


def get_data(file_list, type, start, finish, nice):
    mapped_reqs, running_reqs, refused_reqs = [], [], []
    mapped_requests_dict = dict()
    mapped_requests_dict["request_list"] = []
    mapped_requests_dict["incoming_time"] = []
    mapped_requests_dict["name"] = ""
    running_requests_dict = dict()
    running_requests_dict["request_list"] = []
    running_requests_dict["incoming_time"] = []
    running_requests_dict["name"] = ""
    refused_requests_dict = dict()
    refused_requests_dict["request_list"] = []
    refused_requests_dict["incoming_time"] = []
    refused_requests_dict["name"] = ""
    file_list_iter = 0

    for element in file_list:
        start_time, data_point_count = 0, 0
        name = ""
        if isinstance(element, basestring) or len(element) == 1:
            if not isinstance(element, basestring):
                element = str(element[0])
            for line in open(element):
                if start_time == 0:
                    start_time = datetime.datetime.strptime(line[:22], '%Y-%m-%d %H:%M:%S,%f')
                if "| Orchestrator:" in line:
                    name = line[line.find("| Orchestrator:")+15:]
                if "| What to optimize:" in line:
                    name += "_" + line[line.find("| What to optimize:")+19:]
                if "| When to optimize:" in line:
                    name += "_" + line[line.find("| When to optimize:")+19:]
                if "| Optimize strategy:" in line:
                    name += "_" + line[line.find("| Optimize strategy:")+20:]
                if "Mapped service_requests count:" in line:
                    data_point_count += 1
                if start <= data_point_count <= finish:
                    if "Mapped service_requests count:" in line:
                        count = line[line.find("Mapped service_requests count:")+31:]
                        mapped_requests_dict["request_list"].append(int(count))
                        sec = ((datetime.datetime.strptime(line[:22], '%Y-%m-%d %H:%M:%S,%f')) - start_time).total_seconds()
                        mapped_requests_dict["incoming_time"].append(sec)
                    elif "Running service_requests count:" in line:
                        count = line[line.find("Running service_requests count:")+32:]
                        running_requests_dict["request_list"].append(int(count))
                        sec = ((datetime.datetime.strptime(line[:22], '%Y-%m-%d %H:%M:%S,%f')) - start_time).total_seconds()
                        running_requests_dict["incoming_time"].append(sec)
                    elif "Refused service_requests count:" in line:
                        count = line[line.find("Refused service_requests count:")+32:]
                        refused_requests_dict["request_list"].append(int(count))
                        sec = ((datetime.datetime.strptime(line[:22], '%Y-%m-%d %H:%M:%S,%f')) - start_time).total_seconds()
                        refused_requests_dict["incoming_time"].append(sec)

            mapped_requests_dict["name"] = (name+"_"+str(file_list[file_list_iter])).replace("\n", "")
            mapped_reqs.append(copy.copy(mapped_requests_dict))
            mapped_requests_dict["name"] = ""
            mapped_requests_dict["request_list"] = []
            mapped_requests_dict["incoming_time"] = []

            running_requests_dict["name"] = (name+"_"+str(file_list[file_list_iter])).replace("\n", "")
            running_reqs.append(copy.copy(running_requests_dict))
            running_requests_dict["name"] = ""
            running_requests_dict["request_list"] = []
            running_requests_dict["incoming_time"] = []

            refused_requests_dict["name"] = (name+"_"+str(file_list[file_list_iter])).replace("\n", "")
            refused_reqs.append(copy.copy(refused_requests_dict))
            refused_requests_dict["name"] = ""
            refused_requests_dict["request_list"] = []
            refused_requests_dict["incoming_time"] = []

        else:
            start_time, data_point_count = 0, 0
            name = ""
            mapped_reqs_to_avg, running_reqs_to_avg, refused_reqs_to_avg = [], [], []

            for file in element:
                mapped_requests_dict["name"] = ""
                mapped_requests_dict["request_list"] = []
                mapped_requests_dict["incoming_time"] = []
                running_requests_dict["name"] = ""
                running_requests_dict["request_list"] = []
                running_requests_dict["incoming_time"] = []
                refused_requests_dict["name"] = ""
                refused_requests_dict["request_list"] = []
                refused_requests_dict["incoming_time"] = []
                data_point_count = 0
                for line in open(file):
                    if start_time == 0:
                        start_time = datetime.datetime.strptime(line[:22], '%Y-%m-%d %H:%M:%S,%f')
                    if "| Orchestrator:" in line:
                        name = line[line.find("| Orchestrator:") + 15:]
                    if "| What to optimize:" in line:
                        name += "_" + line[line.find("| What to optimize:") + 19:]
                    if "| When to optimize:" in line:
                        name += "_" + line[line.find("| When to optimize:") + 19:]
                    if "| Optimize strategy:" in line:
                        name += "_" + line[line.find("| Optimize strategy:") + 20:]
                    if "Mapped service_requests count:" in line:
                        data_point_count += 1
                    if start <= data_point_count <= finish:
                        if "Mapped service_requests count:" in line:
                            count = line[line.find("Mapped service_requests count:") + 31:]
                            mapped_requests_dict["request_list"].append(int(count))
                            sec = ((datetime.datetime.strptime(line[:22],
                                                               '%Y-%m-%d %H:%M:%S,%f')) - start_time).total_seconds()
                            mapped_requests_dict["incoming_time"].append(sec)
                        elif "Running service_requests count:" in line:
                            count = line[line.find("Running service_requests count:") + 32:]
                            running_requests_dict["request_list"].append(int(count))
                            sec = ((datetime.datetime.strptime(line[:22],
                                                               '%Y-%m-%d %H:%M:%S,%f')) - start_time).total_seconds()
                            running_requests_dict["incoming_time"].append(sec)
                        elif "Refused service_requests count:" in line:
                            count = line[line.find("Refused service_requests count:") + 32:]
                            refused_requests_dict["request_list"].append(int(count))
                            sec = ((datetime.datetime.strptime(line[:22],
                                                               '%Y-%m-%d %H:%M:%S,%f')) - start_time).total_seconds()
                            refused_requests_dict["incoming_time"].append(sec)

                mapped_requests_dict["name"] = (name + "_AVG_" + str(file_list[file_list_iter])).replace("\n", "")
                mapped_reqs_to_avg.append(copy.copy(mapped_requests_dict))

                running_requests_dict["name"] = (name + "_AVG_" + str(file_list[file_list_iter])).replace("\n", "")
                running_reqs_to_avg.append(copy.copy(running_requests_dict))

                refused_requests_dict["name"] = (name + "_AVG_" + str(file_list[file_list_iter])).replace("\n", "")
                refused_reqs_to_avg.append(copy.copy(refused_requests_dict))

            # Average dicts
            avg_mapped_requests_dict = dict()
            avg_mapped_requests_dict["request_list"] = []
            avg_mapped_requests_dict["incoming_time"] = []
            avg_mapped_requests_dict["name"] = ""
            avg_running_requests_dict = dict()
            avg_running_requests_dict["request_list"] = []
            avg_running_requests_dict["incoming_time"] = []
            avg_running_requests_dict["name"] = ""
            avg_refused_requests_dict = dict()
            avg_refused_requests_dict["request_list"] = []
            avg_refused_requests_dict["incoming_time"] = []
            avg_refused_requests_dict["name"] = ""

            inc_summa, req_summa, log_file_counter = 0, 0, 0

            for i in range(0, len(mapped_reqs_to_avg[0]["request_list"])):
                for m in mapped_reqs_to_avg:
                    inc_summa += m["incoming_time"][i]
                    req_summa += m["request_list"][i]
                    log_file_counter += 1
                avg_mapped_requests_dict["incoming_time"].append(round(inc_summa / log_file_counter, 2))
                avg_mapped_requests_dict["request_list"].append(round(req_summa / log_file_counter, 2))
                avg_mapped_requests_dict["name"] = mapped_reqs_to_avg[0]["name"]
                inc_summa, req_summa, log_file_counter = 0, 0, 0

            for i in range(0, len(running_reqs_to_avg[0]["request_list"])):
                for m in running_reqs_to_avg:
                    inc_summa += m["incoming_time"][i]
                    req_summa += m["request_list"][i]
                    log_file_counter += 1
                avg_running_requests_dict["incoming_time"].append(round(inc_summa / log_file_counter, 2))
                avg_running_requests_dict["request_list"].append(round(req_summa / log_file_counter, 2))
                avg_running_requests_dict["name"] = running_reqs_to_avg[0]["name"]
                inc_summa, req_summa, log_file_counter = 0, 0, 0

            for i in range(0, len(refused_reqs_to_avg[0]["request_list"])):
                for m in running_reqs_to_avg:
                    inc_summa += m["incoming_time"][i]
                    req_summa += m["request_list"][i]
                    log_file_counter += 1
                avg_refused_requests_dict["incoming_time"].append(round(inc_summa / log_file_counter, 2))
                avg_refused_requests_dict["request_list"].append(round(req_summa / log_file_counter, 2))
                avg_refused_requests_dict["name"] = refused_reqs_to_avg[0]["name"]
                inc_summa, req_summa, log_file_counter = 0, 0, 0

            mapped_reqs.append(copy.copy(avg_mapped_requests_dict))
            running_reqs.append(copy.copy(avg_running_requests_dict))
            refused_reqs.append(copy.copy(avg_refused_requests_dict))

        file_list_iter += 1

    return mapped_reqs, running_reqs, refused_reqs


def separate_and_avg(log_files):
    # Separate
    result = []
    if "[" in log_files:
        avg_log_files = log_files.split(",")

        # where are [ and ] characters:
        start = [i for i, s in enumerate(avg_log_files) if '[' in s]
        end = [i for i, s in enumerate(avg_log_files) if ']' in s]

        if len(start) != len(end):
            print("The number of [ and ] is not equal!!")
            raise

        # delete special characters:
        avg_log_files = ([s.replace('[', '') for s in avg_log_files])
        avg_log_files = ([s.replace(']', '') for s in avg_log_files])

        # merge those items in the list that were in the same parentheses
        correction = 0
        for k in range(0, len(start)):
            avg_log_files[(start[k]-correction):(end[k]+1-correction)] = \
                [','.join(avg_log_files[(start[k]-correction):(end[k]+1-correction)])]
            correction += end[k] - start[k]

        for element in avg_log_files:
            while "." in element:
                tmp_element = []
                element = element.split(",")
                for i in element:
                    if i!='':
                        tmp_element.append(i)
                        element = tmp_element
                result.append(element)
        return result
    else:
        return log_files.split(",")


def main(argv):
    mapped_online_req_list = None
    mapped_offline_req_list = None
    mapped_hybrid_req_list = None
    running_online_req_list = None
    running_offline_req_list = None
    running_hybrid_req_list = None
    refused_online_req_list = None
    refused_offline_req_list = None
    refused_hybrid_req_list = None

    start_count = 0
    finish_count = float('inf')
    path = ""
    nice, nolegend = False, False
    format = "png"
    mark_every = 50
    marker_size = 4
    try:
        opts, args = getopt.getopt(argv, "hs:f:", ["online_log_files=", "offline_log_files=", "hybrid_log_files=",
                                                   "dir=", "nice", "format=", "nolegend", "markersize=",
                                                   "markevery=", "s=", "f="])
    except getopt.GetoptError:
        print 'Invalid argument!!!  create_plots.py ' \
              '--online_log_files=<online_log_file1,[online_log_file2,online_log_file3],' \
              'online_log_file4 ...> --offline_log_files=<offline_log_file1,offline_log_file2,...> ' \
              '--hybrid_log_files=<hybrid_log_file1,hybrid_log_file2,...> ' \
              '--dir=<directory name> --s=<start of interval> --f=<end of interval> --nice --format=<pdf or png> ' \
              '--nolegend --markersize=<recommended:5> --markevery=<recommended:40-70>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'create_plots.py ' \
              '--online_log_files=<online_log_file1,[online_log_file2,online_log_file3],' \
              'online_log_file4 ...> --offline_log_files=<offline_log_file1,offline_log_file2,...> ' \
              '--hybrid_log_files=<hybrid_log_file1,hybrid_log_file2,...> ' \
              '--dir=<directory name> --s=<start of interval> --f=<end of interval> --nice --format=<pdf or png> ' \
              '--nolegend --markersize=<recommended:5> --markevery=<recommended:40-70>'
            sys.exit()
        elif opt in ("--online_log_files="):
            online_log_files = arg
        elif opt in ("--offline_log_files="):
            offline_log_files = arg
        elif opt in ("--hybrid_log_files="):
            hybrid_log_files = arg
        elif opt in ("--dir="):
            path = arg
        elif opt in ("--s="):
            start_count = int(arg)
        elif opt in ("--f="):
            finish_count = int(arg)
        elif opt in ("--nice"):
            nice = True
        elif opt in ("--nolegend"):
            nolegend = True
        elif opt in ("--format="):
            if arg == "pdf" or arg == "png":
                format = arg
            else:
                print 'Invalid format! Only pdf or png!'
                sys.exit()
        elif opt in ("--markersize="):
            marker_size = int(arg)
        elif opt in ("--markevery="):
            mark_every = int(arg)
        else:
            print 'Bad parameters! Use python create_plots.py --help'
            sys.exit()

    try:
        online_files = separate_and_avg(online_log_files)
        mapped_online_req_list, running_online_req_list, refused_online_req_list = \
            get_data(online_files, "Online", start_count, finish_count, nice)

    except Exception as e:
        print e
        print "The program runs without online log file."

    try:
        offline_files = separate_and_avg(offline_log_files)
        mapped_offline_req_list, running_offline_req_list, refused_offline_req_list = \
            get_data(offline_files, "Offline", start_count, finish_count, nice)
    except Exception as e:
        print e
        print "The program runs without offline log file."

    try:
        hybrid_files = separate_and_avg(hybrid_log_files)
        mapped_hybrid_req_list, running_hybrid_req_list, refused_hybrid_req_list = \
            get_data(hybrid_files, "Hybrid", start_count, finish_count, nice)
    except Exception as e:
        print e
        print "The program runs without hybrid log file."

    if path == "":
       raise ValueError("Have to give a saving directory! Example: --dir=test100")

    if not os.path.exists(path):
        os.mkdir(path)
    if path[:-1] != "/":
        path = path + "/"

    colors_ls = ['red', 'blue', 'green', 'yellow', 'skyblue', 'yellowgreen', 'black', 'orange', 'magenta', 'slategray']
    lines_ls = [[8, 4, 2, 4, 2, 4], [4, 2], [], [8, 4, 4, 2], [8, 4, 2, 4], [5, 2, 10, 5], []]
    markers_ls = ['o', 'v', '+', 's', '*', '', '|', 'x']
    colors_iter = iter(['red', 'blue', 'green', 'yellow', 'skyblue', 'yellowgreen', 'black', 'orange', 'magenta', 'slategray'])
    lines_iter = iter([[8, 4, 2, 4, 2, 4], [4, 2], [], [8, 4, 4, 2], [8, 4, 2, 4], [5, 2, 10, 5], []])
    markers_iter = iter(['o', 'v', '+', 's', '*', '', '|', 'x'])
    ticks = []

    on_act_colors, on_act_lines, on_act_marker, off_act_colors, off_act_lines, off_act_marker, hy_act_colors, \
                                                    hy_act_lines, hy_act_marker = [], [], [], [], [], [], [], [], []

    # Create mapped picture
    if mapped_online_req_list is not None:
        for element in mapped_online_req_list:
            try:
                color = colors_iter.next()
            except:
                color = random.choice(colors_ls)
            try:
                line = lines_iter.next()
            except:
                line = random.choice(lines_ls)
            try:
                marker = markers_iter.next()
            except:
                marker = random.choice(markers_ls)
            finally:
                on_act_marker.append(marker)
                on_act_colors.append(color)
                on_act_lines.append(line)

            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color,
                         label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                         markevery=mark_every)

    if mapped_offline_req_list is not None:
        for element in mapped_offline_req_list:
            try:
                color = colors_iter.next()
            except:
                color = random.choice(colors_ls)
            try:
                line = lines_iter.next()
            except:
                line = random.choice(lines_ls)
            try:
                marker = markers_iter.next()
            except:
                marker = random.choice(markers_ls)
            finally:
                off_act_marker.append(marker)
                off_act_colors.append(color)
                off_act_lines.append(line)

            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)

    if mapped_hybrid_req_list is not None:
        for element in mapped_hybrid_req_list:
            try:
                color = colors_iter.next()
            except:
                color = random.choice(colors_ls)
            try:
                line = lines_iter.next()
            except:
                line = random.choice(lines_ls)
            try:
                marker = markers_iter.next()
            except:
                marker = random.choice(markers_ls)
            finally:
                hy_act_marker.append(marker)
                hy_act_colors.append(color)
                hy_act_lines.append(line)

            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)

    plt.grid('on')
    plt.title('Accepted incoming service requests')
    plt.ylabel('Accepted requests count')
    plt.xlabel('Incoming requests')
    plt.xticks()

    if start_count != 0 or finish_count != float('inf'):
        plt.xlim(xmin=start_count, xmax=finish_count)

    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1), numpoints=1)
    if nolegend:
        plt.legend().set_visible(False)

    plt.savefig(path + "mapped_requests" + str(time.ctime()).replace(' ', '_').replace(':', '-') + "." + format,
                bbox_extra_artists=(lgd,), bbox_inches='tight')
    plt.clf()

    # Create mapped picture with time axis
    if mapped_online_req_list is not None:
        i = 0
        for element in mapped_online_req_list:
            color = on_act_colors[i]
            line = on_act_lines[i]
            marker = on_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    if mapped_offline_req_list is not None:
        i = 0
        for element in mapped_offline_req_list:
            color = off_act_colors[i]
            line = off_act_lines[i]
            marker = off_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    if mapped_hybrid_req_list is not None:
        i = 0
        for element in mapped_hybrid_req_list:
            color = hy_act_colors[i]
            line = hy_act_lines[i]
            marker = hy_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    plt.grid('on')
    plt.title('Accepted incoming service requests')
    plt.ylabel('Accepted requests count')
    plt.xlabel('Sec')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1), numpoints=1)

    #TODO: fix zoom with time axis too
    if nolegend:
        plt.legend().set_visible(False)
    plt.savefig(path + "mapped_requests_with_time_axis_" +
                str(time.ctime()).replace(' ', '_').replace(':', '-') + "." + format,
                bbox_extra_artists=(lgd,), bbox_inches='tight')

    plt.clf()

    # Create Running picture
    if running_online_req_list is not None:
        i = 0
        for element in running_online_req_list:
            color = on_act_colors[i]
            line = on_act_lines[i]
            marker = on_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    if running_offline_req_list is not None:
        i = 0
        for element in running_offline_req_list:
            color = off_act_colors[i]
            line = off_act_lines[i]
            marker = off_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    if running_hybrid_req_list is not None:
        i = 0
        for element in running_hybrid_req_list:
            color = hy_act_colors[i]
            line = hy_act_lines[i]
            marker = hy_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    plt.grid('on')
    plt.title('Currently running (mapped) requests in the NFFG')
    plt.ylabel('Requests count')
    plt.xlabel('Incoming requests')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1), numpoints=1)
    if start_count != 0 or finish_count != float('inf'):
        plt.xlim(xmin=start_count, xmax=finish_count)
    if nolegend:
        plt.legend().set_visible(False)
    plt.savefig(path + "running_requests" + str(time.ctime()). \
                replace(' ', '_').replace(':', '-') + "." + format, bbox_extra_artists=(lgd,), bbox_inches='tight')
    plt.clf()

    # Create Running picture with time axis
    if running_online_req_list is not None:
        i = 0
        for element in running_online_req_list:
            color = on_act_colors[i]
            line = on_act_lines[i]
            marker = on_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80],
                     dashes=line, marker=marker, markersize=marker_size, markevery=mark_every)
            i += 1

    if running_offline_req_list is not None:
        i = 0
        for element in running_offline_req_list:
            color = off_act_colors[i]
            line = off_act_lines[i]
            marker = off_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    if running_hybrid_req_list is not None:
        i = 0
        for element in running_hybrid_req_list:
            color = hy_act_colors[i]
            line = hy_act_lines[i]
            marker = hy_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    plt.grid('on')
    plt.title('Currently running (mapped) requests in the NFFG')
    plt.ylabel('Requests count')
    plt.xlabel('Sec')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1), numpoints=1)
    if nolegend:
        plt.legend().set_visible(False)
    # TODO: fix zoom with time axis too
    plt.savefig(path + "running_requests_with_time_axis" + str(time.ctime()). \
                replace(' ', '_').replace(':', '-') + "." + format, bbox_extra_artists=(lgd,), bbox_inches='tight')
    plt.clf()

    # Create refused picture
    if refused_online_req_list is not None:
        i = 0
        for element in refused_online_req_list:
            color = on_act_colors[i]
            line = on_act_lines[i]
            marker = on_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    if refused_offline_req_list is not None:
        i = 0
        for element in refused_offline_req_list:
            color = off_act_colors[i]
            line = off_act_lines[i]
            marker = off_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    if refused_hybrid_req_list is not None:
        i = 0
        for element in refused_hybrid_req_list:
            color = hy_act_colors[i]
            line = hy_act_lines[i]
            marker = hy_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    plt.title('Refused requests during the simulation')
    plt.ylabel('Refused requests count')
    plt.xlabel('Incoming requests')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1), numpoints=1)
    if start_count != 0 or finish_count != float('inf'):
        plt.xlim(xmin=start_count, xmax=finish_count)
    if nolegend:
        plt.legend().set_visible(False)
    plt.grid('on')

    plt.savefig(path + "refused_requests" + str(time.ctime()). \
                replace(' ', '_').replace(':', '-') + "." + format, bbox_extra_artists=(lgd,), bbox_inches='tight')
    plt.clf()

    # Create refused picture with time
    if refused_online_req_list is not None:
        i = 0
        for element in refused_online_req_list:
            color = on_act_colors[i]
            line = on_act_lines[i]
            marker = on_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    if refused_offline_req_list is not None:
        i = 0
        for element in refused_offline_req_list:
            color = off_act_colors[i]
            line = off_act_lines[i]
            marker = off_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    if refused_hybrid_req_list is not None:
        i = 0
        for element in refused_hybrid_req_list:
            color = hy_act_colors[i]
            line = hy_act_lines[i]
            marker = hy_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color,
                     label=element["name"].replace('/', '_')[:80], dashes=line, marker=marker, markersize=marker_size,
                     markevery=mark_every)
            i += 1

    plt.grid('on')
    plt.title('Refused requests during the simulation')
    plt.ylabel('Refused requests count')
    plt.xlabel('Sec')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1), numpoints=1)
    if nolegend:
        plt.legend().set_visible(False)
    # TODO: fix zoom with time axis too
    plt.savefig(path + "refused_requests_with_time_axis" + str(time.ctime()). \
                replace(' ', '_').replace(':', '-') + "." + format, bbox_extra_artists=(lgd,), bbox_inches='tight')

    print("Creating plots are DONE :)")

if __name__ == "__main__":
   main(sys.argv[1:])
