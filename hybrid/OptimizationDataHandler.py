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


        with open(self.opt_data_path, 'a') as file:
            file.write("0 \n")
            file.write("0 \n")


        with open(self.opt_data_path, 'r') as file:
            self.number_of_lines = sum (1 for _ in file)


    def get_opt_time(self, number_of_vnfs):

            if os.stat(self.opt_data_path).st_size == 0:
                time = 0
                return time
            else:
                with open(self.opt_data_path, 'r') as file:
                    lines = file.readlines()

                vnf_numbers = []
                opt_times = []
                time = []
                result = 0.0

                for x in range(0, self.number_of_lines):
                    if not x % 2:
                        lines[x] = lines[x].rstrip()
                        vnf_numbers.append(lines[x])
                    else:
                        lines[x] = lines[x].rstrip()
                        opt_times.append(lines[x])

                for i in range(0, len(vnf_numbers)):
                    for j in vnf_numbers:
                        for k in j:
                            if k > int(number_of_vnfs) - 20 or k < int(number_of_vnfs) + 20:

    # eddig van kesz, most a itt szereplo sorszamu elemeket kell kiszedni a opt_times-bol es atlagolni

                                time.append(opt_times)
                                asd = 0
                for k in time:
                    result += k
                return result/len(time)

    def write_data(self, number_of_vnfs, time_of_opt):
        with open(self.opt_data_path, 'r') as file:
            lines = file.readlines()

        asd = 10

        line_of_vnfs = self.number_of_lines - 2
        line_of_time = self.number_of_lines - 1

        lines[line_of_vnfs] = lines[line_of_vnfs].rstrip()
        lines[line_of_vnfs] += ' ' + number_of_vnfs + '\n'

        lines[line_of_time] = lines[line_of_time].rstrip()
        lines[line_of_time] += ' ' + time_of_opt + '\n'

        with open(self.opt_data_path, 'w') as file:
            for line in lines:
                file.write(str(line))


if __name__ == "__main__":

    opt = OptimizationDataHandler('log_file.log', 'gwin')

    opt.write_data('15', '23')
    opt.write_data('45', '33')
    opt.write_data('75', '43')

    print(opt.get_opt_time('45'))