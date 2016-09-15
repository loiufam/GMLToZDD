#ifndef POWER_SET_HYBRID_HPP
#define POWER_SET_HYBRID_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/HybridGraph.hpp"

namespace hybriddd {

class POW_HV : public tdzdd::PodArrayDdSpec< POW_HV, bool, 2 > {
private:
	typedef bool Mate;
	
	const HybridGraph& graph;
	const int n;
	const size_t mate_size;
	
public:
	POW_HV(const HybridGraph& graph_)
	: graph(graph_), n(graph_.getNumOfI()),
	mate_size(graph_.getMaxFSize()) {
		setArraySize(mate_size);
	}
	
	int getRoot(Mate* mate) const {
		for (size_t i = 0; i < mate_size; ++i) mate[i] = 0;
		return n;
	}
	
	int getChild(Mate* mate, int level, bool take) const {
		assert(1 <= level && level <= n);
		
		int i = n - level;
		const HybridGraph::Item& item = graph.getItemAf(i);
		
		if (item.isvertex) {
			Mate& m = mate[item.i];
			
			if (take && !m) return 0;
			if (!take && m) return 0;
			
			m = 0;
		} else {
			Mate& m1 = mate[item.i1];
			Mate& m2 = mate[item.i2];
		
			if (take) {
				m1 = 1;
				m2 = 1;
			}
		}
		
		if (++i == n) return -1;
		
		while (1) {
			const HybridGraph::Item& item = graph.getItemAf(i);
			if (!item.isvertex) break;
			if (mate[item.i]) break;
			if (++i == n) return -1;
		}
		
		assert(i != n);
		return n - i;
	}
};

} // namespace hybriddd

#endif // POWER_SET_HYBRID_HPP
