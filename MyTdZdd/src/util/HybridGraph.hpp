#ifndef HYBRID_GRAPH_HPP
#define HYBRID_GRAPH_HPP

#include "Graph.hpp"

namespace hybriddd {

class HybridGraph : public Graph {
public:
	struct Item {
		int v1, v2;
		size_t i1, i2;
		bool in1, out1, in2, out2;
		
		bool isvertex;
		int v;
		size_t i;
		
		Item() {}
		
		Item(int v1, int v2) : v1(v1), v2(v2) {
			i1 = i2 = 0;
			in1 = out1 = in2 = out2 = false;
			isvertex = false;
		}
		
		Item(int v) : v(v) {
			isvertex = true;
			i = size_t(1e9);
		}
		
		Item(Edge& e) {
			v1 = e.v1; v2 = e.v2;
			i1 = e.i1; i2 = e.i2;
			in1 = e.in1; out1 = e.out1;
			in2 = e.in2; out2 = e.out2;
			isvertex = false;
		}
		
		void dump(std::ostream& os) const {
			if (!isvertex) {
				os << "Edge(" << v1 << ", " << v2 << ")\n";
				os << v1 << " index : " << i1
				   << " in : " << (in1 ? "true" : "false")
				   << " out : " << (out1 ? "true" : "false") << "\n";
				os << v2 << " index : " << i2
				   << " in : " << (in2 ? "true" : "false")
				   << " out : " << (out2 ? "true" : "false") << "\n";
			} else {
				os << "Vertex " << v
				   << " index : " << i << "\n";
			}
		}
		
		bool operator == (const Item& item) const {
			if (isvertex != item.isvertex) return false;
			if (isvertex) return v == item.v && i == item.i;
			return v1 == item.v1 && v2 == item.v2 &&
				   in1 == item.in1 && in2 == item.in2 &&
				   out1 == item.out1 && out2 == item.out2;
		}
		
		class Hash {
		public:
			size_t operator() (const Item& item) const {
				if (item.isvertex) return (item.v << 16) + item.v;
				return (item.v1 << 16) + item.v2;
			}
		};
	};	
	
	struct AddInfoHV {
		int rm1, rm2;
		USet< int > adj1, adj2;
		USet< int > frontier;
		USet< int > adj;
		
		AddInfoHV() { rm1 = rm2 = -1; }
		
		AddInfoHV(const AddInfo& a) {
			rm1 = a.rm1; rm2 = a.rm2;
			adj1 = a.adj1; adj2 = a.adj2;
			frontier = a.frontier;
		}
	};
	
protected:
	bool set_end;
	
	Vec< Item > items_bf;
	Vec< Item > items_af;
	
	Vec< AddInfoHV > addinfo_bf;
	Vec< AddInfoHV > addinfo_af;
	
	MyUMap< Item, size_t, Item::Hash > lev_of_item_bf;
	MyUMap< Item, size_t, Item::Hash > lev_of_item_af;
	
public:
	HybridGraph() : set_end(false) {}
	HybridGraph(size_t num_of_V) : Graph(num_of_V), set_end(false) {}
	
	size_t getNumOfI() const { return items_af.size(); }
	
	Item getItemBf(size_t i) const {
		assert(0 <= i && i < getNumOfI());
		return items_bf[i];
	}
	
	Item getItemAf(size_t i) const {
		assert(0 <= i && i < getNumOfI());
		return items_af[i];
	}
	
	AddInfoHV getAddInfoBf(size_t i) const {
		assert(0 <= i && i < getNumOfI());
		return addinfo_bf[i];
	}
	
	AddInfoHV getAddInfoAf(size_t i) const {
		assert(0 <= i && i < getNumOfI());
		return addinfo_af[i];
	}
	
	size_t getLevelBf(const Item& item) const {
		return lev_of_item_bf.at(item);
	}
	
	size_t getLevelAf(const Item& item) const {
		return lev_of_item_af.at(item);
	}
	
	void setItems() {
		assert(isOrdered());
		
		items_bf.clear();
		items_af.clear();
		
		addinfo_bf.clear();
		addinfo_af.clear();
		
		lev_of_item_bf.clear();
		lev_of_item_af.clear();
		
		std::vector< bool > vis(getNumOfV(), false);
		
		USet< int > frontier;
		size_t num_of_E = getNumOfE();
		size_t lev_bf = getNumOfV() + getNumOfE();
		size_t lev_af = lev_bf;
		
		for (size_t i = 0; i < num_of_E; ++i) {
			Edge e = getEdge(i);
			vis[e.v1] = vis[e.v2] = true;
			
			// bf in
			if (e.in1) {
				Item v1i(e.v1);
				v1i.i = e.i1;
				AddInfoHV addinfo1;
				addinfo1.frontier = frontier;
								
				auto it = frontier.begin(), eit = frontier.end();
				for (; it != eit; ++it) if (isAdj(e.v1, *it)) {
					addinfo1.adj.insert(*it);
				}
				
				items_bf.push_back(v1i);
				addinfo_bf.push_back(addinfo1);
				
				lev_of_item_bf[v1i] = lev_bf;
				--lev_bf;
			}
			
			if (e.in2) {
				Item v2i(e.v2);
				v2i.i = e.i2;
				AddInfoHV addinfo2;
				addinfo2.frontier = frontier;
								
				auto it = frontier.begin(), eit = frontier.end();
				for (; it != eit; ++it) if (isAdj(e.v2, *it)) {
					addinfo2.adj.insert(*it);
				}
				
				items_bf.push_back(v2i);
				addinfo_bf.push_back(addinfo2);
				
				lev_of_item_bf[v2i] = lev_bf;
				--lev_bf;
			}
			
			frontier.insert(e.v1);
			frontier.insert(e.v2);
			
			Item ei(e);
			AddInfoHV addinfo(getAddInfo(i));
			
			// bf
			items_bf.push_back(ei);
			addinfo_bf.push_back(addinfo);
			
			lev_of_item_bf[ei] = lev_bf;
			--lev_bf;
			
			// af
			items_af.push_back(ei);
			addinfo_af.push_back(addinfo);
			
			lev_of_item_af[ei] = lev_af;
			--lev_af;
			
			// af out
			if (e.out1) {
				Item v1i(e.v1);
				v1i.i = e.i1;
				AddInfoHV addinfo1;
				addinfo1.frontier = frontier;
				
				frontier.erase(e.v1);
				
				auto it = frontier.begin(), eit = frontier.end();
				for (; it != eit; ++it) if (isAdj(e.v1, *it)) {
					addinfo1.adj.insert(*it);
				}
				
				items_af.push_back(v1i);
				addinfo_af.push_back(addinfo1);
				
				lev_of_item_af[v1i] = lev_af;
				--lev_af;
			}
			
			if (e.out2) {
				Item v2i(e.v2);
				v2i.i = e.i2;
				AddInfoHV addinfo2;
				addinfo2.frontier = frontier;
				
				frontier.erase(e.v2);
				
				auto it = frontier.begin(), eit = frontier.end();
				for (; it != eit; ++it) if (isAdj(e.v2, *it)) {
					addinfo2.adj.insert(*it);
				}
				
				items_af.push_back(v2i);
				addinfo_af.push_back(addinfo2);
				
				lev_of_item_af[v2i] = lev_af;
				--lev_af;
			}
		}
		
		for (size_t v = 0; v < getNumOfV(); ++v) {
			if (!vis[v]) {
				Item vi(v);
				vi.i = 0;
				
				AddInfoHV addinfo;
				addinfo.frontier = USet< int >();
				
				items_af.push_back(vi);
				addinfo_af.push_back(addinfo);
				
				lev_of_item_af[vi] = lev_af;
				--lev_af;
				
				items_bf.push_back(vi);
				addinfo_bf.push_back(addinfo);
				
				lev_of_item_bf[vi] = lev_bf;
				--lev_bf;
			}
		}
		
		assert(lev_af == 0);
		assert(lev_bf == 0);
		set_end = true;
	}
};

} // namespace hybriddd

#endif // HYBRID_GRAPH_HPP
