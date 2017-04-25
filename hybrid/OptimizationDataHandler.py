import os
import copy
import logging
log = logging.getLogger(" OptimizationDataHandler ")


class OptimizationDataHandler():

    def __init__(self, full_log_path, resource_type):
        formatter = logging.Formatter(
            '%(asctime)s | OptimizationDataHandler | %(levelname)s | \t%(message)s')
        hdlr = logging.FileHandler(full_log_path)
        hdlr.setFormatter(formatter)
        log.addHandler(hdlr)
        log.setLevel(logging.DEBUG)

        if not os.path.exists('optimization_data'):
            os.mkdir('optimization_data')

        self.opt_data_path = os.path.abspath('optimization_data') + '/' +\
                                                    resource_type + '.dat'

        # if dat file is not exist
        if not os.path.exists(self.opt_data_path):
            with open(self.opt_data_path, 'w') as file:
                file.write("0 \n")
                file.write("0 \n")

        # if dat file is exist, but it's empty
        if os.stat(self.opt_data_path).st_size == 0:
            with open(self.opt_data_path, 'a') as file:
                file.write("0 \n")
                file.write("0 \n")

        with open(self.opt_data_path, 'r') as file:
            self.number_of_lines = sum (1 for _ in file)

    def get_opt_time(self, target_vnf_number):

        if os.stat(self.opt_data_path).st_size == 0:
            time = 0
            return time
        else:
            with open(self.opt_data_path, 'r') as file:
                lines = file.readlines()

            time = []
            result = 0.0
            id = 0

            vnf_numbers = lines[0].rstrip().split(",")
            opt_times = lines[1].rstrip().split(",")

            # TODO: a kereses intervalluma config fajlbol allithato legyen
            for i in vnf_numbers:

                if int(i) > int(target_vnf_number)-20  and int(i) < int(target_vnf_number) + 20:
                    time.append(opt_times[id])
                id += 1

            for k in time:
                result += int(k)
            return result/len(time)

    def write_data(self, number_of_vnfs, time_of_opt):
        with open(self.opt_data_path, 'r') as file:
            lines = file.readlines()

        lines[0] = lines[0].rstrip()
        lines[0] += ',' + str(number_of_vnfs) + '\n'

        lines[1] = lines[1].rstrip()
        lines[1] += ',' + str(time_of_opt) + '\n'

        with open(self.opt_data_path, 'w') as file:
            for line in lines:
                file.write(str(line))
