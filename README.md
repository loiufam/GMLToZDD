### sample for s-t path enumeration

	hybriddd::MyTdZdd mytdzdd(< graph_file_name >, < variable_ordering >);
	
	/*** variable_ordering
	"as-is"
	"dfs"
	"bfs" <-- default
	"greedy"
	***/
	
	hybriddd::MyEval result = mytdzdd.S_T_PATH(< S >, < T >, < vertex indeces flag >);
	
	result.dump(std::cout);
	
	/*** dump
	# enumeration type
	# computation (enumeration) time
	# non-reduced dd size
	# reduced dd size
	# cardinality
	***/

### graph file format

	|V| |E|
	u_1 v_1
	u_2 v_2
	...
	...
	...
	u_{|E|} v_{|E|}

u_i and v_i (i = 1, 2, ..., |E|) must be 0-indexed.
