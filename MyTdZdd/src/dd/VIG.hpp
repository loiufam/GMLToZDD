#ifndef VERTEX_INDUCED_GRAPHS_HPP
#define VERTEX_INDUCED_GRAPHS_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/HybridGraph.hpp"
#include "../util/IntSubset.hpp"

namespace hybriddd {

class VIG : public tdzdd::PodHybridDdSpec< VIG, int16_t, int16_t, 2 > {
private:
	typedef int16_t Mate;
	typedef int16_t Counter;
	
	static const Mate DNC = -1; // don't care
	static const Mate IN = 0; // in
	static const Mate OUT = -2; // out
	static const Mate NIL = -1;
	
	const Graph& graph;
	const int n;
	const size_t mate_size;
	const bool connected;
	const bool forest;
	mutable IntSubset cc_constraint;
	
	void reject(Mate* mate, const USet< int >& adj) const {
		auto it = adj.begin(), eit = adj.end();
		
		for (; it != eit; ++it) {
			int t = graph.getMateI((*it));
			if (mate[t] == DNC) mate[t] = OUT;
		}
	}
	
	bool loopCheck(Mate* mate, const USet< int >& adj) const {
		auto it = adj.begin(), eit = adj.end();
		
		for (; it != eit; ++it) {
			int t = graph.getMateI((*it));
			if (mate[t] >= IN) return false;
		}
		
		return true;
	}
	
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
		
		Vec< size_t > next(mate_size);
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
	
	void setIsolate(Mate* mate, const USet< int >& adj) const {
		auto it = adj.begin(), eit = adj.end();
		
		for (; it != eit; ++it) {
			int t = graph.getMateI((*it));
			mate[t] = OUT;
		}
	}
	
	int removeVertex(Counter& counter, Mate* mate, int m_ind) const {
		Mate& m = mate[m_ind];
		
		Mate cc = m;
		m = DNC;
		
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
	VIG(const Graph& graph_, string mode = "normal",
		IntSubset cc_constraint_ = IntSubset())
	: graph(graph_), n(graph_.getNumOfE()),
	mate_size(graph_.getMaxFSize()),
	connected(mode == "connected" || mode == "tree"),
	forest(mode == "forest" || mode == "tree"),
	cc_constraint(cc_constraint_) {
		setArraySize(mate_size);
	}
	
	int getRoot(Counter& counter, Mate* mate) const {
		counter = 0;
		for (size_t i = 0; i < mate_size; ++i) mate[i] = DNC;
		return n;
	}
	
	int getChild(Counter& counter, Mate* mate, int level, bool take) const {
		assert(1 <= level && level <= n);
		
		int i = n - level;
		const Graph::Edge& edge = graph.getEdge(i);
		
		Mate& m1 = mate[edge.i1];
		Mate& m2 = mate[edge.i2];
		
		if (take) {
			if (m1 == OUT || m2 == OUT) return 0;
			
			if (forest && m1 >= IN && m2 >= IN && m1 == m2) return 0;
			
			const Graph::AddInfo addinfo = graph.getAddInfo(i);
			
			if (m1 == DNC) {
				if (forest && !loopCheck(mate, addinfo.adj1)) return 0;
				m1 = (connected || forest) ? getCCid(mate) : IN;
				reject(mate, addinfo.adj1);
			}
			
			if (m2 == DNC) {
				if (forest && !loopCheck(mate, addinfo.adj2)) return 0;
				m2 = (connected || forest) ? getCCid(mate) : IN;
				reject(mate, addinfo.adj2);
			}
			
			if (m1 != m2) ccLink(mate, m1, m2);
		} else {
			if (m1 >= IN && m2 >= IN) return 0;
			if (m1 >= IN) m2 = OUT;
			if (m2 >= IN) m1 = OUT;
		}
		
		if (edge.out1) {
			int res = removeVertex(counter, mate, edge.i1);
			if (res == 0 || res == -1) return res;
		}
		
		if (edge.out2) {
			int res = removeVertex(counter, mate, edge.i2);
			if (res == 0 || res == -1) return res;			
		}
		
		if (++i == n) {
			if (!connected && !cc_constraint.empty() &&
				!cc_constraint.contain(counter)) return 0;
			return -1;
		}
		
		return n - i;
	}
};

} // namespace hybriddd

#endif // VERTEX_INDUCED_GRAPHS_HPP
