This orchestration algorithm maps service graphs (consisting of (virtual) network
 functions and logical connections) to resource graphs (consisting of virtualized
 node and network resources) in a greedy backtracking manner, based on heuristics
and customizable perference value calculations. 

Files required to run the algorithm:
      * MappingAlgorithms.py ---> function MAP() is the entry point
      * Alg1_Core.py
      * GraphPreprocessor.py
      * Alg1_Helper.py
      * BacktrackHandler.py
      * UnifyExceptionTypes.py

Other files:
      * StressTest-small.py
      * CarrierTopoBuilder.py
      * MIPBaseline.py
      * milp_solution_in_nffg.py

Utilities (can be outdated):
      * BatchTest-params.py
      * ParameterSearch.py
      * SimulatedAnnealing.py
      * StressTest.py
      * StressTest-agressive.py
      * StressTest-decent.py
      * StressTest-gwin.py
      * StressTest-normal.py
      * StressTest-sc8decent.py
      * StressTest-sharing.py
      * calc_mapping_times.py
      * calc_res_util_metrics.py
      * count_bt_successes.py
      * count_milp_successes.py

The parameters of the algorithm are:
      * enable_shortest_path_cache -- saves the calculated shortest paths for the
                 resource graph into a file for later usage.
      * bw_factor, res_factor, lat_factor -- the coefficients of bandwidth, node
      		 resources and latency respectively, during network function 
		 placement preference value. Their sum is suggested to be 3.0.
      * bt_limit -- Backtracking depth limit of the algorithm.
      * bt_branching_factor -- The number of the top preferred placement options
                 to remember.
      * mode -- Mapping operation mode:
      	     	 NFFG.MODE_REMAP -- All network function and every reservation 
              		 attribute of the resource graph are ignored.
		 NFFG.MODE_ADD -- The stored VNF information in the substrate 
                         graph is interpreted as reservation state. Their 
			 resource requirements are subtracted from the available.
			 If an ID is present in both the substrate and request 
			 graphs, the resource requirements (and the whole 
			 instance) will be updated.
                 NFFG.MODE_DEL -- All the elements of the request will be 
		         deleted from the resource graph which has all of its 
			 connected components speficied in the service graph.
      * (shortest_paths -- The shortest path matrix can be added as an input 
      		 Python object.)
      * (return_dist -- The MAP function returns a tuple of the mapped NFFG and 
      	         the shortest path Python object)

An example invocation of the orchestration algorithm for mapping a sevice graph
to a resource graph both given by an NFFG file, can be found in the __main__ of 
MappingAlgorithms.py.

The documentation for the input structure formats can be found in nffg-doc.pdf.

The project was mainly created for the needs of UNIFY, FP7 project 
(http://fp7-unify.eu/). The algorithm is incoroprated into the ESCAPE framework
available at https://sb.tmit.bme.hu/escape/.

For more details on the context and design of the algorithm is (will be) 
available in the paper published in 
IEEE NFV-SDN -- 2nd Workshop for Orchestration for Software Defined Infrastructure
(O4SDI), 07th November 2016, Palo Alto, CA, USA. 
title: Efficient Service Graph Embedding: A Practical Approach
authors: Balázs Németh, Balázs Sonkoly (Budapest University of Technology and
Economics), Matthias Rost (Technische Universität Berlin), Stefan Schmid (Aalborg
 University)
