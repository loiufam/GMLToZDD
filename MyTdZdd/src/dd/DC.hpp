#ifndef DEGREE_CONSTRAINTS_HPP
#define DEGREE_CONSTRAINTS_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/HybridGraph.hpp"
#include "../util/IntSubset.hpp"

namespace hybriddd {

class DC : public tdzdd::PodArrayDdSpec< DC, int16_t, 2 > {
private:
	typedef int16_t Deg;
	static const Deg DONT_CARE = -1;
	
	const Graph& graph;
	const Vec< IntSubset >& constraints;
	const bool use_cut_and_dc;
	
	const int n;
	const int F;
	
	inline bool takable(int v, Deg deg, bool out, int rem) const {
		if (deg == DONT_CARE) return true;
		if (use_cut_and_dc && constraints[v].range_count(deg + 1, deg + 1 + rem) == 0) return false;
		if (constraints[v].upper() <= deg) return false;
		return !out || constraints[v].contain(deg + 1);
	}
	
	inline bool leavable(int v, Deg deg, bool out, int rem) const {
		if (deg == DONT_CARE) return true;
		if (use_cut_and_dc && constraints[v].range_count(deg, deg + rem) == 0) return false;
		return !out || constraints[v].contain(deg);
	}
	
	inline void update(int v, Deg& deg, int rem, bool out, bool take) const {
		if (out) {
			deg = 0;
		} else if (deg != DONT_CARE) {
			if (take) ++deg;
			if (use_cut_and_dc && constraints[v].range_count(deg, deg + rem) == rem + 1) deg = DONT_CARE;
		}
	}
	
public:
	DC(const Graph& _graph_, const Vec< IntSubset >& _constraints_, bool _use_cut_and_dc_ = true)
	: graph(_graph_), constraints(_constraints_), use_cut_and_dc(_use_cut_and_dc_),
	  n(_graph_.getNumOfE()), F(_graph_.getMaxFSize()) {
		setArraySize(F);
	}
	
	int getRoot(Deg* deg) const {
		for (int i = 0; i < F; ++i) deg[i] = 0;
		return n;
	}
	
	int getChild(Deg* deg, int level, bool take) const {
		int i = n -level;
		const Graph::Edge& edge = graph.getEdge(i);
		const Graph::AddInfo& info = graph.getAddInfo(i);
		
		if (edge.in1) deg[edge.i1] = (constraints[edge.v1].size() == 0 && use_cut_and_dc) ? DONT_CARE : 0;
		if (edge.in2) deg[edge.i2] = (constraints[edge.v2].size() == 0 && use_cut_and_dc) ? DONT_CARE : 0;		
		
		if (take) {
			if (!takable(edge.v1, deg[edge.i1], edge.out1, info.rm1)) return 0;
			if (!takable(edge.v2, deg[edge.i2], edge.out2, info.rm2)) return 0;
		} else {
			if (!leavable(edge.v1, deg[edge.i1], edge.out1, info.rm1)) return 0;
			if (!leavable(edge.v2, deg[edge.i2], edge.out2, info.rm2)) return 0;
		}
		
		if (++i == n) return -1;
		
		update(edge.v1, deg[edge.i1], info.rm1, edge.out1, take);
		update(edge.v2, deg[edge.i2], info.rm2, edge.out2, take);
		
		return n - i;
	}
};

} // namespace hybriddd

#endif // DEGREE_CONSTRAINTS_HPP
