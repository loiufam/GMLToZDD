#include "MyTdZdd.hpp"
using namespace tdzdd;
using namespace hybriddd;

#include <iostream>

int main(int argc, char* argv[]) {
	MyTdZdd mytdzdd(argv[1], "as-is");
	MyEval result = mytdzdd.S_T_Path(0, 4, true);
	result.dump(std::cout);
}
