#!/usr/bin/python

import json
import matplotlib.pyplot as plt
import sys, getopt

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
        opts, args = getopt.getopt(argv,"h",["hybrid_file=","online_file=","offline_file="])
    except getopt.GetoptError:
        print 'create_plots.py --hybrid_file <hybrid_inputfile> --online_file <online_inputfile> --offline_file <offline_inputfile>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'create_plots.py --hybrid_file <hybrid_inputfile> --online_file <online_inputfile> --offline_file <offline_inputfile>'
            sys.exit()
        elif opt in ("--hybrid_file"):
            hybridfile = arg
        elif opt in ("--online_file"):
            onlinefile = arg
        elif opt in ("--offline_file"):
            offlinefile = arg

    try:
        with open(hybridfile) as data_file:
            hybrid_requests = json.load(data_file)
            hybrid = True
    except:
        pass

    try:
        with open(onlinefile) as data_file:
            online_requests = json.load(data_file)
            online = True
    except:
        pass

    try:
        with open(offlinefile) as data_file:
            offline_requests = json.load(data_file)
            offline = True
    except:
        pass

    #Create mapped picture

    x=[]
    for i in xrange(0,len(hybrid_requests['running_requests'])):
        x.append(i)

    if hybrid:
        plt.plot(x, hybrid_requests['running_requests'],label="hybrid")

    if online:
        plt.plot(x, online_requests['running_requests'],label="online")

    if offline:
        plt.plot(x, offline_requests['running_requests'],label="offline")

    plt.title('Accepted incoming service requests')
    plt.ylabel('Accepted requests count')
    plt.xlabel('Incoming requests')
    plt.legend(loc=3)
    plt.savefig("mapped_requests.png")
    plt.clf()

    #Create Running picture
    x=[]
    for i in xrange(0,len(hybrid_requests['running_requests'])):
        x.append(i)

    if hybrid:
        plt.plot(x, hybrid_requests['running_requests'],label="hybrid")

    if online:
        plt.plot(x, online_requests['running_requests'],label="online")

    if offline:
        plt.plot(x, offline_requests['running_requests'],label="offline")

    plt.plot(x,hybrid_requests['running_requests'])
    plt.title('Currently running (mapped) requests in the NFFG')
    plt.ylabel('Mapped requests count')
    plt.xlabel('Incoming requests')
    plt.legend(loc=3)
    plt.savefig("running_requests.png")
    plt.clf()


    #Create refused picture
    x=[]
    for i in xrange(0,len(hybrid_requests['refused_requests'])):
        x.append(i)

    if hybrid:
        plt.plot(x, hybrid_requests['refused_requests'],label="hybrid")

    if online:
        plt.plot(x, online_requests['refused_requests'],label="online")

    if offline:
        plt.plot(x, offline_requests['refused_requests'],label="offline")

    plt.plot(x,hybrid_requests['refused_requests'])
    plt.title('Refused requests during the simulation')
    plt.ylabel('Refused requests count')
    plt.xlabel('Incoming requests')
    plt.legend(loc=3)
    plt.savefig("refused_requests.png")

    print("DONE")


if __name__ == "__main__":
   main(sys.argv[1:])