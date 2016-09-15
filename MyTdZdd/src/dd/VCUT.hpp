#ifndef VERTEX_CUT_HPP
#define VERTEX_CUT_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/HybridGraph.hpp"
#include "../util/IntSubset.hpp"

namespace hybriddd {

class VCUT : public tdzdd::PodHybridDdSpec< VCUT, int16_t, int16_t, 2 > {
private:
	typedef int16_t Mate;
	typedef int16_t Counter;
	
	static const Mate DNC = -1; // don't care
	static const Mate IN = 0; // in
	static const Mate OUT = -2; // out
	
	const Graph& graph;
	const int n;
	const size_t mate_size;
	mutable IntSubset constraint;
	
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
			++counter;
			
			if (constraint.upper() == counter) {
				if (otherCCs(mate, cc)) return 0;
				else return -1;
			}
		}
		
		return -2;
	}
	
public:
	VCUT(const Graph& graph_,
			IntSubset constraint_ = IntSubset())
	: graph(graph_), n(graph_.getNumOfE()),
	mate_size(graph_.getMaxFSize()),
	constraint(constraint_) {
		setArraySize(mate_size);
		
		// 必ず2分割以上になるような制約
		if (constraint.empty()) {
			for (int c = 2; c <= (int)graph_.getNumOfV(); ++c) {
				constraint.add(c);
			}
		} else if (constraint.upper() < 2) {
			constraint.clear();
			for (int c = 2; c <= (int)graph_.getNumOfV(); ++c) {
				constraint.add(c);
			}
		}
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
		
		if (!take) {
			if (m1 == OUT || m2 == OUT) return 0;
			
			Graph::AddInfo addinfo = graph.getAddInfo(i);
			
			if (m1 == DNC) {
				m1 = getCCid(mate);
				reject(mate, addinfo.adj1);
			}
			
			if (m2 == DNC) {
				m2 = getCCid(mate);
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
			if (!constraint.contain(counter)) return 0;
			return -1;
		}
		
		return n - i;
	}
};

} // namespace hybriddd

#endif // VERTEX_CUT_HPP
