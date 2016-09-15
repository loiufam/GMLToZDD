#ifndef MY_EVAL_HPP
#define MY_EVAL_HPP

#include "./src/dd_pack.hpp"
#include <iostream>
#include <string>
#include <sstream>
#include <iomanip>

namespace hybriddd {

class MyEval {
private:
	Timer timer;
	
	double time;		
	DdStructure< 2 > dd, ndd;
	std::string enumerate_type;
	
public:
	MyEval() {}
	
	void setTimer() { timer = Timer(); }
	void endTimer() { time = timer.curTime(); }
	
	void setEnumerateType(std::string type) { enumerate_type = type; }
	void setNDd(DdStructure< 2 >& ndd_) { ndd = ndd_; }
	void setDd(DdStructure< 2 >& dd_) { dd = dd_; }
	
public:
	double getTime(int digit = 2) const {
		return time;
	}
	
	size_t getNonReducedDdSize() const {
		return ndd.size();
	}
	
	size_t getReducedDdSize() const {
		return dd.size();
	}
	
	std::string getCardinality() const {
		return dd.zddCardinality();
	}
	
	std::string getEnumerateType() const {
		return enumerate_type;
	}
	
	DdStructure< 2 > getNDd() const { return ndd; }
	DdStructure< 2 > getDd() const { return dd; }
	
	void dump(std::ostream& os) const {
		os << "# enumerate type : " << getEnumerateType() << endl;	
		os << "# time : " << setprecision(2) << setiosflags(ios::fixed) << getTime() << endl;
		os << "# non reduced dd size : " << getNonReducedDdSize() << endl;
		os << "# reduced dd size : " << getReducedDdSize() << endl;
		os << "# cardinality : " << getCardinality() << endl;
	}
	
	void dumpSapporo(std::string file_name) {
		ofstream ofs(file_name.c_str());
		if (ofs.fail()) fopen_err(file_name);
		dd.dumpSapporo(ofs);
		ofs.close();
	}
	
	void dumpDot(std::string file_name) {
		ofstream ofs(file_name.c_str());
		if (ofs.fail()) fopen_err(file_name);
		dd.dumpDot(ofs);
		ofs.close();
	}
};

} // namespace hybriddd

#endif // MY_EVAL_HPP
