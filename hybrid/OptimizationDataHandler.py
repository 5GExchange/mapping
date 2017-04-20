import os
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


        with open(self.opt_data_path, 'r+') as file:
            file.write("a\n")
            file.write("b\n")
            self.number_of_lines = sum(1 for _ in file)

        asd = 0

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

                for n in lines:
                    if n % 2:
                        vnf_numbers.append(n)
                    else:
                        opt_times.append(n)

                for i in vnf_numbers:
                    if i > number_of_vnfs - 20 or i < number_of_vnfs + 20:
                        time.append(opt_times[i])

                for k in time:
                    result += k

                return result/len(time)


    def write_data(self, number_of_vnfs, time_of_opt):
        with open(self.opt_data_path, 'r') as file:
            lines = file.readlines()

        lines[self.number_of_lines-1] += number_of_vnfs + ' '
        lines[self.number_of_lines] += time_of_opt + ' '

        with open(self.opt_data_path, 'w') as file:
            for line in lines:
                file.write(str(line))


if __name__ == "__main__":

    opt = OptimizationDataHandler('log_file.log', 'gwin')

    opt.write_data('15', '23')
    opt.write_data('45', '33')
    opt.write_data('75', '43')

    print(opt.get_opt_time('45'))