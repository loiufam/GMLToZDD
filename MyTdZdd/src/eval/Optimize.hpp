#ifndef OPTIMIZE_HPP
#define OPTIMIZE_HPP

#include <iostream>
#include <string>
#include <algorithm>
#include <cassert>
#include <set>

#include <tdzdd/DdEval.hpp>
#include "../util/MyValues.hpp"
#include "../util/commons.hpp"

namespace hybriddd {

template< typename T >
struct Value {
	T value;
	std::vector< bool > bits;
	
	bool operator == (const Value& v) const { return value == v.value && bits == v.bits; }
	bool operator < (const Value& v) const { return value < v.value; }
	bool operator > (const Value& v) const { return value > v.value; }
	
	Value< T > update(T add, int flag) const {
		Value< T > res{value + add, bits};
		if (flag >= 0) res.bits[flag] = true;
		return res;
	}
};

template< typename T >
class ValueSet {
private:
	int K;
	std::set< Value< T > > values;
	
public:
	ValueSet() {}
	
	void setK(int _K_) { K = _K_; }
	
	void insert(Value< T > val, bool maximize) {
		values.insert(val);
		
		if (values.size() > K && maximize) {
			values.erase(values.begin());
		}
		
		if (values.size() > K && !maximize) {
			auto it = values.end(); --it;
			values.erase(it);
		}
	}
	
	bool empty() { return values.empty(); }
	
	void clear() { values.clear(); }
	
	typename std::set< Value< T > >::iterator begin() const { return values.begin(); }
	typename std::set< Value< T > >::iterator end() const { return values.end(); }
};

template < typename T >
class Optimize : public tdzdd::DdEval< Optimize< T >, ValueSet< T > > {
private:
	const MyValues< T >& values;
	size_t n;
	
	const int K;
	const bool minimize;
	const bool maximize;
	const bool eval_comb;
	
public:
	Optimize(const MyValues< T >& values, std::string mode = "minimize",
			 int _K_ = 1, bool eval_comb = false)
	: values(values),
	n(values.getNumOfItems()), K(_K_),
	minimize(mode == "minimize"),
	maximize(mode == "maximize"),
	eval_comb(eval_comb) {
		assert(minimize || maximize);
	}
		
	void evalTerminal(ValueSet< T >& s, bool one) const {
		s.setK(K);
		if (one) s.insert(Value< T >{0, std::vector< bool >(eval_comb ? n : 0, false)}, maximize);
	}
	
	template < int ARITY >
	void evalNode(ValueSet< T >& s, int i,
				  const DdValues< ValueSet< T >, ARITY >& ddv) const {
		s.setK(K);
		
		for (int b = 0; b < ARITY; ++b) {
			ValueSet< T > sb = ddv.get(b);
			
			T add_val = values.getValue(n - i, b);
			
			int ii = ddv.getLevel(b);
			
			while (++ii < i) {
				add_val += values.getValue(n - ii, 0);
			}
			
			auto it = sb.begin(), eit = sb.end();
			
			for (; it != eit; ++it) {
				s.insert((*it).update(add_val, eval_comb && b > 0 ? n - i : -1), maximize);
			}
		}
	}
};

} // namespace hybriddd

#endif // OPTIMIZE_HPP
