#ifndef VERTEX_COUNT_HYBRID_HPP
#define VERTEX_COUNT_HYBRID_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/HybridGraph.hpp"
#include "../util/IntSubset.hpp"

namespace hybriddd {

class VCNT_HV : public tdzdd::DdSpec< VCNT_HV, int, 2 > {
private:
	const HybridGraph& graph;
	const int n;
	const IntSubset constraint;
	
public:
	VCNT_HV(const HybridGraph& graph_, IntSubset constraint_ = IntSubset())
	: graph(graph_), n(graph_.getNumOfI()), constraint(constraint_) {}
	
	int getRoot(int& counter) const {
		counter = 0;
		return (!constraint.empty() && constraint.lower() > n) ? 0 : n;
	}
	
	int getChild(int& counter, int level, bool take) const {
		assert(1 <= level && level <= n);
		
		if (constraint.empty()) {
			--level;
			return level;
		}
		
		int i = n - level;
		const HybridGraph::Item item = graph.getItemAf(i);
		
		if (item.isvertex) {
			if (take) {
				++counter;
				if (constraint.upper() < counter) return 0;
			}
		}
		
		if (++i == n) return constraint.contain(counter) ? -1 : 0;
		return n - i;
	}
};

} // namespace hybriddd

#endif // VERTEX_COUNT_HYBRID_HPP
