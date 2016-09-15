#ifndef INT_SUBSET_HPP
#define INT_SUBSET_HPP

#include <iostream>
#include <set>
#include <climits>
#include <algorithm>

namespace hybriddd {

struct IntSubset {
private:
	typedef std::vector< int > Subset;
	Subset subset;
	
public:
	IntSubset() {}

	IntSubset(Subset subset_) : subset(subset_) {
		sorting();
	}
	
	void add(int x) {
		subset.push_back(x);
		sorting();
	}
	
	void remove(int x) {
		Subset::iterator st = lower_bound(subset.begin(), subset.end(), x);
		Subset::iterator ed = upper_bound(subset.begin(), subset.end(), x);
		subset.erase(st, ed);
	}
	
	void unique() {
		subset.erase(std::unique(subset.begin(), subset.end()), subset.end());
	}
	
	void clear() {
		subset.clear();
	}
	
	void sorting() {
		std::sort(subset.begin(), subset.end());
	}
	
	bool contain(int x) const {
		return std::binary_search(subset.begin(), subset.end(), x);
	}
	
	int range_count(int LB, int UB) const {
		return std::upper_bound(subset.begin(), subset.end(), UB) - std::lower_bound(subset.begin(), subset.end(), LB);
	}
	
	int lower() const {
		return *subset.begin();
	}
	
	int upper() const {
		return *subset.rbegin();
	}
	
	size_t size() const {
		return subset.size();
	}
	
	bool empty() const {
		return size() == 0;
	}
	
	void dump(std::ostream& os) const {
		for (size_t i = 0; i < size(); ++i) {
			os << subset[i] << (i < size()-1 ? " " : "\n");
		}
	}
};

} // namespace hybriddd

#endif // INT_SUBSET_HPP
