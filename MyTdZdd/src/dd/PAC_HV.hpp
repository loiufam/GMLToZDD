#ifndef SIMPLE_PATHS_HYBRID_HPP
#define SIMPLE_PATHS_HYBRID_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/HybridGraph.hpp"

namespace hybriddd {

namespace simpath_hv  {

const static int16_t INTER = -123;

struct Path {
	int16_t s, t;
	
	Path() { s = t = INTER; }
	
	void init(int16_t s_) { s = s_; t = s_; }
	void setInterPath() { t = INTER; }
	void setTerminal(int16_t u) { t = u; }
	
	bool isOuterPath() { return s == t; }
	bool terminalIs(int16_t u) { return t == u; }
	bool isInterPath() { return t == INTER; }
	bool isTerminal() { return !isInterPath() && t != s; }
	
	void dump(std::ostream& os) { os << "Path(" << s << ", " << t << ")\n";	}
	
	bool operator > (const Path& a) const {	return (s == a.s) ? t > a.t : s > a.s; }	
	bool operator < (const Path& a) const {	return a > *this; }
	bool operator == (const Path& a) const { return !(a > *this) && !(a < *this); }
	bool operator >= (const Path& a) const { return !(*this < a); }
	bool operator <= (const Path& a) const { return !(*this > a); }
};

};

class PAC_HV : public tdzdd::PodHybridDdSpec< PAC_HV, bool, simpath_hv::Path, 2 > {
private:
	typedef simpath_hv::Path Mate;
	
	const HybridGraph& graph;
	const int n;
	const size_t mate_size;
	
	const int s;
	const int t;
	const bool cycle;
	
	bool pathComplete(Mate* mate, const HybridGraph::Item& item) const {
		for (size_t i = 0; i < mate_size; ++i) {
			if (i == item.i1 || i == item.i2) continue;
			if (mate[i].isTerminal()) return false;
		}
		
		return true;
	}
	
	bool cycleComplete(Mate* mate) const {
		for (size_t i = 0; i < mate_size; ++i) if (mate[i].isTerminal()) return false;
		return true;
	}
	
public:
	PAC_HV(const HybridGraph& graph_, int s_ = -1, int t_ = -1)
	: graph(graph_), n(graph_.getNumOfI()),
	mate_size(graph_.getMaxFSize()),
	s(s_), t(t_), cycle(s_ == -1 || t_ == -1) {
		setArraySize(mate_size);
	}
	
	int getRoot(bool& complete, Mate* mate) const {
		complete = false;
		for (size_t i = 0; i < mate_size; ++i) mate[i] = Mate();
		return n;
	}
	
	int getChild(bool& complete, Mate* mate, int level, bool take) const {
		int i = n - level;
		const HybridGraph::Item& item = graph.getItemAf(i);
		
		if (item.isvertex) {
			Mate& m = mate[item.i];
			
			if (take && m.isOuterPath()) return 0;
			if (!take && !m.isOuterPath()) return 0;
			
			m.init(simpath_hv::INTER);			
		} else {
			if (item.in1) mate[item.i1].init(item.v1);
			if (item.in2) mate[item.i2].init(item.v2);
		
			if (take) {
				Mate m1 = mate[item.i1], m2 = mate[item.i2];
			
				// no branch
				if (m1.isInterPath() || m2.isInterPath()) return 0;
		
				// no loop
				if (!cycle && m1.terminalIs(item.v2)) return 0;
		
				// complete s-t path
				if (!cycle && ((m1.terminalIs(s) && m2.terminalIs(t)) || (m1.terminalIs(t) && m2.terminalIs(s)))) {
					if (i == 0 || pathComplete(mate, item)) complete = true;
					else return 0;
				}
			
				// update mate
				if (m1.t != s && m1.t != t) {
					int t_ind_m1 = graph.getMateI(m1.t);
					mate[t_ind_m1].setTerminal(m2.t);
				}
				
				if (m2.t != s && m2.t != t) {
					int t_ind_m2 = graph.getMateI(m2.t);
					mate[t_ind_m2].setTerminal(m1.t);
				}
				
				if (item.v1 == s || item.v1 == t) mate[item.i1].setInterPath();
				if (item.v2 == s || item.v2 == t) mate[item.i2].setInterPath();
				
				if (!m1.terminalIs(item.v1)) mate[item.i1].setInterPath();
				if (!m2.terminalIs(item.v2)) mate[item.i2].setInterPath();
				
				// complete one cycle
				if (cycle && m1.t == m2.s && m1.s == m2.t) {
					if (cycleComplete(mate)) complete = true;
					else return 0;
				}
			}
			
			// out frontier
			if (item.out1) {
				if (mate[item.i1].isTerminal()) return 0;
				if (mate[item.i1].terminalIs(s) || mate[item.i1].terminalIs(t)) return 0;
			}
		
			if (item.out2) {
				if (mate[item.i2].isTerminal()) return 0;
				if (mate[item.i2].terminalIs(s) || mate[item.i2].terminalIs(t)) return 0;
			}
		}
		
		if (++i == n) return complete ? -1 : 0;
		
		if (complete) {
			while (1) {
				const HybridGraph::Item& item = graph.getItemAf(i);
				if (item.isvertex) break;
				++i; assert(i != n);
			}
		}
		
		return n - i;
	}
};

} // namespace hybriddd

#endif // SIMPLE_PATHS_HYBRID_HPP
