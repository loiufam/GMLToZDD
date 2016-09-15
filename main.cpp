#include "MyTdZdd.hpp"
using namespace tdzdd;
using namespace hybriddd;

#include <iostream>

int main(int argc, char* argv[]) {
	MyTdZdd mytdzdd(argv[1], "as-is");
	MyEval result = mytdzdd.S_T_Path(0, 4, true);
	
	int I = mytdzdd.getGraph().getNumOfI();
	for (int i = 0; i < I; ++i) {
		HybridGraph::Item item = mytdzdd.getGraph().getItemAf(i);
		std::cout << "Lev." << I - i << " : ";
		if (item.isvertex) std::cout << "v" << item.v << std::endl;
		else std::cout << "e={v" << item.v1 << ", v" << item.v2 << "}" << std::endl;
	}
	
	result.dump(std::cout);
	result.dumpSapporo("sample.zdd");
}
