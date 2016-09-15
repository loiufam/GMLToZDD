#ifndef HYBRID_OPTIMIZATION_HPP
#define HYBRID_OPTIMIZATION_HPP
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
#include "../util/Timer.hpp"

namespace hybriddd {

class HybridOptimization {
private:
	Vec< Vec< int > > makeMask(const Graph& graph) {
		int N = graph.getNumOfE();
		int F = graph.getMaxFSize();
		
		Vec< Vec< int > > frontier(N + 1, Vec< int >(F, -1));
		Vec< int > cur_frontier(F, -1);
		
		for (int level = N; level > 0; --level) {
			int i = N - level;
			const Graph::Edge& edge = graph.getEdge(i);
			
			if (edge.in1) cur_frontier[edge.i1] = edge.v1;
			if (edge.in2) cur_frontier[edge.i2] = edge.v2;
			
			frontier[level] = cur_frontier;
			
			if (edge.out1) cur_frontier[edge.i1] = -1;
			if (edge.out2) cur_frontier[edge.i2] = -1;
		}
		
		Vec< Vec< int > > mask(N + 1, Vec< int >(N + 1, 0));
		
		for (int i = N; i > 0; --i) {
			for (int j = i - 1; j >= 0; --j) {
				int u = 1 << F;
				
				for (int k = 0; k < F; ++k) {
					if (frontier[i][k] == frontier[j][k]) u |= 1 << k;
				}
				
				mask[i][j] = u;
			}
		}
		
		return mask;
	}
	
public:
	HybridOptimization() {}
	
	template< typename T >
	T maximize(const DdStructure< 2 >& dd,
			   const Graph& graph,
			   const Vec< T >& edge_weight,
			   const Vec< T >& vertex_weight) {
		const NodeTableHandler< 2 >& diagram = dd.getDiagram();
		
		int N = dd.topLevel();
		int F = graph.getMaxFSize();
		
		Vec< Vec< int > > mask = makeMask(graph);
		
		Vec< Vec< MyHashMap< int, T > > > dp_table(N + 1);
		
		for (int level = N; level >= 0; --level) {
			size_t m = (*diagram)[level].size();
			dp_table[level].assign(m, MyHashMap< int, T >());
		}
		
		dp_table[N][0][1 << F] = T(0);
		
		for (int level = N; level > 0; --level) {
			const MyVector< Node< 2 > >& nodes = (*diagram)[level];
			size_t m = nodes.size();
			int i = N - level;
			const Graph::Edge& edge = graph.getEdge(i);
			
			for (size_t j = 0; j < m; ++j) {
				auto it = dp_table[level][j].begin();
				auto eit = dp_table[level][j].end();
				
				for (; it != eit; ++it) {
					for (int b = 0; b < 2; ++b) {
						const NodeId& c = nodes[j].branch[b];
						int ni = c.row(), nj = c.col();
						
						int nxts = it->key;
						T nxt_cost = it->value;
						
						if (b == 1) {
							nxt_cost += edge_weight[i] +
										((nxts >> edge.i1) & 1 ? 0 : vertex_weight[edge.v1]) +
										((nxts >> edge.i2) & 1 ? 0 : vertex_weight[edge.v2]);
							nxts |= (1 << edge.i1) | (1 << edge.i2);
						}

						nxts &= mask[level][ni];
						
						if (dp_table[ni][nj].getValue(nxts) == NULL) {
							dp_table[ni][nj][nxts] = nxt_cost;
						} else {
							T& cost = dp_table[ni][nj][nxts];
							cost = std::max(cost, nxt_cost);
						}
					}
				}
			}
		}
		
		return dp_table[0][1][1 << F];
	}
	
	template< typename T >
	T maximize(const DdStructure< 2 >& ddv, const MyValues< T >& values) {
		const NodeTableHandler< 2 >& diagram = ddv.getDiagram();
		
		int N = ddv.topLevel();
		
		Vec< Vec< T > > dp_table(N + 1);
		
		for (int level = N; level >= 0; --level) {
			size_t m = (*diagram)[level].size();
			dp_table[level].assign(m, values.getLower());
		}
		
		dp_table[N][0] = T(0);
		
		for (int level = N; level > 0; --level) {
			const MyVector< Node< 2 > >& nodes = (*diagram)[level];
			size_t m = nodes.size();
			int i = N - level;
			
			for (size_t j = 0; j < m; ++j) {
				for (int b = 0; b < 2; ++b) {
					const NodeId& c = nodes[j].branch[b];
					int ni = c.row(), nj = c.col();
					
					dp_table[ni][nj] = std::max(dp_table[ni][nj],
														  dp_table[level][j] +
														  values.getValue(i, b));
				}
			}
		}
		
		return dp_table[0][1];
	}
};

}

#endif // HYBRID_OPTIMIZATION_HPP
