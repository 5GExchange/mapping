import os
from configobj import ConfigObj
import logging
log = logging.getLogger(" OptimizationDataHandler ")


class OptimizationDataHandler():

    def __init__(self, full_log_path, config_file_path, resource_type):
        formatter = logging.Formatter(
            '%(asctime)s | OptimizationDataHandler | %(levelname)s | \t%(message)s')
        hdlr = logging.FileHandler(full_log_path)
        hdlr.setFormatter(formatter)
        log.addHandler(hdlr)
        log.setLevel(logging.DEBUG)
        config = ConfigObj(config_file_path)
        self.parameter = int(config['optdatahandler_param'])

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
            try:
                with open(self.opt_data_path, 'r') as file:
                    lines = file.readlines()

                time = []
                result = 0.0
                id = 0
                vnf_numbers = lines[0].rstrip().split(",")
                opt_times = lines[1].rstrip().split(",")

                for i in vnf_numbers:
                    if (int(i) > int(target_vnf_number) - self.parameter) and \
                            (int(i) < int(target_vnf_number) + self.parameter):
                        time.append(opt_times[id])
                    id += 1

                for k in time:
                    result += float(k)

                if len(time) > 0:
                    log.debug("OptDataHandler: " + str(target_vnf_number) +
                              " VNF avg opt time: " + str(result/len(time)))
                    return result/len(time)
                else:
                    log.debug("OptDataHandler: There is no such value in the database")
                    return 0
            except Exception as e:
                log.error("OptDataHandler: get_opt_time error -  %s", e)
                raise


    def write_data(self, number_of_vnfs, time_of_opt):
        try:
            with open(self.opt_data_path, 'r') as file:
                lines = file.readlines()

            time_of_opt = round(time_of_opt, 2)

            lines[0] = lines[0].rstrip()
            lines[0] += ',' + str(number_of_vnfs) + '\n'

            lines[1] = lines[1].rstrip()
            lines[1] += ',' + str(time_of_opt) + '\n'

            with open(self.opt_data_path, 'w') as file:
                for line in lines:
                    file.write(str(line))
        except Exception as e:
            log.error("OptDataHandler: write_data error -  %s", e)
            raise