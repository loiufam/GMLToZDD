#ifndef CONNECTED_COMPONENTS_HYBRID_HPP
#define CONNECTED_COMPONENTS_HYBRID_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/HybridGraph.hpp"
#include "../util/IntSubset.hpp"

namespace hybriddd {

class CCS_HV : public tdzdd::PodHybridDdSpec< CCS_HV, int, int, 2 > {
private:
	typedef int Mate;
	typedef int Counter;
	
	static const int STEINER_SHIFT = 16;
	static const int COUNTER_MASK = (1 << 16) - 1;
	
	static const Mate IN = 0;
	static const Mate NIL = -1;
	
	const HybridGraph& graph;
	const int V;
	const int E;
	const int n;
	const size_t mate_size;
	
	const bool connected;
	const bool forest;
	const bool steiner;
	
	mutable IntSubset cc_constraint;
	mutable IntSubset terminals;
	
	Mate getCCid(Mate* mate) const {
		Mate res = -1;
		for (size_t i = 0; i < mate_size; ++i)
			res = std::max(res, mate[i]);
		return res + 1;
	}
	
	void ccLink(Mate* mate, Mate& m1, Mate& m2) const {
		Mate a = std::min(m1, m2);
		Mate b = std::max(m1, m2);
		m1 = m2 = a;
		
		for (size_t i = 0; i < mate_size; ++i) if (mate[i] == b) mate[i] = a;
		
		Vec< Mate > trans(mate_size + 5, NIL);
		Mate cur = 0;
		for (size_t i = 0; i < mate_size; ++i) {
			Mate mi = mate[i];
			if (mi >= IN) {
				if (trans[mi] == NIL) {
					mate[i] = trans[mi] = cur++;
				} else {
					mate[i] = trans[mi];
				}
			}
		}
		/*
		for (size_t i = 0; i < mate_size; ++i) {
			if (mate[i] == b) mate[i] = a;
			if (mate[i] > b) --mate[i];
		}
		
		typedef std::pair< Mate, Mate > pii;
		Vec< pii > vp(mate_size);
		for (size_t i = 0; i < mate_size; ++i) vp[i] = pii(0, i);
		
		for (size_t i = 0; i < mate_size; ++i)
			if (mate[i] >= IN) ++vp[mate[i]].first;
		std::sort(vp.begin(), vp.end(), greater< pii >());
		
		Vec< Mate > next(mate_size);
		for (size_t i = 0; i < mate_size; ++i) next[vp[i].second] = i;
		
		for (size_t i = 0; i < mate_size; ++i)
			if (mate[i] >= IN) mate[i] = next[mate[i]];
		*/
	}
	
	bool linkCheck(Mate* mate, Mate cc) const {
		for (size_t i = 0; i < mate_size; ++i)
			if (mate[i] == cc) return true;
		return false;
	}
	
	bool otherCCs(Mate* mate, Mate cc) const {
		for (size_t i = 0; i < mate_size; ++i)
			if (mate[i] >= IN && mate[i] != cc) return true;
		return false;
	}
	
public:
	CCS_HV(const HybridGraph& graph_, string mode = "connected",
		   IntSubset cc_constraint_ = IntSubset(),
		   IntSubset terminals_ = IntSubset()) 
	: graph(graph_), V(graph_.getNumOfV()), E(graph_.getNumOfE()),
	n(graph_.getNumOfI()), mate_size(graph_.getMaxFSize()),
	connected(mode == "connected" || mode == "tree"),
	forest(mode == "forest" || mode == "tree"),
	steiner(!terminals_.empty()),
	cc_constraint(cc_constraint_),
	terminals(terminals_) {
		setArraySize(mate_size);
	}
	
	int getRoot(Counter& counter, Mate* mate) const {
		counter = steiner ? (terminals.size() << STEINER_SHIFT) : 0;
		for (size_t i = 0; i < mate_size; ++i) mate[i] = NIL;
		return n;
	}
	
	int getChild(Counter& counter, Mate* mate, int level, bool take) const {
		assert(1 <= level && level <= n);
		
		int i = n - level;
		const HybridGraph::Item& item = graph.getItemAf(i);
		
		if (item.isvertex) {
			Mate& m = mate[item.i];
			
			if (take && m == NIL) return 0;
			if (!take && m >= IN) return 0;
			
			int steiner_terms = counter >> STEINER_SHIFT;
			
			if (steiner) {
				if (terminals.contain(item.v) && m == NIL) return 0;
				if (terminals.contain(item.v) && m >= IN) --steiner_terms;
			}
			
			Mate cc = m;
			m = NIL;
			
			int cc_counter = counter & COUNTER_MASK;
			
			if (cc >= IN && !linkCheck(mate, cc)) {
				if (connected) {
					if (otherCCs(mate, cc)) return 0;
					else if (steiner_terms > 0) return 0;
					else return -1;
				}
				
				if (!cc_constraint.empty()) {
					++cc_counter;
					if (cc_constraint.upper() < cc_counter) return 0;
				}
			}
			
			if (++i == n) {
				if (connected || steiner_terms > 0) return 0;
				if (!cc_constraint.empty() &&
					!cc_constraint.contain(cc_counter)) return 0;
				return -1;
			}
			
			counter = (steiner_terms << STEINER_SHIFT) | cc_counter;
				
			return n - i;
		}
		
		Mate& m1 = mate[item.i1];
		Mate& m2 = mate[item.i2];
		
		if (take) {
			if (forest && m1 >= IN && m2 >= IN && m1 == m2) return 0;
			if (m1 == NIL) m1 = getCCid(mate);
			if (m2 == NIL) m2 = getCCid(mate);
			if (m1 != m2) ccLink(mate, m1, m2);
		}
		
		++i;
		assert(i != n);
		return n - i;
	}
};

} // namespace hybriddd

#endif // CONNECTED_COMPONENTS_HYBRID_HPP
