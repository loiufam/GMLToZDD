#ifndef SIMPLE_PATHS_HPP
#define SIMPLE_PATHS_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/Graph.hpp"

namespace hybriddd {

namespace simpath  {

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

class PAC : public tdzdd::PodArrayDdSpec< PAC, simpath::Path, 2 > {
private:
	typedef simpath::Path Mate;
	
	const Graph& graph;
	const int n;
	const size_t mate_size;
	
	const int s;
	const int t;
	const bool cycle;
	
	bool pathComplete(Mate* mate, const Graph::Edge& edge) const {
		for (size_t i = 0; i < mate_size; ++i) {
			if (i == edge.i1 || i == edge.i2) continue;
			if (mate[i].isTerminal()) return false;
		}
		
		return true;
	}
	
	bool cycleComplete(Mate* mate) const {
		for (size_t i = 0; i < mate_size; ++i) if (mate[i].isTerminal()) return false;
		return true;
	}
	
public:
	PAC(const Graph& graph_, int s_ = -1, int t_ = -1)
	: graph(graph_), n(graph_.getNumOfE()),
	mate_size(graph_.getMaxFSize()),
	s(s_), t(t_), cycle(s_ == -1 || t_ == -1) {
		setArraySize(mate_size);
	}
	
	int getRoot(Mate* mate) const {
		for (size_t i = 0; i < mate_size; ++i) mate[i] = Mate();
		return n;
	}
	
	int getChild(Mate* mate, int level, bool take) const {
		int i = n - level;
		const Graph::Edge& edge = graph.getEdge(i);
	
		if (edge.in1) mate[edge.i1].init(edge.v1);
		if (edge.in2) mate[edge.i2].init(edge.v2);
	
		if (take) {
			Mate m1 = mate[edge.i1], m2 = mate[edge.i2];
		
			// no branch
			if (m1.isInterPath() || m2.isInterPath()) return 0;
	
			// no loop
			if (!cycle && m1.terminalIs(edge.v2)) return 0;
	
			// complete s-t path
			if (!cycle && ((m1.terminalIs(s) && m2.terminalIs(t)) || (m1.terminalIs(t) && m2.terminalIs(s)))) {
				if (i == 0 || pathComplete(mate, edge)) return -1;
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
			
			if (edge.v1 == s || edge.v1 == t) mate[edge.i1].setInterPath();
			if (edge.v2 == s || edge.v2 == t) mate[edge.i2].setInterPath();
			
			if (!m1.terminalIs(edge.v1)) mate[edge.i1].setInterPath();
			if (!m2.terminalIs(edge.v2)) mate[edge.i2].setInterPath();
			
			// complete one cycle
			if (cycle && m1.t == m2.s && m1.s == m2.t) {
				if (cycleComplete(mate)) return -1;
				else return 0;
			}
		}
		
		// out frontier
		if (edge.out1) {
			if (mate[edge.i1].isTerminal()) return 0;
			if (mate[edge.i1].terminalIs(s) || mate[edge.i1].terminalIs(t)) return 0;
			mate[edge.i1].init(simpath::INTER);
		}
	
		if (edge.out2) {
			if (mate[edge.i2].isTerminal()) return 0;
			if (mate[edge.i2].terminalIs(s) || mate[edge.i2].terminalIs(t)) return 0;
			mate[edge.i2].init(simpath::INTER);
		}
		
		if (++i == n) return 0;
				
		return n - i;
	}
};

} // namespace hybriddd

#endif // SIMPLE_PATHS_HPP
