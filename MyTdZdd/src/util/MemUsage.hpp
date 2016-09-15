#ifndef MEM_USAGE_HPP
#define MEM_USAGE_HPP

#include <sys/resource.h>

long long get_maxmem() {
	struct rusage r;
	if (getrusage(RUSAGE_SELF, &r) != 0) {
		std::cerr << "get max mem fail" << std::endl;
	}
	return r.ru_maxrss / 1000;
}

#endif // MEM_USAGE_HPP
