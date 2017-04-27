#!/usr/bin/python

import json
import matplotlib.pyplot as plt
import sys, getopt
import copy
import time
import datetime

def get_data(file_list, type):

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
        for line in open(file):
            if start_time == 0:
                start_time = datetime.datetime.strptime(line[:22], '%Y-%m-%d %H:%M:%S,%f')
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

        mapped_requests_dict["name"] = type+str(file_list.index(file))
        mapped_reqs.append(copy.copy(mapped_requests_dict))
        mapped_requests_dict["name"] = ""
        mapped_requests_dict["request_list"] = []
        mapped_requests_dict["incoming_time"] = []

        running_requests_dict["name"] = type + str(file_list.index(file))
        running_reqs.append(copy.copy(running_requests_dict))
        running_requests_dict["name"] = ""
        running_requests_dict["request_list"] = []
        running_requests_dict["incoming_time"] = []

        refused_requests_dict["name"] = type + str(file_list.index(file))
        refused_reqs.append(copy.copy(refused_requests_dict))
        refused_requests_dict["name"] = ""
        refused_requests_dict["request_list"] = []
        refused_requests_dict["incoming_time"] = []

    return mapped_reqs, running_reqs, refused_reqs

def separte_files(log_files,method):

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

    try:
        for param in argv:
            if param[0:2] != "--":
                print 'Bad parameter: '+str(param)+'\nUse "python create_plots.py --help"'
                sys.exit()
        opts, args = getopt.getopt(argv,"h",["online_log_files=","offline_log_files=","hybrid_log_files=","bad_log"])
    except getopt.GetoptError:
        print 'create_plots.py --online_log_files=<online_log_file1,online_log_file2,...> --offline_log_files=<offline_log_file1,offline_log_file2,...> --hybrid_log_files=<hybrid_log_file1,hybrid_log_file2,...> --bad_log'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'create_plots.py --online_log_files=<online_log_file1,online_log_file2, ...> --offline_log_files=<offline_log_file1,offline_log_file2, ...> --hybrid_log_files=<hybrid_log_file1,hybrid_log_file2, ...> --bad_log'
            sys.exit()
        elif opt in ("--online_log_files="):
            online_log_files = arg
        elif opt in ("--offline_log_files="):
            offline_log_files = arg
        elif opt in ("--hybrid_log_files="):
            hybrid_log_files = arg
        else:
            print 'Bad parameters! Use python create_plots.py --help'
            sys.exit()

    try:
        online_files = separte_files(online_log_files,"Online")
        mapped_online_req_list, running_online_req_list,refused_online_req_list = get_data(online_files,"Online")
    except Exception as e:
        print e
        print "The program runs without online log file."

    try:
        offline_files = separte_files(offline_log_files,"Offline")
        mapped_offline_req_list, running_offline_req_list, refused_offline_req_list = get_data(offline_files, "Offline")
    except Exception as e:
        print e
        print "The program runs without offline log file."

    try:
        hybrid_files = separte_files(hybrid_log_files,"Hybrid")
        mapped_hybrid_req_list, running_hybrid_req_list, refused_hybrid_req_list = get_data(hybrid_files, "Hybrid")
    except Exception as e:
        print e
        print "The program runs without hybrid log file."

    """
    mapped_requests_dict = dict()
    mapped_requests_dict["request_list"] = []
    mapped_requests_dict["name"] = ""
    """

    #Create mapped picture
    if mapped_online_req_list is not None:
        for element in mapped_online_req_list:
            plt.plot(range(0,len(element["request_list"])), element["request_list"],label=element["name"])
    if mapped_offline_req_list is not None:
        for element in mapped_offline_req_list:
            plt.plot(range(0,len(element["request_list"])), element["request_list"],label=element["name"])
    if mapped_hybrid_req_list is not None:
        for element in mapped_hybrid_req_list:
            plt.plot(range(0,len(element["request_list"])), element["request_list"],label=element["name"])

    plt.title('Accepted incoming service requests')
    plt.ylabel('Accepted requests count')
    plt.xlabel('Incoming requests')
    plt.legend(loc=4)
    plt.savefig("mapped_requests" +  str (time.ctime()).\
            replace(' ', '_').replace(':', '-') + ".png")
    plt.clf()

    # Create mapped picture with time axis
    if mapped_online_req_list is not None:
        for element in mapped_online_req_list:
            plt.plot(element["incoming_time"], element["request_list"], label=element["name"])
    if mapped_offline_req_list is not None:
        for element in mapped_offline_req_list:
            plt.plot(element["incoming_time"], element["request_list"], label=element["name"])
    if mapped_hybrid_req_list is not None:
        for element in mapped_hybrid_req_list:
            plt.plot(element["incoming_time"], element["request_list"], label=element["name"])

    plt.title('Accepted incoming service requests')
    plt.ylabel('Accepted requests count')
    plt.xlabel('Sec')
    plt.legend(loc=4)
    plt.savefig("mapped_requests_with_time_axis_" + str(time.ctime()). \
                replace(' ', '_').replace(':', '-') + ".png")
    plt.clf()

    #Create Running picture
    if running_online_req_list is not None:
        for element in running_online_req_list:
            plt.plot(range(0,len(element["request_list"])), element["request_list"],label=element["name"])
    if running_offline_req_list is not None:
        for element in running_offline_req_list:
            plt.plot(range(0,len(element["request_list"])), element["request_list"],label=element["name"])
    if running_hybrid_req_list is not None:
        for element in running_hybrid_req_list:
            plt.plot(range(0,len(element["request_list"])), element["request_list"],label=element["name"])

    plt.title('Currently running (mapped) requests in the NFFG')
    plt.ylabel('Requests count')
    plt.xlabel('Incoming requests')
    plt.legend(loc=4)
    plt.savefig("running_requests" +  str (time.ctime()).\
            replace(' ', '_').replace(':', '-') + ".png")
    plt.clf()

    # Create Running picture with time axis
    if running_online_req_list is not None:
        for element in running_online_req_list:
            plt.plot(element["incoming_time"], element["request_list"], label=element["name"])
    if running_offline_req_list is not None:
        for element in running_offline_req_list:
            plt.plot(element["incoming_time"], element["request_list"], label=element["name"])
    if running_hybrid_req_list is not None:
        for element in running_hybrid_req_list:
            plt.plot(element["incoming_time"], element["request_list"], label=element["name"])

    plt.title('Currently running (mapped) requests in the NFFG')
    plt.ylabel('Requests count')
    plt.xlabel('Sec')
    plt.legend(loc=4)
    plt.savefig("running_requests_with_time_axis" + str(time.ctime()). \
                replace(' ', '_').replace(':', '-') + ".png")
    plt.clf()


    #Create refused picture
    if refused_online_req_list is not None:
        for element in refused_online_req_list:
            plt.plot(range(0,len(element["request_list"])), element["request_list"],label=element["name"])
    if refused_offline_req_list is not None:
        for element in refused_offline_req_list:
            plt.plot(range(0,len(element["request_list"])), element["request_list"],label=element["name"])
    if refused_hybrid_req_list is not None:
        for element in refused_hybrid_req_list:
            plt.plot(range(0,len(element["request_list"])), element["request_list"],label=element["name"])

    plt.title('Refused requests during the simulation')
    plt.ylabel('Refused requests count')
    plt.xlabel('Incoming requests')
    plt.legend(loc=4)
    plt.savefig("refused_requests" +  str (time.ctime()).\
            replace(' ', '_').replace(':', '-') + ".png")

    # Create refused picture with time
    if refused_online_req_list is not None:
        for element in refused_online_req_list:
            plt.plot(element["incoming_time"], element["request_list"], label=element["name"])
    if refused_offline_req_list is not None:
        for element in refused_offline_req_list:
            plt.plot(element["incoming_time"], element["request_list"], label=element["name"])
    if refused_hybrid_req_list is not None:
        for element in refused_hybrid_req_list:
            plt.plot(element["incoming_time"], element["request_list"], label=element["name"])

    plt.title('Refused requests during the simulation')
    plt.ylabel('Refused requests count')
    plt.xlabel('Sec')
    plt.legend(loc=4)
    plt.savefig("refused_requests_with_time_axis" + str(time.ctime()). \
                replace(' ', '_').replace(':', '-') + ".png")

    print("Creating plots are DONE :)")


if __name__ == "__main__":
   main(sys.argv[1:])