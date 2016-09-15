#ifndef MY_TD_ZDD_HPP
#define MY_TD_ZDD_HPP

#include <fstream>
#include <string>
#include <sstream>

#include "./src/dd_pack.hpp"
#include "./MyEval.hpp"

namespace hybriddd {

class MyTdZdd {
private:
	HybridGraph graph;
	MessageHandler mh;
	DdStructure< 2 > dd;
	bool vvar;
	
public:
	MyTdZdd() {}
	
	MyTdZdd(std::string file_name, std::string var_order = "bfs") {
		inputGraph(file_name, var_order);
	}
	
	void inputGraph(std::string file_name, std::string var_order) {
		std::ifstream ifs(file_name.c_str());
		if (ifs.fail()) fopen_err(file_name);
		
		int V, E;
		ifs >> V >> E;
		
		graph = HybridGraph(V);
		
		for (int i = 0; i < E; ++i) {
			int u, v;
			ifs >> u >> v;
			graph.addEdge(u, v);
		}
		
		ifs.close();
		
		graph.setOrder(var_order);
		graph.setItems();
		
		vvar = false;
	}
	
	void setGraph(HybridGraph graph_) {
		assert(graph_.isOrdered());		
		graph = graph_;
		graph.setItems();
		vvar = false;
	}
	
	void reordering(std::string var_order) {
		graph.setOrder(var_order);
		graph.setItems();
	}
	
	const HybridGraph& getGraph() const { return graph; }
	bool isVVar() const { return vvar; }
	
public:
	void setShowMessages() { MessageHandler::showMessages(); }
	
	MyEval Power() {
		std::stringstream ss;
		ss << "power set";
		
		mh.begin(ss.str().c_str());
		
		MyEval result;
		
		result.setEnumerateType("power set");
		result.setTimer();	
		
		POW_HV power(graph);
		dd = DdStructure< 2 >(power);
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = true;
		return result;
	}
	
	MyEval S_T_Path(int s, int t,
					bool vertex_var = true) {
		if (s < 0 || t < 0) {
			s = 0;
			t = graph.getNumOfV() - 1;
		}
		
		std::stringstream ss;
		ss << s << "-" << t << " path";
		
		MyEval result;
		
		result.setEnumerateType(ss.str());
		result.setTimer();
		
		mh.begin(result.getEnumerateType().c_str());
		
		if (vertex_var) {
			PAC_HV pac(graph, s, t);
			dd = DdStructure< 2 >(pac);
		} else {
			PAC pac(graph, s, t);
			dd = DdStructure< 2 >(pac);
		}
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = vertex_var;
		return result;
	}
	
	MyEval Cycle(bool vertex_var = true) {		
		MyEval result;
		
		result.setEnumerateType("cycle");
		result.setTimer();
		
		mh.begin(result.getEnumerateType().c_str());
		
		if (vertex_var) {
			PAC_HV pac(graph);
			dd = DdStructure< 2 >(pac);
		} else {
			PAC pac(graph);
			dd = DdStructure< 2 >(pac);
		}
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = vertex_var;
		return result;
	}
	
	MyEval Connected(IntSubset cc_constraint,
					 bool vertex_var = true) {
		MyEval result;
		
		result.setEnumerateType("connected");
		result.setTimer();
		
		mh.begin(result.getEnumerateType().c_str());
		
		if (vertex_var) {
			CCS_HV ccs(graph, "connected", cc_constraint);
			dd = DdStructure< 2 >(ccs);
		} else {
			CCS ccs(graph, "connected", cc_constraint);
			dd = DdStructure< 2 >(ccs);
		}
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = vertex_var;
		return result;
	}
	
	MyEval Forest(IntSubset cc_constraint = IntSubset(),
				  IntSubset terminals = IntSubset(),
				  bool vertex_var = true) {
		MyEval result;
		
		result.setEnumerateType(terminals.empty() ?
								"forest" : "steiner forest");
		result.setTimer();
		
		mh.begin(result.getEnumerateType().c_str());
		
		if (vertex_var) {
			CCS_HV ccs(graph, "forest", cc_constraint, terminals);
			dd = DdStructure< 2 >(ccs);
		} else {
			CCS ccs(graph, "forest", cc_constraint, terminals);
			dd = DdStructure< 2 >(ccs);
		}
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = vertex_var;
		return result;
	}
	
	MyEval Tree(IntSubset terminals = IntSubset(),
				bool vertex_var = true) {
		MyEval result;
		
		result.setEnumerateType(terminals.empty() ?
								"tree" : "steiner tree");
		result.setTimer();
		
		mh.begin(result.getEnumerateType().c_str());
		
		if (vertex_var) {
			CCS_HV ccs(graph, "tree", IntSubset(), terminals);
			dd = DdStructure< 2 >(ccs);
		} else {
			CCS ccs(graph, "tree", IntSubset(), terminals);
			dd = DdStructure< 2 >(ccs);
		}
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = vertex_var;
		return result;
	}
	
	MyEval InducedGraphs(bool no_isolate,
						 bool vertex_var = true) {
		MyEval result;
		
		result.setEnumerateType("induced graphs");
		result.setTimer();
				
		mh.begin(result.getEnumerateType().c_str());
		
		if (vertex_var) {
			VIG_HV vig(graph, "normal", no_isolate);
			dd = DdStructure< 2 >(vig);
		} else {
			VIG vig(graph, "normal");
			dd = DdStructure< 2 >(vig);
		}
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = vertex_var;
		return result;
	}
	
	MyEval InducedGraphsConnected(bool no_isolate,
								  bool vertex_var = true) {
		MyEval result;
		
		result.setEnumerateType("induced connected");
		result.setTimer();
		
		mh.begin(result.getEnumerateType().c_str());
		
		if (vertex_var) {
			VIG_HV vig(graph, "connected", no_isolate);
			dd = DdStructure< 2 >(vig);
		} else {
			VIG vig(graph, "connected");
			dd = DdStructure< 2 >(vig);
		}
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = vertex_var;
		return result;
	}
	
	MyEval InducedForest(bool no_isolate,
						 IntSubset cc_constraint,
						 bool vertex_var = true) {		
		MyEval result;
		
		result.setEnumerateType("induced forest");
		result.setTimer();
		
		mh.begin(result.getEnumerateType().c_str());
		
		if (vertex_var) {
			VIG_HV vig(graph, "forest", no_isolate, cc_constraint);
			dd = DdStructure< 2 >(vig);
		} else {
			VIG vig(graph, "forest", cc_constraint);
			dd = DdStructure< 2 >(vig);
		}
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = vertex_var;
		return result;
	}
	
	MyEval InducedTree(bool no_isolate,
					   bool vertex_var = true) {		
		MyEval result;
		
		result.setEnumerateType("induced tree");
		result.setTimer();
		
		mh.begin(result.getEnumerateType().c_str());
		
		if (vertex_var) {
			VIG_HV vig(graph, "tree", no_isolate);
			dd = DdStructure< 2 >(vig);
		} else {
			VIG vig(graph, "tree");
			dd = DdStructure< 2 >(vig);
		}
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = vertex_var;
		return result;
	}
	
	MyEval VertexCut(IntSubset cc_constraint) {
		MyEval result;
		
		result.setEnumerateType("vertex cut");
		result.setTimer();
		
		mh.begin(result.getEnumerateType().c_str());
		
		VCUT_HV vcut(graph, cc_constraint);
		dd = DdStructure< 2 >(vcut);
		
		result.endTimer();
		result.setNDd(dd);
		
		dd.zddReduce();
		
		result.setDd(dd);
		
		mh.end("finish");
		
		vvar = true;
		return result;
	}
};

} // namespace hybriddd

#endif // MY_TD_ZDD
