#!/usr/bin/python

import matplotlib.pyplot as plt
import sys, getopt
import copy
import time
import datetime
import random
import sys
import os


def get_data(file_list, type, start, finish):
    mapped_reqs = []
    running_reqs = []
    refused_reqs = []
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

    for file in file_list:
        start_time = 0
        name = ""
        data_point_count = 0
        for line in open(file):
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
                
        mapped_requests_dict["name"] = (name+"_"+str(file_list.index(file))).replace("\n","")
        mapped_reqs.append(copy.copy(mapped_requests_dict))
        mapped_requests_dict["name"] = ""
        mapped_requests_dict["request_list"] = []
        mapped_requests_dict["incoming_time"] = []

        running_requests_dict["name"] = (name+"_"+str(file_list.index(file))).replace("\n","")
        running_reqs.append(copy.copy(running_requests_dict))
        running_requests_dict["name"] = ""
        running_requests_dict["request_list"] = []
        running_requests_dict["incoming_time"] = []

        refused_requests_dict["name"] = (name+"_"+str(file_list.index(file))).replace("\n","")
        refused_reqs.append(copy.copy(refused_requests_dict))
        refused_requests_dict["name"] = ""
        refused_requests_dict["request_list"] = []
        refused_requests_dict["incoming_time"] = []

    return mapped_reqs, running_reqs, refused_reqs


def separte_files(log_files, method):
    files = []
    log_files += ","
    while "," in log_files:
        file = log_files[:log_files.find(",")]
        files.append(file)
        print "Read "+method+" file:"+file
        log_files = log_files[log_files.find(",") + 1:]

    return files


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
    
    try:
        opts, args = getopt.getopt(argv, "hs:f:", ["online_log_files=", "offline_log_files=", "hybrid_log_files=", "dir="])
    except getopt.GetoptError:
        print 'create_plots.py --online_log_files=<online_log_file1,online_log_file2,...> ' \
              '--offline_log_files=<offline_log_file1,offline_log_file2,...> ' \
              '--hybrid_log_files=<hybrid_log_file1,hybrid_log_file2,...> ' \
              '--dir=<directory name>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'create_plots.py --online_log_files=<online_log_file1,online_log_file2,...> ' \
                  '--offline_log_files=<offline_log_file1,offline_log_file2,...> ' \
                  '--hybrid_log_files=<hybrid_log_file1,hybrid_log_file2,...> ' \
                  '--dir=<directory name>'
            sys.exit()
        elif opt in ("--online_log_files="):
            online_log_files = arg
        elif opt in ("--offline_log_files="):
            offline_log_files = arg
        elif opt in ("--hybrid_log_files="):
            hybrid_log_files = arg
        elif opt in ("--dir="):
            path = arg
        elif opt == '-s':
            start_count = int(arg)
        elif opt == '-f':
            finish_count = int(arg)
        else:
            print 'Bad parameters! Use python create_plots.py --help'
            sys.exit()

    try:
        online_files = separte_files(online_log_files, "Online")
        mapped_online_req_list, running_online_req_list, refused_online_req_list = get_data(online_files, "Online", start_count, finish_count)
    except Exception as e:
        print e
        print "The program runs without online log file."

    try:
        offline_files = separte_files(offline_log_files, "Offline")
        mapped_offline_req_list, running_offline_req_list, refused_offline_req_list = get_data(offline_files, "Offline", start_count, finish_count)
    except Exception as e:
        print e
        print "The program runs without offline log file."

    try:
        hybrid_files = separte_files(hybrid_log_files, "Hybrid")
        mapped_hybrid_req_list, running_hybrid_req_list, refused_hybrid_req_list = get_data(hybrid_files, "Hybrid", start_count, finish_count)
    except Exception as e:
        print e
        print "The program runs without hybrid log file."

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

    on_act_colors = []
    on_act_lines = []
    on_act_marker = []
    off_act_colors = []
    off_act_lines = []
    off_act_marker = []
    hy_act_colors = []
    hy_act_lines = []
    hy_act_marker = []

    # Create mapped picture
    if mapped_online_req_list is not None:
        for element in mapped_online_req_list:
            try:
                color = colors_iter.next()
            except:
                color = random.choice(colors_ls)
            finally:
                on_act_colors.append(color)
            try:
                line = lines_iter.next()
            except:
                line = random.choice(lines_ls)
            finally:
                on_act_lines.append(line)
            try:
                marker = markers_iter.next()
            except:
                marker = random.choice(markers_ls)
            finally:
                on_act_marker.append(marker)

            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)

    if mapped_offline_req_list is not None:
        for element in mapped_offline_req_list:
            try:
                color = colors_iter.next()
            except:
                color = random.choice(colors_ls)
            finally:
                off_act_colors.append(color)
            try:
                line = lines_iter.next()
            except:
                line = random.choice(lines_ls)
            finally:
                off_act_lines.append(line)
            try:
                marker = markers_iter.next()
            except:
                marker = random.choice(markers_ls)
            finally:
                off_act_marker.append(marker)

            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)

    if mapped_hybrid_req_list is not None:
        for element in mapped_hybrid_req_list:
            try:
                color = colors_iter.next()
            except:
                color = random.choice(colors_ls)
            finally:
                hy_act_colors.append(color)
            try:
                line = lines_iter.next()
            except:
                line = random.choice(lines_ls)
            finally:
                hy_act_lines.append(line)
            try:
                marker = markers_iter.next()
            except:
                marker = random.choice(markers_ls)
            finally:
                hy_act_marker.append(marker)
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
    plt.grid('on')
    plt.title('Accepted incoming service requests')
    plt.ylabel('Accepted requests count')
    plt.xlabel('Incoming requests')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1))
    plt.savefig(path + "mapped_requests" + str(time.ctime()).\
            replace(' ', '_').replace(':', '-') + ".png", bbox_extra_artists=(lgd,), bbox_inches='tight')
    plt.clf()

    # Create mapped picture with time axis
    if mapped_online_req_list is not None:
        i = 0
        for element in mapped_online_req_list:
            color = on_act_colors[i]
            line = on_act_lines[i]
            marker = on_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    if mapped_offline_req_list is not None:
        i = 0
        for element in mapped_offline_req_list:
            color = off_act_colors[i]
            line = off_act_lines[i]
            marker = off_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    if mapped_hybrid_req_list is not None:
        i = 0
        for element in mapped_hybrid_req_list:
            color = hy_act_colors[i]
            line = hy_act_lines[i]
            marker = hy_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    plt.grid('on')
    plt.title('Accepted incoming service requests')
    plt.ylabel('Accepted requests count')
    plt.xlabel('Sec')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1))
    plt.savefig(path + "mapped_requests_with_time_axis_" + str(time.ctime()). \
                replace(' ', '_').replace(':', '-') + ".png", bbox_extra_artists=(lgd,), bbox_inches='tight')
    plt.clf()

    # Create Running picture
    if running_online_req_list is not None:
        i = 0
        for element in running_online_req_list:
            color = on_act_colors[i]
            line = on_act_lines[i]
            marker = on_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    if running_offline_req_list is not None:
        i = 0
        for element in running_offline_req_list:
            color = off_act_colors[i]
            line = off_act_lines[i]
            marker = off_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    if running_hybrid_req_list is not None:
        i = 0
        for element in running_hybrid_req_list:
            color = hy_act_colors[i]
            line = hy_act_lines[i]
            marker = hy_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    plt.grid('on')
    plt.title('Currently running (mapped) requests in the NFFG')
    plt.ylabel('Requests count')
    plt.xlabel('Incoming requests')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1))
    plt.savefig(path + "running_requests" + str(time.ctime()).\
            replace(' ', '_').replace(':', '-') + ".png", bbox_extra_artists=(lgd,), bbox_inches='tight')
    plt.clf()

    # Create Running picture with time axis
    if running_online_req_list is not None:
        i = 0
        for element in running_online_req_list:
            color = on_act_colors[i]
            line = on_act_lines[i]
            marker = on_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    if running_offline_req_list is not None:
        i = 0
        for element in running_offline_req_list:
            color = off_act_colors[i]
            line = off_act_lines[i]
            marker = off_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    if running_hybrid_req_list is not None:
        i = 0
        for element in running_hybrid_req_list:
            color = hy_act_colors[i]
            line = hy_act_lines[i]
            marker = hy_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    plt.grid('on')
    plt.title('Currently running (mapped) requests in the NFFG')
    plt.ylabel('Requests count')
    plt.xlabel('Sec')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1))
    plt.savefig(path + "running_requests_with_time_axis" + str(time.ctime()). \
                replace(' ', '_').replace(':', '-') + ".png", bbox_extra_artists=(lgd,), bbox_inches='tight')
    plt.clf()

    # Create refused picture
    if refused_online_req_list is not None:
        i = 0
        for element in refused_online_req_list:
            color = on_act_colors[i]
            line = on_act_lines[i]
            marker = on_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    if refused_offline_req_list is not None:
        i = 0
        for element in refused_offline_req_list:
            color = off_act_colors[i]
            line = off_act_lines[i]
            marker = off_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    if refused_hybrid_req_list is not None:
        i = 0
        for element in refused_hybrid_req_list:
            color = hy_act_colors[i]
            line = hy_act_lines[i]
            marker = hy_act_marker[i]
            plt.plot(range(0, len(element["request_list"])), element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    plt.title('Refused requests during the simulation')
    plt.ylabel('Refused requests count')
    plt.xlabel('Incoming requests')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1))
    plt.grid('on')

    plt.savefig(path + "refused_requests" + str(time.ctime()).\
            replace(' ', '_').replace(':', '-') + ".png", bbox_extra_artists=(lgd,), bbox_inches='tight')
    plt.clf()

    # Create refused picture with time
    if refused_online_req_list is not None:
        i = 0
        for element in refused_online_req_list:
            color = on_act_colors[i]
            line = on_act_lines[i]
            marker = on_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    if refused_offline_req_list is not None:
        i = 0
        for element in refused_offline_req_list:
            color = off_act_colors[i]
            line = off_act_lines[i]
            marker = off_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    if refused_hybrid_req_list is not None:
        i = 0
        for element in refused_hybrid_req_list:
            color = hy_act_colors[i]
            line = hy_act_lines[i]
            marker = hy_act_marker[i]
            plt.plot(element["incoming_time"], element["request_list"], color=color, label=element["name"],
                     dashes=line, marker=marker, markersize=5, markevery=40)
            i += 1

    plt.grid('on')
    plt.title('Refused requests during the simulation')
    plt.ylabel('Refused requests count')
    plt.xlabel('Sec')
    lgd = plt.legend(loc='upper left', bbox_to_anchor=(0, -0.1))
    plt.savefig(path + "refused_requests_with_time_axis" + str(time.ctime()). \
                replace(' ', '_').replace(':', '-') + ".png", bbox_extra_artists=(lgd,), bbox_inches='tight')

    print("Creating plots are DONE :)")


if __name__ == "__main__":
   main(sys.argv[1:])
