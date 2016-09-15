#ifndef ITEM_CNT_HPP
#define ITEM_CNT_HPP

#include <tdzdd/DdSpec.hpp>
#include "../util/IntSubset.hpp"

namespace hybriddd {

class ITEM_CNT : public tdzdd::DdSpec< ITEM_CNT, int, 2 > {
private:
	const int n;
	const Vec< bool > is_candidate;
	const IntSubset constraint;
	
public:
	ITEM_CNT(int n_, Vec< bool > is_candidate_, IntSubset constraint_ = IntSubset())
	: n(n_), is_candidate(is_candidate_), constraint(constraint_) {}
	
	int getRoot(int& counter) const {
		counter = 0;
		return (!constraint.empty() && constraint.lower() > n) ? 0 : n;
	}
	
	int getChild(int& counter, int level, bool take) const {
		assert(1 <= level && level <= n);
		
		if (constraint.empty()) {
			--level;
			return level;
		}
		
		int i = n - level;
		
		if (take) {
			if (is_candidate[i]) ++counter;
			if (constraint.upper() < counter) return 0;
		}
		
		if (++i == n) return constraint.contain(counter) ? -1 : 0;
		return n - i;
	}
};

} // namespace hybriddd

#endif // ITEM_CNT_HPP
