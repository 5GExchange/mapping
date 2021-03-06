# Copyright 2017 Balazs Nemeth, Mark Szalay, Janos Doka
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import math
import random
import string
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from pprint import pformat

import numpy as N
from scipy.stats import norm

try:
  # runs when mapping files are called from ESCAPE
  from escape.nffg_lib.nffg import NFFG, NFFGToolBox
except ImportError:
  # runs when mapping repo is cloned individually, and NFFG lib is in a
  # sibling directory. WARNING: cicular import is not avioded by design.
  import site
  site.addsitedir('..')
  from nffg_lib.nffg import NFFG, NFFGToolBox

class AbstractRequestGenerator:
    __metaclass__ = ABCMeta

    def __init__(self, request_lifetime_lambda, nf_type_count, seed=0):
        self.nf_types = list(string.ascii_uppercase)[:nf_type_count]
        self.request_lifetime_lambda = request_lifetime_lambda
        self.rnd = random.Random()
        self.rnd.seed(seed)
        self.numpyrandom = N.random.RandomState(seed)

    @abstractmethod
    def get_request(self, resource_graph, test_lvl):
        pass

    @abstractmethod
    def get_request_lifetime(self, requests_alive):
        pass

    def _shareVNFFromEarlierSG(self, nffg, running_nfs, nfs_this_sc, p):
        sumlen = sum([ l * i for l, i in zip([ len(running_nfs[n]) for n in running_nfs ], xrange(1, len(running_nfs) + 1)) ])
        i = 0
        ratio = float(len(running_nfs.values()[i])) / sumlen
        while ratio < p:
            i += 1
            ratio += float((i + 1) * len(running_nfs.values()[i])) / sumlen

        nf = self.rnd.choice(running_nfs.values()[i])
        if reduce(lambda a, b: a and b, [ v in nfs_this_sc for v in running_nfs.values()[i] ]):
            return (False, None)
        else:
            while nf in nfs_this_sc:
                nf = self.rnd.choice(running_nfs.values()[i])

            if nf in nffg.nfs:
                return (False, nf)
            nffg.add_node(nf)
            return (True, nf)

    def gen_seq (self):
        while True:
            yield int(math.floor(self.rnd.random() * 999999999))

    def get_request_parametrizable (self, resource_graph, test_lvl, min_lat,
                                    max_lat, max_cpu=2, max_sto=3, max_mem=800,
                                    multiSC=False, chain_maxlen=8,
                                    loops=False, use_saps_once=False,
                                    vnf_sharing_probabilty=0.0, max_sc_count=1,
                                    max_bw=10.0, randomize_everything=True):
        all_saps_ending = [s.id for s in resource_graph.saps]
        all_saps_beginning = [s.id for s in resource_graph.saps]
        running_nfs = OrderedDict()
        current_sg_link_cnt = 1
        sc_count = self.rnd.randint(1,max_sc_count)
        while len(all_saps_ending) > sc_count and len(
           all_saps_beginning) > sc_count:
            nffg = NFFG(id='Benchmark-Req-' + str(test_lvl) + '-Piece')
            current_nfs = []
            for scid in xrange(0, sc_count):
                nfs_this_sc = []
                sap1 = nffg.add_sap(
                    id=all_saps_beginning.pop() if use_saps_once else
                    self.rnd.choice(
                        all_saps_beginning))
                sap2 = None
                if loops:
                    sap2 = sap1
                else:
                    tmpid = all_saps_ending.pop() if use_saps_once else \
                        self.rnd.choice(
                        all_saps_ending)
                    while True:
                        if tmpid != sap1.id:
                            sap2 = nffg.add_sap(id=tmpid)
                            break
                        else:
                            tmpid = all_saps_ending.pop() if use_saps_once \
                                else self.rnd.choice(
                                all_saps_ending)
                # WARNING: SAP port must have ID 1, and one single port!
                sg_path = []
                if 1 in sap1.ports:
                    sap1port = sap1.ports[1]
                else:
                    sap1port = sap1.add_port(id=1)
                last_req_port = sap1port
                vnf_cnt = next(self.gen_seq()) % chain_maxlen + 1
                for vnf in xrange(0, vnf_cnt):
                    vnf_added = False
                    p = self.rnd.random()
                    if self.rnd.random() < vnf_sharing_probabilty and len(
                       running_nfs) > 0 and not multiSC:
                        vnf_added, nf = self._shareVNFFromEarlierSG(nffg,
                                                                    running_nfs,
                                                                    nfs_this_sc,
                                                                    p)
                    else:
                        nf = nffg.add_nf(id='-'.join(
                            ('Test', str(test_lvl), 'SC', str(scid), 'VNF',
                             str(vnf))), func_type=self.rnd.choice(
                            self.nf_types), cpu=self.rnd.randint(1, max_cpu) if randomize_everything else max_cpu,
                                         mem=self.rnd.random() * max_mem if randomize_everything else max_mem,
                                         storage=self.rnd.random() * max_sto if randomize_everything else max_sto)
                        vnf_added = True
                    if vnf_added:
                        nfs_this_sc.append(nf)
                        newport = nf.add_port(id=1)
                        sg_link_id = ".".join(
                            ("sghop", str(test_lvl), str(current_sg_link_cnt)))
                        sglink = nffg.add_sglink(last_req_port, newport,
                                                 id=sg_link_id)
                        current_sg_link_cnt += 1
                        sg_path.append(sglink.id)
                        last_req_port = nf.add_port(id=2)

                if 1 in sap2.ports:
                    sap2port = sap2.ports[1]
                else:
                    sap2port = sap2.add_port(id=1)
                sg_link_id = ".".join(
                    ("sghop", str(test_lvl), str(current_sg_link_cnt)))
                sglink = nffg.add_sglink(last_req_port, sap2port, id=sg_link_id)
                current_sg_link_cnt += 1
                sg_path.append(sglink.id)
                nffg.add_req(sap1port, sap2port, id="edge_req_"+str(test_lvl),
                             delay=self.rnd.uniform(min_lat, max_lat),
                             bandwidth=self.rnd.random() * max_bw if randomize_everything else max_bw,
                             sg_path=sg_path)
                new_nfs = [vnf for vnf in nfs_this_sc if vnf not in current_nfs]
                for tmp in xrange(0, scid + 1):
                    current_nfs.extend(new_nfs)

                return nffg


class TestReqGen(AbstractRequestGenerator):

    def __init__(self, request_lifetime_lambda, nf_type_count, seed):
        super(TestReqGen, self).__init__(request_lifetime_lambda, nf_type_count, seed)
        raise Exception("The test request generator is depracted!!")

    def get_request(self, resource_graph, test_lvl):
        all_saps_ending = [s.id for s in resource_graph.saps]
        all_saps_beginning = [s.id for s in resource_graph.saps]
        running_nfs = OrderedDict()
        multiSC = False
        loops = False
        use_saps_once = False
        vnf_sharing_probabilty = 0.0
        vnf_sharing_same_sg = 0.0
        vnf_cnt = 4
        sc_count = 1

        while len(all_saps_ending) > sc_count and len(all_saps_beginning) > sc_count:
            nffg = NFFG(id='Benchmark-Req-' + str(test_lvl) + '-Piece')
            current_nfs = []
            for scid in xrange(0, sc_count):
                nfs_this_sc = []
                sap1 = nffg.add_sap(id=all_saps_beginning.pop() if use_saps_once else self.rnd.choice(all_saps_beginning))
                sap2 = None
                if loops:
                    sap2 = sap1
                else:
                    tmpid = all_saps_ending.pop() if use_saps_once else self.rnd.choice(all_saps_ending)
                    while True:
                        if tmpid != sap1.id:
                            sap2 = nffg.add_sap(id=tmpid)
                            break
                        else:
                            tmpid = all_saps_ending.pop() if use_saps_once else self.rnd.choice(all_saps_ending)

                sg_path = []
                sap1port = sap1.add_port()
                last_req_port = sap1port


                for vnf in xrange(0, vnf_cnt):
                    vnf_added = False
                    p = self.rnd.random()
                    if self.rnd.random() < vnf_sharing_probabilty and len(running_nfs) > 0 and not multiSC:
                        vnf_added, nf = self._shareVNFFromEarlierSG(nffg, running_nfs, nfs_this_sc, p)
                    else:
                        nf = nffg.add_nf(id='-'.join(('Test',
                        str(test_lvl),
                        'SC',
                        str(scid),
                        'VNF',
                        str(vnf))), func_type=self.rnd.choice(self.nf_types), cpu=2, mem=1600, storage=5)
                        vnf_added = True
                    if vnf_added:
                        nfs_this_sc.append(nf)
                        newport = nf.add_port()
                        sglink = nffg.add_sglink(last_req_port, newport)
                        sg_path.append(sglink.id)
                        last_req_port = nf.add_port()

                sap2port = sap2.add_port()
                sglink = nffg.add_sglink(last_req_port, sap2port)
                sg_path.append(sglink.id)
                nffg.add_req(sap1port, sap2port, delay=140.0, bandwidth=4.0, sg_path=sg_path)
                new_nfs = [ vnf for vnf in nfs_this_sc if vnf not in current_nfs ]
                for tmp in xrange(0, scid + 1):
                    current_nfs.extend(new_nfs)

                return nffg

    def get_request_lifetime(self, requests_alive):
        scale_radius = (1 / self.request_lifetime_lambda)
        life_time = self.numpyrandom.exponential(scale_radius)
        return life_time


class SimpleReqGen(AbstractRequestGenerator):

    def __init__(self, request_lifetime_lambda, nf_type_count, seed, min_lat=60, max_lat=220):
        super(SimpleReqGen, self).__init__(request_lifetime_lambda, nf_type_count, seed)
        self.min_lat = min_lat
        self.max_lat = max_lat

    def get_request(self, resource_graph, test_lvl):

        return self.get_request_parametrizable(resource_graph, test_lvl,
                                               self.min_lat, self.max_lat,
                                               max_bw=1.0)

    def get_request_lifetime(self, requests_alive):
        scale_radius = (1 / self.request_lifetime_lambda)
        exp_time = self.numpyrandom.exponential(scale_radius)
        life_time = exp_time
        return life_time


class MultiReqGen(AbstractRequestGenerator):

    def __init__(self, request_lifetime_lambda, nf_type_count, seed, min_lat=60, max_lat=220):
        # NOTE: this doesn't work, not too good for testing anyway...
        self.min_lat = min_lat
        self.max_lat = max_lat
        super(MultiReqGen, self).__init__(request_lifetime_lambda, nf_type_count, seed)

    def get_request(self, resource_graph, test_lvl):

        return self.get_request_parametrizable(resource_graph, test_lvl,
                                               self.min_lat, self.max_lat,
                                               max_cpu=4, max_sto=3,
                                               max_mem=1600, multiSC=True,
                                               max_sc_count=10, max_bw=7.0)
        # WARNING: some behviour is changed due to refactoring into ancestor
        # class (e.g.:length dependant latency generation, but this generator
        # is not really used!

    def get_request_lifetime(self, requests_alive):
        scale_radius = (1 / self.request_lifetime_lambda)
        exp_time = self.numpyrandom.exponential(scale_radius)
        life_time = exp_time
        return life_time


class SimpleReqGenKeepActiveReqsFixed(AbstractRequestGenerator):
    """
    Creates a sequence of lifetime rates so that the number of most probably
    alive requests are around the given parameter. A small radius (measured
    in alive request numbers) around this request count has significant
    probability, the other states are with small probability. Basically
    simulates the following stationary distribution of requests generated:
    """

    def __init__ (self, request_lifetime_lambda, nf_type_count, seed,
                  min_lat, max_lat, equilibrium, request_arrival_lambda,
                  equilibrium_radius=7, cutoff_epsilon=1e-5,
                  convergence_speedup_factor=1):
        super(SimpleReqGenKeepActiveReqsFixed, self).__init__(request_lifetime_lambda,
                                                              nf_type_count, seed)
        self.min_lat = min_lat
        self.max_lat = max_lat
        self.request_arrival_lambda = request_arrival_lambda
        self.most_probable_req_count = equilibrium
        self.convergence_speedup_factor = convergence_speedup_factor
        # significant probability around the most_probable_req_count
        self.cone_radius = equilibrium_radius
        # After max_req_count a fix very small expected lifetime is returned
        self.max_req_count = int((self.most_probable_req_count +
                                  self.cone_radius ) * 1.2)
        self.epsilon = cutoff_epsilon
        # a positive number used to cutoff standard normal distribution to a
        # symmetric interval around zero.
        self.x_epsilon_cutoff = norm.isf(self.epsilon)
        # where should we start to divide normal distribution intervals
        # NOTE: isf = inverse of (1 - cdf)
        x1_epsilon_norm = -1.0 * norm.isf((self.most_probable_req_count -
                                           self.cone_radius) * self.epsilon)
        # where should we finish to divide normal distribution intervals
        self.x2_epsilon_norm = norm.isf((self.max_req_count - self.most_probable_req_count
                                    - self.cone_radius) * self.epsilon)
        if x1_epsilon_norm < -1.0 * self.x_epsilon_cutoff or self.x2_epsilon_norm \
                > self.x_epsilon_cutoff:
            raise RuntimeError("Bad parameter setting of stationary probability "
                               "of alive requests in the system: Intervals overlap!x1_eps: "
                               "%s, x2_eps: %s"%
                               (x1_epsilon_norm, self.x2_epsilon_norm))
        if norm.cdf(self.x2_epsilon_norm) - norm.cdf(x1_epsilon_norm) < 0.66:
            raise RuntimeError("Bad parameter setting of stionary probability of "
                               "alive requests in the system: Too small probability"
                               " around equilibrium! x1_eps: %s, x2_eps: %s, probability: %s"%
                               (x1_epsilon_norm, self.x2_epsilon_norm,
                                norm.cdf(self.x2_epsilon_norm) - norm.cdf(x1_epsilon_norm)))
        if not (0.8 <= math.fabs(x1_epsilon_norm / self.x2_epsilon_norm) <= 1.2) or \
            not (0.8 <= math.fabs(x1_epsilon_norm / self.x2_epsilon_norm) <= 1.2):
            raise RuntimeError(
                "Bad parameter setting of stionary probability of "
                "alive requests in the system: Interval is not symmetric "
                "around equilibrium!x1_eps: %s, x2_eps: %s, ratio: %s"%
                               (x1_epsilon_norm, self.x2_epsilon_norm,
                                x1_epsilon_norm / self.x2_epsilon_norm))
        self.gauss_interval = (self.x2_epsilon_norm - x1_epsilon_norm) / \
                              (2.0*self.cone_radius + 1)
        self.gauss_interval_below = (x1_epsilon_norm - (-1.0*self.x_epsilon_cutoff)) / \
                                    (self.most_probable_req_count - self.cone_radius)
        self.gauss_interval_above = (self.x_epsilon_cutoff - self.x2_epsilon_norm) / \
                                    (self.max_req_count - self.most_probable_req_count
                                    - self.cone_radius)
        # CDF offset to ensure summing up to 1.0
        self.cdf_offset = x1_epsilon_norm + \
                          (self.cone_radius+0.5)*self.gauss_interval
        self.request_lifetime_lambda_cache = {}

    def get_stationary_probability(self, k):
        """
        Calculates the desired statiorary probability of having k requests
        alive in the system for the given distribution parameters.
        :param k:
        :return:
        """
        if 0 <= k < self.most_probable_req_count - self.cone_radius:
            return norm.cdf((k+1)*self.gauss_interval_below - self.x_epsilon_cutoff) -\
                   norm.cdf(k*self.gauss_interval_below - self.x_epsilon_cutoff)
        elif self.most_probable_req_count - self.cone_radius <= k <= \
                self.most_probable_req_count + self.cone_radius:
            # generate probabilities based on normal standard distribution
            # scale to significant interval
            k_prime = k - self.most_probable_req_count - 0.5
            return norm.cdf((k_prime+1) * self.gauss_interval + self.cdf_offset)-\
                   norm.cdf(k_prime * self.gauss_interval + self.cdf_offset)
        elif self.most_probable_req_count + self.cone_radius < k <= self.max_req_count:
            k_prime = k - self.most_probable_req_count - self.cone_radius - 1
            return norm.cdf((k_prime+1)*self.gauss_interval_above + self.x2_epsilon_norm) -\
                   norm.cdf(k_prime*self.gauss_interval_above + self.x2_epsilon_norm)
        elif k < 0:
            raise RuntimeError("Stationary probability of negative request "
                               "count doesn't exist!")
        else:
            # after max_req_count we don't want to increase the number of
            # requests in the network. This is neglected from summing up to 1.0
            # but also, 2*self.epsilon was missing from 1.0 (from the two sides
            # below/above cutoff)
            return self.epsilon

    def _calc_request_lifetime_rate(self, k):
        """
        Calculates the rate of lifetimes of the generated request when there
        are "k" requests running in the system, to achieve the desired
        stationary distribution of alive requests.
        :param k:
        :return:
        """
        try:
            int(k)
        except TypeError:
            raise RuntimeError("Number of requests in the network must be integer!")
        if k < 0:
            raise RuntimeError("Negative number of requests in the network?!")

        if k in self.request_lifetime_lambda_cache:
            return self.request_lifetime_lambda_cache[k]
        elif k == 1 or k == 0:
            self.request_lifetime_lambda_cache[k] = \
                self.request_arrival_lambda * self.get_stationary_probability(0) / \
                self.get_stationary_probability(1)
            return self.request_lifetime_lambda_cache[k]
        else:
            self.request_lifetime_lambda_cache[k] = \
                self.request_arrival_lambda * \
                self.get_stationary_probability(k-1) / \
                self.get_stationary_probability(k) - \
                sum((self._calc_request_lifetime_rate(i) for i in xrange(1,k)))
            return self.request_lifetime_lambda_cache[k]

    def _calc_request_lifetime_rate_easier(self, k):
      try:
        int(k)
      except TypeError:
        raise RuntimeError("Number of requests in the network must be integer!")
      if k < 0:
        raise RuntimeError("Negative number of requests in the network?!")
      if k in self.request_lifetime_lambda_cache:
        return self.request_lifetime_lambda_cache[k]
      elif k == 1 or k == 0:
        self.request_lifetime_lambda_cache[k] = \
          self.request_arrival_lambda * self.get_stationary_probability(0) / \
          self.get_stationary_probability(1)
        return self.request_lifetime_lambda_cache[k]
      else:
        self.request_lifetime_lambda_cache[k] = self.request_arrival_lambda * \
          (self.get_stationary_probability(k-1) / self.get_stationary_probability(k) -
           self.get_stationary_probability(k-2) / self.get_stationary_probability(k-1))
        return self.request_lifetime_lambda_cache[k]

    def get_request_lifetime_rate(self, k):
        """
        Handles the singular values when the rate would be negative because
        of transition between insignificant and significant stationary
        probabilites.
        :param k:
        :return:
        """
        # initially we ask for request lifetime when there is no requests yet
        #  running, but we can terminate the recursion at state 1, beacuse
        # death rate in state 0 doesn't exist! So give +1 offset for the states.
        k += 1
        if k > self.most_probable_req_count + self.cone_radius:
            # make an artificial barrier not to leave behind the top of the
            # cone radius. According to the calculations these rates should
            # be a fairly small value, which makes the number of requests
            # increase in a hight rate
            # Big lifetime rate means low expected lifetime!
            return 1e2 * self.request_arrival_lambda
        if k not in self.request_lifetime_lambda_cache:
            self._calc_request_lifetime_rate_easier(k)
        if self.request_lifetime_lambda_cache[k] < 0:
            # return a neutral value, which doesn't really changes anything.
            return self.request_arrival_lambda
        elif k <= self.most_probable_req_count - self.cone_radius:
            return self.request_lifetime_lambda_cache[k] / self.convergence_speedup_factor
        else:
            return self.request_lifetime_lambda_cache[k]

    def get_request (self, resource_graph, test_lvl):

        return self.get_request_parametrizable(resource_graph, test_lvl,
                                               self.min_lat, self.max_lat)

    def get_request_lifetime(self, requests_alive):
        """
        Calculates a request lifetime based on an exponential distribution
        parameterized by the currently alive requests.
        :param requests_alive:
        :return:
        """
        scale_radius = (1.0 / self.get_request_lifetime_rate(requests_alive))
        # meaning: the scale_radius is the expected value of the exponential distribution
        life_time = self.numpyrandom.exponential(scale_radius)
        return life_time


class SimpleMoreDeterministicReqGen(AbstractRequestGenerator):
    """
    Only the request chain length and the latency is generated randomly, the
    other parameters are fix. So in this request the number of VNFs can be a
    universal metric.
    """

    def __init__ (self, request_lifetime_lambda, nf_type_count, seed,
                  min_lat=60, max_lat=220):
        super(SimpleMoreDeterministicReqGen, self).__init__(request_lifetime_lambda,
                                                            nf_type_count, seed)
        self.min_lat = min_lat
        self.max_lat = max_lat

    def get_request (self, resource_graph, test_lvl):

        return self.get_request_parametrizable(resource_graph, test_lvl,
                                               self.min_lat, self.max_lat,
                                               max_bw=5.0,
                                               randomize_everything=False)

    def get_request_lifetime (self, requests_alive):
        scale_radius = (1 / self.request_lifetime_lambda)
        exp_time = self.numpyrandom.exponential(scale_radius)
        life_time = exp_time
        return life_time


class SimpleDeterministicInitiallyImmortalReqGen(SimpleMoreDeterministicReqGen):

    def __init__(self, request_lifetime_lambda, nf_type_count, seed,
                 initial_request_count, min_lat=60, max_lat=220):
        super(SimpleDeterministicInitiallyImmortalReqGen, self).__init__(
            request_lifetime_lambda, nf_type_count, seed)
        self.min_lat = min_lat
        self.max_lat = max_lat
        self.initial_request_count = initial_request_count
        self.lifetime_getting_counter = 0

    def get_request_lifetime(self, requests_alive):
        if self.initial_request_count >= self.lifetime_getting_counter:
            # this is 10 years in seconds (floatmax is too large)
            self.lifetime_getting_counter += 1
            return 321408000.0
        else:
            return super(SimpleDeterministicInitiallyImmortalReqGen,
                         self).get_request_lifetime(requests_alive)


if __name__ == '__main__':
    # for cr in xrange(7, 50, 3):
    # cr = 14
    # for eps in xrange(1,20):
    #     print 0.9 + eps*0.005, [(i, srgkarf.get_request_lifetime_rate(i)) for i in xrange(395-cr, 406+cr)]
    er = 15
    eq = 300
    srgkarf = SimpleReqGenKeepActiveReqsFixed(1, 1, 1, 1, 1, equilibrium=eq, request_arrival_lambda=0.3333,
                                              equilibrium_radius=er, cutoff_epsilon=1e-7, convergence_speedup_factor=1)
    print "probability", pformat([(i, srgkarf.get_stationary_probability(i)) for i in xrange(0, eq+er+30)]), srgkarf.epsilon
    print sum([srgkarf.get_stationary_probability(i) for i in xrange(0, srgkarf.max_req_count+1)]) + 2*srgkarf.epsilon
    print "exponential distr. parameter", pformat([(i, srgkarf.get_request_lifetime_rate(i)) for i in xrange(0, eq+er+100)])
    print "expected lifetime", pformat([(i, 1.0 / srgkarf.get_request_lifetime_rate(i)) for i in xrange(0, eq+er+100)])
    # print pformat(srgkarf.request_lifetime_lambda_cache)