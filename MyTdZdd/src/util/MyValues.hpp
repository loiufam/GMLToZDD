#ifndef MY_VALUES_HPP
#define MY_VALUES_HPP

#include <vector>
#include <cassert>

namespace hybriddd {

template < typename T >
class MyValues {
private:
	size_t num_of_items;
	
	T upper_value;
	T lower_value;
	std::vector< T > value[2];
	
public:
	MyValues(size_t num_of_items)
	: num_of_items(num_of_items) {
		for (size_t i = 0; i < 2; ++i) value[i].assign(num_of_items, T(0));
	}
	
	size_t getNumOfItems() const { return num_of_items; }
	
	void setUpper(T upper) { upper_value = upper; }
	T getUpper() const { return upper_value; }
	
	void setLower(T lower) { lower_value = lower; }
	T getLower() const { return lower_value; }
	
	void setValue(size_t i, T val0, T val1) {
		assert(0 <= i && i < num_of_items);
		value[0][i] = val0;
		value[1][i] = val1;
	}
	
	T getValue(size_t i, size_t j) const {
		assert(0 <= i && i < num_of_items);
		return value[j][i];
	}
};

} // namespace hybriddd

#endif // MY_VALUES_HPP
