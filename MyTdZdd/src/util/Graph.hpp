#ifndef GRAPH_HPP
#define GRAPH_HPP

#include <iostream>
#include <cassert>
#include <set>
#include <map>
#include <queue>
#include <algorithm>

#include "commons.hpp"

namespace hybriddd {

class Graph {
public:
	struct Edge {
		int v1, v2;
		size_t i1, i2;
		bool in1, in2, out1, out2;
		
		Edge(int v1, int v2) : v1(v1), v2(v2) {
			i1 = i2 = size_t(1e9);
			in1 = out1 = in2 = out2 = false;
		}
		
		void dump(std::ostream& os) const {
			os << "Edge(" << v1 << ", " << v2 << ")\n";
			os << v1 << " index : " << i1
			   << " in : " << (in1 ? "true" : "false")
			   << " out : " << (out1 ? "true" : "false") << "\n";
			os << v2 << " index : " << i2
			   << " in : " << (in2 ? "true" : "false")
			   << " out : " << (out2 ? "true" : "false") << "\n";
		}
		
		bool operator == (const Edge& e) const {
			return v1 == e.v1 && v2 == e.v2 &&
				   in1 == e.in1 && in2 == e.in2 &&
				   out1 == e.out1 && out2 == e.out2;
		}
		
		class Hash {
		public:
			size_t operator() (const Edge& e) const {
				return (e.v1 << 16) + e.v2;
			}
		};
	};
	
	struct AddInfo {
		int rm1, rm2;
		USet< int > adj1, adj2;
		USet< int > frontier;
		AddInfo() { rm1 = rm2 = -1; }
	};
	
	typedef std::pair< int, int > pii;
	
	class PiiHash {
	public:
		size_t operator() (const pii& p) const {
			return (p.first << 16) + p.second;
		}
	};
	
protected:
	bool ordered;
	size_t num_of_V;
	size_t max_fsize;
	MyUMap< Edge, size_t, Edge::Hash > lev_of_edge;	
	MyUMap< pii, size_t, PiiHash > Emap;
	Vec< pii > asisvec;
	
protected:
	Vec< Edge > edges;
	Vec< AddInfo > addinfo_vec;
	Vec< size_t > mate_index;
	
public:
	Graph() : ordered(false) {}
	Graph(size_t num_of_V) : ordered(false), num_of_V(num_of_V) {}
	
	void addEdge(int v1, int v2) {
		assert(0 <= v1 && v1 < (int)num_of_V);
		assert(0 <= v2 && v2 < (int)num_of_V);
		++Emap[pii(v1, v2)];
		asisvec.push_back(pii(v1, v2));
	}
	
	size_t getNumOfV() const { return num_of_V; }
	
	size_t getNumOfE() const { return edges.size(); }
	
	Edge getEdge(size_t i) const {
		assert(0 <= i && i < getNumOfE());
		return edges[i];
	}
	
	AddInfo getAddInfo(size_t i) const {
		assert(0 <= i && i < getNumOfE());
		return addinfo_vec[i];
	}
	
	size_t getMaxFSize() const { return max_fsize; }
	
	size_t getMateI(int v) const {
		assert(0 <= v && v < (int)num_of_V);
		return mate_index[v];
	}
	
	size_t getLevel(const Edge& e) const { return lev_of_edge.at(e); }
	
	bool findEdge(int u, int v) const {	return Emap.count(pii(u, v)); }
	
	bool isAdj(int u, int v) const { return findEdge(u, v) || findEdge(v, u); }
	
public:
	bool isOrdered() const { return ordered; }
	
	void setOrder(std::string type = "bfs") {
		assert(Emap.size() > 0);
		ordered = false;
		
		edges.clear();
		addinfo_vec.clear();
		
		if (type == "dfs") dfsOrdering();
		else if (type == "greedy") greedyOrdering();
		else if (type == "as-is") asisOrdering();
		else bfsOrdering();
		
		setMateOrder();
		ordered = true;
	}
	
private:	
	void asisOrdering() { for (pii& p : asisvec) edges.push_back(Edge(p.first, p.second)); }
	
	void greedyOrdering() {
		Vec< int > deg(num_of_V + 1, 0);
		MyUSet< pii, PiiHash > used;
		
		for (pii& p : asisvec) {
			int u = p.first, v = p.second;
			++deg[u];
			++deg[v];
		}
		
		deg[num_of_V] = int(1e9);
		
		std::set< int > frontier;
		
		while (1) {
			auto it1 = frontier.begin(), eitf = frontier.end();
			std::set< int > out_v;
			
			for (; it1 != eitf; ++it1) {
				int u = *it1;
				
				auto it2 = it1;
				++it2;
				
				for (; it2 != eitf; ++it2) {
					int v = *it2;
					
					if (used.count(pii(u, v)) == 0 && findEdge(u, v)) {
						int cnt = Emap.at(pii(u, v));
						for (int i = 0; i < cnt; ++i) edges.push_back(Edge(u, v));
						deg[u] -= cnt;
						deg[v] -= cnt;
						used.insert(pii(u, v));
					}
					
					if (used.count(pii(v, u)) == 0 && findEdge(v, u)) {
						int cnt = Emap.at(pii(v, u));
						for (int i = 0; i < cnt; ++i) edges.push_back(Edge(v, u));
						deg[u] -= cnt;
						deg[v] -= cnt;
						used.insert(pii(v, u));
					}
					
					if (deg[u] == 0) out_v.insert(u);
					if (deg[v] == 0) out_v.insert(v);
				}
			}
			
			for (int v : out_v) frontier.erase(v);
			
			int piv = num_of_V;
			
			if (frontier.size() == 0) {
				for (int v = 0; v < (int)num_of_V; ++v)
					if (deg[v] > 0 && deg[piv] > deg[v]) piv = v;
				if (piv == (int)num_of_V) break;
			} else {
				auto itf = frontier.begin(), eitf = frontier.end();
				for (; itf != eitf; ++itf) {
					int x = *itf;
					if (deg[piv] > deg[x]) piv = x;
				}
			}
			
			int u = piv;
			for (int v = 0; v < (int)num_of_V; ++v) {				
				if (used.count(pii(u, v)) == 0 && findEdge(u, v)) {
					frontier.insert(v);
					int cnt = Emap.at(pii(u, v));	
					for (int i = 0; i < cnt; ++i) edges.push_back(Edge(u, v));
					deg[u] -= cnt;
					deg[v] -= cnt;
					used.insert(pii(u, v));
				}
				
				if (used.count(pii(v, u)) == 0 && findEdge(v, u)) {
					frontier.insert(v);
					int cnt = Emap.at(pii(v, u));
					for (int i = 0; i < cnt; ++i) edges.push_back(Edge(v, u));
					deg[u] -= cnt;
					deg[v] -= cnt;
					used.insert(pii(v, u));
				}
				
				if (deg[u] == 0) frontier.erase(u);
				if (deg[v] == 0) frontier.erase(v);
			}
		}
	}
	
	void dfs(int v, Vec< bool >& vis, MyUSet< pii, PiiHash >& used) {
		if (vis[v]) return;
		vis[v] = true;
		
		for (int u = 0; u < (int)num_of_V; ++u) {
			if (used.count(pii(u, v))) continue;
			
			if (findEdge(u, v)) {
				int cnt = Emap.at(pii(u, v));
				for (int i = 0; i < cnt; ++i) edges.push_back(Edge(u, v));
			}
			
			if (findEdge(v, u)) {
				int cnt = Emap.at(pii(v, u));
				for (int i = 0; i < cnt; ++i) edges.push_back(Edge(v, u));
			}
			
			used.insert(pii(u, v));
			used.insert(pii(v, u));
			
			if (isAdj(u, v)) dfs(u, vis, used);
		}
	}
	
	void dfsOrdering() {
		Vec< bool > vis(num_of_V, false);
		MyUSet< pii, PiiHash > used;
		for (int v = 0; v < (int)num_of_V; ++v) dfs(v, vis, used);
	}
	
	void bfsOrdering() {
		Vec< Vec< int > > adjlist(num_of_V);
		
		auto it = Emap.begin(), eit = Emap.end();
		for (; it != eit; ++it) {
			pii p = (*it).first;
			int u = p.first, v = p.second;
			adjlist[u].push_back(v);
			adjlist[v].push_back(u);
		}
		
		for (size_t v = 0; v < num_of_V; ++v)
			std::sort(adjlist[v].begin(), adjlist[v].end());
		
		Vec< bool > vis(num_of_V, false);
		MyUSet< pii, PiiHash > used;
		
		for (int u = 0; u < (int)num_of_V; ++u) {
			if (vis[u]) continue;
			
			std::queue< int > que;
			que.push(u);
			
			while (!que.empty()) {
				int v = que.front(); que.pop();
				
				if (vis[v]) continue;
				vis[v] = true;
				
				size_t adjnum = adjlist[v].size();
				for (size_t i = 0; i < adjnum; ++i) {
					int ui = adjlist[v][i];
					
					if (!vis[ui]) que.push(ui);
					
					if (used.count(pii(ui, v))) continue;
					
					if (findEdge(ui, v)) {
						int cnt = Emap.at(pii(ui, v));
						for (int i = 0; i < cnt; ++i) edges.push_back(Edge(ui, v));
					}
					
					if (findEdge(v, ui)) {
						int cnt = Emap.at(pii(v, ui));
						for (int i = 0; i < cnt; ++i) edges.push_back(Edge(v, ui));
					}
					
					used.insert(pii(ui, v));
					used.insert(pii(v, ui));
				}
			}
		}
	}
	
	void setMateOrder() {
		size_t num_of_E = getNumOfE();
		
		Vec< int > deg(num_of_V, 0);
		Vec< USet< int > > adjv(num_of_V, USet< int >());
		USet< int > frontier;
		
		auto it = Emap.begin(), eit = Emap.end();
		for (; it != eit; ++it) {
			pii p = (*it).first;
			int u = p.first, v = p.second;
			++deg[u];
			++deg[v];
		}
		
		mate_index.assign(num_of_V, num_of_V + 1);
		std::priority_queue< size_t, Vec< size_t >, std::greater< size_t > > que;
		for (size_t i = 0; i < num_of_V; ++i) que.push(i);
		
		for (size_t i = 0; i < num_of_E; ++i) {
			Edge& e = edges[i];
			AddInfo addinfo;
			
			--deg[e.v1];
			--deg[e.v2];
			
			frontier.insert(e.v1);
			frontier.insert(e.v2);
			
			addinfo.rm1 = deg[e.v1];
			addinfo.rm2 = deg[e.v2];
			addinfo.adj1 = adjv[e.v1];
			addinfo.adj2 = adjv[e.v2];
			addinfo.frontier = frontier;
			
			addinfo_vec.push_back(addinfo);
			
			adjv[e.v1].insert(e.v2);
			adjv[e.v2].insert(e.v1);
			
			if (mate_index[e.v1] == num_of_V + 1) e.in1 = true;
			if (mate_index[e.v2] == num_of_V + 1) e.in2 = true;
			
			if (deg[e.v1] == 0) {
				e.out1 = true;
				frontier.erase(e.v1);
				for (int u = 0; u < (int)num_of_V; ++u)
					adjv[u].erase(e.v1);
			}
			
			if (deg[e.v2] == 0) {
				e.out2 = true;
				frontier.erase(e.v2);
				for (int u = 0; u < (int)num_of_V; ++u)
					adjv[u].erase(e.v2);
			}
			
			if (e.in1) {
				size_t index = que.top(); que.pop();
				e.i1 = mate_index[e.v1] = index;
			} else {
				e.i1 = mate_index[e.v1];
			}
			
			if (e.in2) {
				size_t index = que.top(); que.pop();
				e.i2 = mate_index[e.v2] = index;
			} else {
				e.i2 = mate_index[e.v2];
			}
			
			if (e.out1) que.push(mate_index[e.v1]);
			if (e.out2) que.push(mate_index[e.v2]);
		}
		
		max_fsize = 0;
		for (int v = 0; v < (int)num_of_V; ++v) {
			if (mate_index[v] == num_of_V + 1) continue;
			max_fsize = std::max(max_fsize, mate_index[v] + 1);
		}
	}
};

} // namespace hybriddd

#endif // GRAPH_HPP
