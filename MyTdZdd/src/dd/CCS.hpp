#ifndef CONNECTED_COMPONENTS_HPP
#define CONNECTED_COMPONENTS_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/Graph.hpp"
#include "../util/IntSubset.hpp"

namespace hybriddd {

class CCS : public tdzdd::PodHybridDdSpec< CCS, int, int, 2 > {
private:
	typedef int Mate;
	typedef int Counter;
	
	static const Mate IN = 0;
	static const Mate NIL = -1;
	
	const Graph& graph;
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
		
		typedef std::pair< int, int > pii;
		Vec< pii > vp(mate_size);
		for (size_t i = 0; i < mate_size; ++i) vp[i] = pii(0, i);
		
		for (size_t i = 0; i < mate_size; ++i)
			if (mate[i] >= IN) ++vp[mate[i]].first;
		std::sort(vp.begin(), vp.end(), greater< pii >());
		
		Vec< int > next(mate_size);
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
	
	int removeVertex(Counter& counter, Mate* mate, size_t i) const {
		Mate& m = mate[i];
		
		Mate cc = m;
		m = NIL;
		
		if (cc >= IN && !linkCheck(mate, cc)) {
			if (connected) {
				if (otherCCs(mate, cc)) return 0;
				else return -1;
			}
			
			if (!cc_constraint.empty()) {
				++counter;
				
				if (cc_constraint.upper() == counter) {
					if (otherCCs(mate, cc)) return 0;
					else return -1;
				}
			}
		}
		
		return -2;
	}
	
public:
	CCS(const Graph& graph_, string mode = "connected",
		IntSubset cc_constraint_ = IntSubset(),
		IntSubset terminals_ = IntSubset()) 
	: graph(graph_), V(graph_.getNumOfV()), E(graph_.getNumOfE()),
	n(graph_.getNumOfE()), mate_size(graph_.getMaxFSize()),
	connected(mode == "connected" || mode == "tree"),
	forest(mode == "forest" || mode == "tree"),
	steiner(!terminals_.empty()),
	cc_constraint(cc_constraint_),
	terminals(terminals_) {
		setArraySize(mate_size);
	}
	
	int getRoot(Counter& counter, Mate* mate) const {
		counter = 0;
		for (size_t i = 0; i < mate_size; ++i) mate[i] = NIL;
		return n;
	}
	
	int getChild(Counter& counter, Mate* mate, int level, bool take) const {
		assert(1 <= level && level <= n);
		
		int i = n - level;
		const Graph::Edge& edge = graph.getEdge(i);
		
		Mate& m1 = mate[edge.i1];
		Mate& m2 = mate[edge.i2];
		
		if (take) {
			if (forest && m1 >= IN && m2 >= IN && m1 == m2) return 0;
			if (m1 == NIL) m1 = getCCid(mate);
			if (m2 == NIL) m2 = getCCid(mate);
			if (m1 != m2) ccLink(mate, m1, m2);
		}
		
		if (edge.out1) {
			if (steiner && terminals.contain(edge.v1) && m1 == NIL)
				return 0;
			
			int res = removeVertex(counter, mate, edge.i1);
			if (res == 0 || res == -1) return res;
		}
		
		if (edge.out2) {
			if (steiner && terminals.contain(edge.v2) && m2 == NIL)
				return 0;
			
			int res = removeVertex(counter, mate, edge.i2);
			if (res == 0 || res == -1) return res;
		}
		
		if (++i == n) {
			if (connected) return 0;
			if (!connected && !cc_constraint.empty() &&
				!cc_constraint.contain(counter)) return 0;
			return -1;
		}
		
		return n - i;
	}
};

} // namespace hybriddd

#endif // CONNECTED_COMPONENTS_HPP
