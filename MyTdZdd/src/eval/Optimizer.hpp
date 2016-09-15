#ifndef __OPTIMIZER_HPP__
#define __OPTIMIZER_HPP__

#include <set>
#include <tdzdd/DdStructure.hpp>
#include "../util/MyValues.hpp"
#include "../util/commons.hpp"

namespace hybriddd {

template< typename T >
class DP_Table {
private:
	struct Info {
		T value;
		int prev_row, prev_col, prev_rank, branch;
		bool operator < (const Info& o) const { return value < o.value; }
		bool operator > (const Info& o) const { return o < *this; }
	};
	
	int N, K, INF;
	Vec< Vec< Vec< Info > > > table;

public:
	T getOptimalValue(int rank) const {
		assert(1 <= rank && rank <= K);
		return table[0][1][rank - 1].value;
	};
	
	string getOptimalSolution(int rank) const {
		assert(1 <= rank && rank <= K);
		Info cur = table[0][1][rank - 1];
		int cur_row = 0;
		string res = "";
		
		while (cur.prev_row != -1) {
			for (int i = cur_row + 1; i < cur.prev_row; ++i) res += '0';
			res += char('0' + (cur.branch));
			cur_row = cur.prev_row;
			cur = table[cur.prev_row][cur.prev_col][cur.prev_rank];
		}
		
		reverse(res.begin(), res.end());
		return res;
	}

public:
	DP_Table() {}
	DP_Table(int _N_, int _K_, T _INF_) : N(_N_), K(_K_), INF(_INF_) { setHeight(_N_); }
	
	void setHeight(int h) { table.assign(h, Vec< Vec< Info > >()); }
	void setWidth(int row, int w) { table[row].assign(w, Vec< Info >(K, Info{INF, -1, -1, -1, -1})); }
	
	void setInitValue(T init_value) { table[table.size() - 1][0][0] = Info{init_value, -1, -1, -1, -1}; }
	
	void minUpdate(int from_row, int from_col, int to_row, int to_col, int branch, T add_value) {
		for (int k = 0; k < K; ++k) {
			Info cur = table[from_row][from_col][k];
			if (cur.value == INF) break;
			
			Info nxt{cur.value + add_value, from_row, from_col, k, branch};
			if (table[to_row][to_col][K - 1] > nxt) {
				table[to_row][to_col][K - 1] = nxt;				
				for (int kk = K - 2; kk >= 0; --kk) {
					if (table[to_row][to_col][kk] > nxt) swap(table[to_row][to_col][kk], table[to_row][to_col][kk + 1]);
					else break;
				}
			}
		}
	}
	
	void maxUpdate(int from_row, int from_col, int to_row, int to_col, int branch, T add_value) {
		for (int k = 0; k < K; ++k) {
			Info cur = table[from_row][from_col][k];
			if (cur.value == INF) break;
			
			Info nxt{cur.value + add_value, from_row, from_col, k, branch};
			if (table[to_row][to_col][K - 1] < nxt) {
				table[to_row][to_col][K - 1] = nxt;				
				for (int kk = K - 2; kk >= 0; --kk) {
					if (table[to_row][to_col][kk] < nxt) swap(table[to_row][to_col][kk], table[to_row][to_col][kk + 1]);
					else break;
				}
			}
		}
	}
};

template< typename T >
class Optimizer {
private:
	const MyValues< T >& values;
	// value of item at level L -> values.getValue(N - L, branch)
	
public:
	Optimizer() {}
	Optimizer(const MyValues< T >& __values__) : values(__values__) {}
	
	const DP_Table< T > maximize(DdStructure< 2 >& dd, int top_K, T INF) {
		const NodeTableHandler< 2 >& diagram = dd.getDiagram();
		int N = dd.topLevel();
		
		DP_Table< T > result(N + 1, top_K, INF);
		
		for (int lev = N; lev >= 0; --lev) {
			int w = (*diagram)[lev].size();
			result.setWidth(lev, w);
		}
		
		result.setInitValue(T(0));
		
		Vec< T > zero_skip(N + 1, T(0));
		for (int i = 1; i <= N; ++i) zero_skip[i] = zero_skip[i - 1] + values.getValue(i - 1, 0);
		
		for (int level = N; level > 0; --level) {
			const MyVector< Node< 2 > >& nodes = (*diagram)[level];
			int m = nodes.size(), i = N - level;
			
			for (int j = 0; j < m; ++j) {
				for (int b = 0; b < 2; ++b) {
					const NodeId& c = nodes[j].branch[b];
					int ni = c.row(), nj = c.col();
					T add_value = values.getValue(i, b) + zero_skip[N - ni] - zero_skip[i + 1];
					result.maxUpdate(level, j, ni, nj, b, add_value);
				}
			}
		}
		
		return result;
	}
	
	const DP_Table< T > minimize(DdStructure< 2 >& dd, int top_K, T INF) {
		const NodeTableHandler< 2 >& diagram = dd.getDiagram();
		int N = dd.topLevel();
		
		DP_Table< T > result(N + 1, top_K, INF);
		
		for (int lev = N; lev >= 0; --lev) {
			int w = (*diagram)[lev].size();
			result.setWidth(lev, w);
		}
		
		result.setInitValue(T(0));
		
		Vec< T > zero_skip(N + 1, T(0));
		for (int i = 1; i <= N; ++i) zero_skip[i] = zero_skip[i - 1] + values.getValue(i - 1, 0);
		
		for (int level = N; level > 0; --level) {
			const MyVector< Node< 2 > >& nodes = (*diagram)[level];
			int m = nodes.size(), i = N - level;
			
			for (int j = 0; j < m; ++j) {
				for (int b = 0; b < 2; ++b) {
					const NodeId& c = nodes[j].branch[b];
					int ni = c.row(), nj = c.col();
					T add_value = values.getValue(i, b) + zero_skip[N - ni] - zero_skip[i + 1];
					result.minUpdate(level, j, ni, nj, b, add_value);
				}
			}
		}
		
		return result;
	}
};

}

#endif // __OPTIMIZER_HPP__
