#ifndef SCP_HYBRID_HPP
#define SCP_HYBRID_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/HybridGraph.hpp"
#include "../util/IntSubset.hpp"

namespace hybriddd {

class SCP : public tdzdd::PodHybridDdSpec< SCP, int32_t, int16_t, 2 > {
private:
	typedef int16_t Mate;
	typedef int32_t Counter;
	
	static const int VNUM_MASK = (1L << 16);
	static const int CCNUM_OFFSET = 16;
	
	static const Mate DNC = -1; // don't care
	static const Mate IN = 0; // in
	static const Mate OUT = -2; // out
	
	const HybridGraph& graph;
	const int n;
	const size_t mate_size;
	
	void reject(Mate* mate, const USet< int >& adj) const {
		auto it = adj.begin(), eit = adj.end();
		
		for (; it != eit; ++it) {
			int t = graph.getMateI((*it));
			if (mate[t] == DNC) mate[t] = OUT;
		}
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
		for (size_t i = 0; i < mate_size; ++i) if (mate[i] == cc) return true;
		return false;
	}
	
	bool otherCCs(Mate* mate, Mate cc) const {
		for (size_t i = 0; i < mate_size; ++i) if (mate[i] >= IN && mate[i] != cc) return true;
		return false;
	}
	
	void setIsolate(Mate* mate, const USet< int >& adj) const {
		auto it = adj.begin(), eit = adj.end();
		
		for (; it != eit; ++it) {
			int t = graph.getMateI((*it));
			mate[t] = OUT;
		}
	}
	
public:
	SCP(const HybridGraph& graph_)
	: graph(graph_), n(graph_.getNumOfI()),
	mate_size(graph_.getMaxFSize()) {
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
		const HybridGraph::Item& item = graph.getItemAf(i);
		
		if (item.isvertex) {
			Mate& m = mate[item.i];
			
			int32_t vnum = counter & VNUM_MASK;
			int32_t ccnum = counter >> CCNUM_OFFSET;
			
			if (take) ++vnum;
			
			if (take && m == OUT) return 0;
			if (!take && m >= IN) return 0;
			
			if (take && m == DNC) {
				const HybridGraph::AddInfoHV addinfo = graph.getAddInfoAf(i);
				m = getCCid(mate);
				setIsolate(mate, addinfo.adj);
			}
			
			Mate cc = m;
			m = DNC;
			
			if (cc >= IN && !linkCheck(mate, cc)) ++ccnum;
			
			if (++i == n) return -1;
			
			counter = (ccnum << CCNUM_OFFSET) | vnum;
			
			return n - i;
		}
		
		Mate& m1 = mate[item.i1];
		Mate& m2 = mate[item.i2];
		
		if (take) {
			if (m1 == OUT || m2 == OUT) return 0;
			
			const HybridGraph::AddInfoHV addinfo = graph.getAddInfoAf(i);
			
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
		
		++i;
		assert(i != n);
		return n - i;
	}
};

} // namespace hybriddd

#endif // VERTEX_INDUCED_GRAPHS_HYBRID_HPP
