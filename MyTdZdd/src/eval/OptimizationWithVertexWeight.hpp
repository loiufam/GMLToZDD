#ifndef OPTIMIZATION_WITH_VERTEX_WEIGHT_HPP
#define OPTIMIZATION_WITH_VERTEX_WEIGHT_HPP
#include <iostream>
#include <string>
#include <algorithm>
#include <cassert>
#include <set>
#include <map>

#include <tdzdd/DdStructure.hpp>
#include "../util/MyValues.hpp"
#include "../util/HybridGraph.hpp"
#include "../util/commons.hpp"

namespace hybriddd {

class OptimizationWithVertexWeight {
private:
	const DdStructure< 2 >& dd;
	
	int N;
	size_t F;
	const Graph& graph;
	
	typedef Vec< char > FColor;
	
	class NodeHash { public: size_t operator () (const NodeId& f) const { return f.hash(); } };
	
	Vec< Vec< int > > frontier;
	MyUMap< NodeId, FColor, NodeHash > colors;
	Vec< NodeId > node_vector;
	Vec< size_t > last_col;
	
	void makeFrontier() {
		frontier = Vec< Vec< int > >(N + 1);
		Vec< int > cur_frontier(F, -1);
		frontier[0] = cur_frontier;
		
		for (int level = N; level > 0; --level) {
			const Graph::Edge& edge = graph.getEdge(N - level);
			
			if (edge.in1) cur_frontier[edge.i1] = edge.v1;
			if (edge.in2) cur_frontier[edge.i2] = edge.v2;
			
			frontier[level] = cur_frontier;
			
			if (edge.out1) cur_frontier[edge.i1] = -1;
			if (edge.out2) cur_frontier[edge.i2] = -1;
		}
	}
	
	void TopDownDp() {
		NodeId root = dd.root();
		
		FColor init_fcolor(F + 1, '#');
		init_fcolor[F] = 'E';
		
		colors[root] = init_fcolor;
		
		Vec< queue< NodeId > > que(N + 1);
		que[N].push(root);
		
		last_col.assign(N + 1, 0);
		
		for (int level = N; level > 0; --level) {
			int i = N - level;
			const Graph::Edge edge = graph.getEdge(i);
						
			while (!que[level].empty()) {
				NodeId n = que[level].front(); que[level].pop();
				node_vector.push_back(n);
				last_col[level] = std::max(last_col[level], n.col());
				FColor& nc = colors[n];
				
				if (edge.in1) nc[edge.i1] = 'b';
				if (edge.in2) nc[edge.i2] = 'b';
				
				for (int b = 0; b < 2; ++b) {
					const NodeId& c = dd.child(n, b);
					int nxt_level = c.row();
				
					if (colors.count(c) == 0) {
						colors[c] = init_fcolor;
						if (c != 0 && c != 1) que[nxt_level].push(c);
					}
					
					if (c == 0 || c == 1) continue;
					FColor& cc = colors[c];
					
					size_t j = 0;
					
					while (cc[j] != 'E') {
						int v = frontier[level][j], nv = frontier[nxt_level][j];
						
						if (v != -1 && v == nv) {
							if (v == edge.v1 || v == edge.v2) {
								// black node
								if (cc[j] == '#') cc[j] = (b == 0 ? nc[j] : 'r');
								else if (cc[j] != (b == 0 ? nc[j] : 'r')) cc[j] = 'g';
							} else {
								// white node
								if (cc[j] == '#') cc[j] = nc[j];
								else if (cc[j] != nc[j]) cc[j] = 'g';
							}
						}
						
						++j;
					}
				}
			}
		}
		
		std::sort(node_vector.begin(), node_vector.end());
	}
	
	void BottomUpDp() {
		size_t num_of_node = node_vector.size();
		
		for (size_t k = 0; k < num_of_node; ++k) {
			const NodeId& n = node_vector[k];
			int level = n.row();
			
			const NodeId& low = dd.child(n, 0);
			const NodeId& high = dd.child(n, 1);
						
			FColor& nc = colors[n];
			const FColor& lc = colors[low];
			const FColor& hc = colors[high];
			
			int i = N - level;
			const Graph::Edge& edge = graph.getEdge(i);
						
			size_t j = 0;
			
			while (nc[j] != 'E') {
				int v = frontier[level][j], lv = frontier[low.row()][j], hv = frontier[high.row()][j];
				
				if (v != -1) {				
					if (v == edge.v1 || v == edge.v2) {
						// black node
						if ((lv == v && lc[j] == 'r') || low == 0) nc[j] = 'r';
					} else if (frontier[level][j] >= 0) {
						// white node
						if (((lv == v && lc[j] == 'r') || low == 0) &&
							(hv == v && hc[j] == 'r')) nc[j] = 'r';
					}
				}// else { assert(nc[j] == '#'); }
				
				++j;
			}
		}
	}
	
	void preprocess() {
		makeFrontier();
		TopDownDp();
		BottomUpDp();
		cerr << "end preprocess" << endl;
	}
		
public:
	OptimizationWithVertexWeight(const DdStructure< 2 >& _dd_, const Graph& _graph_)
	: dd(_dd_), N(_graph_.getNumOfE()), F(_graph_.getMaxFSize()), graph(_graph_) {
		preprocess();
	}
	
	typedef unsigned long long ull;
	
	struct StateF {
		NodeId n;
		ull f;
	};
	
	template< typename T >
	T optimizeSimple(Vec< T >& edge_weight, Vec< T >& vertex_weight, bool maximize = true) {
		NodeId root = dd.root();
		
		Vec< queue< StateF > > que(N + 1);
		que[N].push(StateF{root, 0});
		
		MyUMap< NodeId, UMap< ull, T >, NodeHash > dp_table;
		dp_table[root][0] = T(0);
		
		int search_node_cnt = 0;
		
		for (int level = N; level > 0; --level) {
			int i = N - level;
			const Graph::Edge& edge = graph.getEdge(i);
			
			while (!que[level].empty()) {
				StateF s = que[level].front(); que[level].pop();
				++search_node_cnt;
				
				T cur_cost = dp_table[s.n][s.f];
				
				for (int b = 0; b < 2; ++b) {
					const NodeId& c = dd.child(s.n, b);
					
					int nxt_level = c.row();
					T nxt_cost = cur_cost + (b == 1 ? edge_weight[i] : T(0));
					ull nxt_f = s.f;
					
					if (b == 1 && (nxt_f >> edge.i1 & 1) == 0) {
						nxt_cost += vertex_weight[edge.v1];
						nxt_f |= 1LL << edge.i1;
					}
					
					if (b == 1 && (nxt_f >> edge.i2 & 1) == 0) {
						nxt_cost += vertex_weight[edge.v2];
						nxt_f |= 1LL << edge.i2;
					}
					
					for (size_t k = 0; k < F; ++k) {
						if (frontier[level][k] != frontier[nxt_level][k]) {
							nxt_f &= ((1ULL << 63) - 1) ^ (1LL << k);
						}
					}
					
					if (dp_table[c].count(nxt_f) == 0) {
						dp_table[c][nxt_f] = (maximize ? T(-(1L << 30)) : T(1L << 30));
						que[nxt_level].push(StateF{c, nxt_f});
					}
					
					T& cost = dp_table[c][nxt_f];
					cost = (maximize ? std::max(cost, nxt_cost) : std::min(cost, nxt_cost));
				}
			}
		}
		
		cerr << "search nodes " << search_node_cnt << endl;
		return dp_table[1][0];
	}
	
	template< typename T >
	T optimizeFast64(Vec< T >& edge_weight, Vec< T >& vertex_weight, bool maximize = true) {
		NodeId root = dd.root();
		
		T init_cost = T(0);
		ull init_f = 0;
		
		if (colors[root][graph.getEdge(0).i1] == 'r') {
			init_cost += vertex_weight[graph.getEdge(0).v1];
			init_f |= 1LL << graph.getEdge(0).i1;
		}
		
		if (colors[root][graph.getEdge(0).i2] == 'r') {
			init_cost += vertex_weight[graph.getEdge(0).v2];
			init_f |= 1LL << graph.getEdge(0).i2;
		}
		
		Vec< queue< StateF > > que(N + 1);
		que[N].push(StateF{root, init_f});
				
		MyUMap< NodeId, UMap< ull, T >, NodeHash > dp_table;
		dp_table[root][init_f] = init_cost;
		
		int search_node_cnt = 0;
		
		for (int level = N; level > 0; --level) {
			int i = N - level;
			const Graph::Edge& edge = graph.getEdge(i);
			
			while (!que[level].empty()) {
				StateF s = que[level].front(); que[level].pop();
				++search_node_cnt;
				
				T cur_cost = dp_table[s.n][s.f];
								
				for (int b = 0; b < 2; ++b) {
					const NodeId& c = dd.child(s.n, b);
					const FColor& cc = colors[c];
					
					int nxt_level = c.row();
					T nxt_cost = cur_cost + (b == 1 ? edge_weight[i] : T(0));
					ull nxt_f = s.f;
					
					if (b == 1 && (nxt_f >> edge.i1 & 1) == 0) {
						nxt_cost += vertex_weight[edge.v1];
						nxt_f |= 1LL << edge.i1;
					}
					
					if (b == 1 && (nxt_f >> edge.i2 & 1) == 0) {
						nxt_cost += vertex_weight[edge.v2];
						nxt_f |= 1LL << edge.i2;
					}
					
					for (size_t k = 0; k < F; ++k) {
						if (frontier[level][k] != frontier[nxt_level][k]) {
							nxt_f &= ((1ULL << 63) - 1) ^ (1LL << k);
						}
						
						if (cc[k] == 'r' && (nxt_f >> k & 1) == 0) {
							nxt_cost += vertex_weight[frontier[nxt_level][k]];
							nxt_f |= 1LL << k;							
						}
					}
					
					if (dp_table[c].count(nxt_f) == 0) {
						dp_table[c][nxt_f] = (maximize ? T(-(1L << 30)) : T(1L << 30));
						que[nxt_level].push(StateF{c, nxt_f});
					}
					
					T& cost = dp_table[c][nxt_f];
					cost = (maximize ? std::max(cost, nxt_cost) : std::min(cost, nxt_cost));
				}
			}
		}
		
		cerr << "search nodes " << search_node_cnt << endl;
		return dp_table[1][0];
	}
};

} // namespace hybriddd

#endif // OPTIMIZATION_WITH_VERTEX_WEIGHT_HPP
