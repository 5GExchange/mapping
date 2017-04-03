#!/usr/bin/python

import json
import matplotlib.pyplot as plt
import sys, getopt
import copy

def get_data(file_list, type):

    mapped_reqs = []
    running_reqs = []
    refused_reqs = []
    mapped_requests_dict = dict()
    mapped_requests_dict["request_list"] = []
    mapped_requests_dict["name"] = ""
    running_requests_dict = dict()
    running_requests_dict["request_list"] = []
    running_requests_dict["name"] = ""
    refused_requests_dict = dict()
    refused_requests_dict["request_list"] = []
    refused_requests_dict["name"] = ""

    for file in file_list:
        for line in open(file):
            if "Mapped service_requests count:" in line:
                line = line[line.find("Mapped service_requests count:")+31:]
                mapped_requests_dict["request_list"].append(int(line))
            elif "Running service_requests count:" in line:
                line = line[line.find("Running service_requests count:")+32:]
                running_requests_dict["request_list"].append(int(line))
            elif "Refused service_requests count:" in line:
                line = line[line.find("Refused service_requests count:")+32:]
                refused_requests_dict["request_list"].append(int(line))

        mapped_requests_dict["name"] = type+str(file_list.index(file))
        mapped_reqs.append(copy.copy(mapped_requests_dict))
        mapped_requests_dict["name"] = ""
        mapped_requests_dict["request_list"] = []

        running_requests_dict["name"] = type + str(file_list.index(file))
        running_reqs.append(copy.copy(running_requests_dict))
        running_requests_dict["name"] = ""
        running_requests_dict["request_list"] = []

        refused_requests_dict["name"] = type + str(file_list.index(file))
        refused_reqs.append(copy.copy(mapped_requests_dict))
        refused_requests_dict["name"] = ""
        refused_requests_dict["request_list"] = []

    return mapped_reqs, running_reqs, refused_reqs

def separte_files(log_files):

    files = []
    log_files += ","
    while "," in log_files:
        file = log_files[:log_files.find(",")]
        files.append(file)
        log_files = log_files[log_files.find(",") + 1:]

    return files

def main(argv):

    hybridfile = ""
    onlinefile = ""
    offlinefile = ""
    hybrid = False
    online = False
    offline = False
    hybrid_requests = None
    online_requests = None
    offline_requests = None


    try:
        opts, args = getopt.getopt(argv,"h",["online_log_files=","offline_log_files=","hybrid_log_files="])
    except getopt.GetoptError:
        print 'create_plots.py --online_log_files <online_log_file1,online_log_file2, ...> --offline_log_files <offline_log_file1,offline_log_file2, ...> --hybrid_log_files <hybrid_log_file1,hybrid_log_file2, ...>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'create_plots.py --online_log_files <online_log_file1,online_log_file2, ...> --offline_log_files <offline_log_file1,offline_log_file2, ...> --hybrid_log_files <hybrid_log_file1,hybrid_log_file2, ...>'
            sys.exit()
        elif opt in ("--online_log_files="):
            online_log_files = arg
        elif opt in ("--offline_log_files="):
            offline_log_files = arg
        elif opt in ("--hybrid_log_files="):
            hybrid_log_files = arg
        else:
            print 'create_plots.py --online_log_files <online_log_files>'
            sys.exit()

    online_files = separte_files(online_log_files)
    mapped_online_req_list, running_online_req_list,refused_online_req_list = get_data(online_files,"Online")

    offline_files = separte_files(offline_log_files)
    mapped_offline_req_list, running_offline_req_list, refused_offline_req_list = get_data(offline_files, "Offline")

    hybrid_files = separte_files(hybrid_log_files)
    mapped_hybrid_req_list, running_hybrid_req_list, refused_hybrid_req_list = get_data(hybrid_files, "Hybrid")



    #Create mapped picture
    x=[]
    x_list=[]
    if mapped_online_req_list is not 0:
        x_list =  mapped_online_req_list[0]["request_list"]
    elif mapped_offline_req_list is not 0:
        x_list = mapped_offline_req_list[0]["request_list"]
    elif mapped_hybrid_req_list is not 0:
        x_list = mapped_hybrid_req_list[0]["request_list"]
    for i in xrange(1, len(x_list) + 1):
        x.append(i)

    for element in mapped_online_req_list:
        plt.plot(x, element["request_list"],label=element["name"])
    for element in running_offline_req_list:
        plt.plot(x, element["request_list"],label=element["name"])
    for element in running_hybrid_req_list:
        plt.plot(x, element["request_list"],label=element["name"])

    plt.title('Accepted incoming service requests')
    plt.ylabel('Accepted requests count')
    plt.xlabel('Incoming requests')
    plt.legend(loc=3)
    plt.savefig("mapped_requests.png")
    plt.clf()

    #Create Running picture
    for element in running_online_req_list:
        plt.plot(x, element["request_list"],label=element["name"])
    for element in running_offline_req_list:
        plt.plot(x, element["request_list"],label=element["name"])
    for element in running_hybrid_req_list:
        plt.plot(x, element["request_list"],label=element["name"])

    plt.title('Currently running (mapped) requests in the NFFG')
    plt.ylabel('Mapped requests count')
    plt.xlabel('Incoming requests')
    plt.legend(loc=3)
    plt.savefig("running_requests.png")
    plt.clf()


    #Create refused picture
    for element in running_online_req_list:
        plt.plot(x, element["request_list"],label=element["name"])
    for element in running_offline_req_list:
        plt.plot(x, element["request_list"],label=element["name"])
    for element in running_hybrid_req_list:
        plt.plot(x, element["request_list"],label=element["name"])

    plt.title('Refused requests during the simulation')
    plt.ylabel('Refused requests count')
    plt.xlabel('Incoming requests')
    plt.legend(loc=3)
    plt.savefig("refused_requests.png")

    print("DONE")


if __name__ == "__main__":
   main(sys.argv[1:])