#ifndef VERTEX_CONSTRAINT_HYBRID_HPP
#define VERTEX_CONSTRAINT_HYBRID_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/HybridGraph.hpp"
#include "../util/IntSubset.hpp"

namespace hybriddd {

class VC_HV : public tdzdd::StatelessDdSpec< VC_HV, 2 > {
private:
	const HybridGraph& graph;
	const int n;
	const IntSubset select;
	const IntSubset non_select;
	
public:
	VC_HV(const HybridGraph& graph_,
		  IntSubset select,
		  IntSubset non_select)
	: graph(graph_), n(graph_.getNumOfI()),
	select(select), non_select(non_select) {}
	
	int getRoot() const {
		return n;
	}
	
	int getChild(int level, bool take) const {
		assert(1 <= level && level <= n);
		
		int i = n - level;
		
		const HybridGraph::Item item = graph.getItemAf(i);
		
		if (item.isvertex) {
			if (!take && select.contain(item.v)) return 0;
			if (take && non_select.contain(item.v)) return 0;
		}
		
		if (++i == n) return -1;
		return n - i;
	}
};

} // namespace hybriddd

#endif // VERTEX_CONSTRAINT_HYBRID_HPP
