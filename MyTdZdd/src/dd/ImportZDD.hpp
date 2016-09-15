#ifndef IMPORT_ZDD_HPP
#define IMPORT_ZDD_HPP

#include <cassert>
#include <iostream>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>
#include <set>
#include <unordered_map>
#include <algorithm>

#include <tdzdd/DdSpec.hpp>

class ImportZDD : public tdzdd::DdSpec< ImportZDD, long long, 2 > {
public:
	typedef long long lint;
	static const lint term0 = -2;
	static const lint term1 = -1;

	struct NodeF {
	public:
		lint adr; int lev; lint zero, one;
	
		NodeF() {}
	
		NodeF(lint adr_, int lev_, lint zero_, lint one_)
		: adr(adr_), lev(lev_), zero(zero_), one(one_) {}	
	};
	
private:
	int top_level;
	lint root_adr;
	std::unordered_map< lint, NodeF > adr2node;
	
	lint str2adr(string str) {
		if (str == "F") return term0;
		if (str == "T") return term1;
		std::stringstream ss;
		ss << str;
		lint res;
		ss >> res;
		return res;
	}
	
public:	
	ImportZDD(std::ifstream& ifs) {
		adr2node.clear();
		
		string dumy;
		lint nodeNums;
		
		ifs >> dumy >> top_level;
		ifs >> dumy >> nodeNums;
		ifs >> dumy >> nodeNums;
		
		for (lint i = 0; i < nodeNums; ++i) {
			lint adr; int lev; string zero, one;			
			ifs >> adr >> lev >> zero >> one;
			//cout << adr << " " << lev << " " << zero << " " << one << endl;	
			adr2node[adr] = NodeF(adr, lev, str2adr(zero), str2adr(one));
		}
		
		ifs >> root_adr;
	}
	
	int getRoot(lint& adr) const {
		adr = root_adr;
		//cout << top_level << endl;
		return top_level;
	}
	
	int getChild(lint& adr, int lev, bool take) const {
		NodeF cnode = adr2node.at(adr);
		
		adr = take ? cnode.one : cnode.zero;
		
		if (adr == term0) return 0;
		if (adr == term1) return -1;
		
		NodeF nnode = adr2node.at(adr);
		
		lev = nnode.lev;
		//cout << lev << endl;
		return lev;
	}
};

#endif // IMPORT_ZDD_HPP
