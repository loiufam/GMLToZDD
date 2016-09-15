#ifndef DEGREE_CONSTRAINTS_HYBRID_HPP
#define DEGREE_CONSTRAINTS_HYBRID_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/HybridGraph.hpp"
#include "../util/IntSubset.hpp"

namespace hybriddd {

class DC_HV : public tdzdd::PodArrayDdSpec< DC_HV, int16_t, 2 > {
private:
	typedef int16_t Deg;
	static const Deg DONT_CARE = -1;
	
	const HybridGraph& graph;
	const Vec< IntSubset >& constraints;
	
	const int n;
	const int F;
	
	inline bool takable(int v, Deg deg, bool out, int rem) const {
		if (deg == DONT_CARE) return true;
		if (constraints[v].range_count(deg + 1, deg + 1 + rem) == 0) return false;
		if (constraints[v].upper() <= deg) return false;
		return !out || constraints[v].contain(deg + 1);
	}
	
	inline bool leavable(int v, Deg deg, bool out, int rem) const {
		if (deg == DONT_CARE) return true;
		if (constraints[v].range_count(deg, deg + rem) == 0) return false;
		return !out || constraints[v].contain(deg);
	}
	
	inline void update(int v, Deg& deg, int rem, bool out, bool take) const {
		if (!out && deg != DONT_CARE) {
			if (take) ++deg;
			if (constraints[v].range_count(deg, deg + rem) == rem + 1) deg = DONT_CARE;
		}
	}
	
public:
	DC_HV(const HybridGraph& _graph_, const Vec< IntSubset >& _constraints_)
	: graph(_graph_), constraints(_constraints_),
	  n(_graph_.getNumOfI()), F(_graph_.getMaxFSize()) {
		setArraySize(F);
	}
	
	int getRoot(Deg* deg) const {
		for (int i = 0; i < F; ++i) deg[i] = 0;
		return n;
	}
	
	int getChild(Deg* deg, int level, bool take) const {
		int i = n -level;
		const HybridGraph::Item& item = graph.getItemAf(i);
		
		if (item.isvertex) {
			if (deg[item.i] == 0 && take) return 0;
			if (deg[item.i] != 0 && !take) return 0;
			deg[item.i] = 0;
		} else {
			const HybridGraph::AddInfoHV& info = graph.getAddInfoAf(i);
			
			if (item.in1) deg[item.i1] = (constraints[item.v1].size() == 0) ? DONT_CARE : 0;
			if (item.in2) deg[item.i2] = (constraints[item.v2].size() == 0) ? DONT_CARE : 0;		
			
			if (take) {
				if (!takable(item.v1, deg[item.i1], item.out1, info.rm1)) return 0;
				if (!takable(item.v2, deg[item.i2], item.out2, info.rm2)) return 0;
			} else {
				if (!leavable(item.v1, deg[item.i1], item.out1, info.rm1)) return 0;
				if (!leavable(item.v2, deg[item.i2], item.out2, info.rm2)) return 0;
			}
			
			update(item.v1, deg[item.i1], info.rm1, item.out1, take);
			update(item.v2, deg[item.i2], info.rm2, item.out2, take);
		}
		
		if (++i == n) return -1;
		
		return n - i;
	}
};

} // namespace hybriddd

#endif // DEGREE_CONSTRAINTS_HYBRID_HPP
