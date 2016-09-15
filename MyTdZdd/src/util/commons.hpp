#ifndef COMMONS_HPP
#define COMMONS_HPP

#include <iostream>
#include <string>
#include <vector>
#include <unordered_set>
#include <unordered_map>

namespace hybriddd {

template< typename T >
using Vec = std::vector< T >;

template < typename T, class C >
using MyUSet = std::unordered_set< T, C >;

template < typename T >
using USet = std::unordered_set< T >;

template < typename T, typename S, class C >
using MyUMap = std::unordered_map< T, S, C >;

template < typename T, typename S >
using UMap = std::unordered_map< T, S >;

template < typename TYPE, std::size_t SIZE >
std::size_t array_length(const TYPE (&)[SIZE]) { return SIZE; }

void fopen_err(std::string fname) {
	std::cerr << "file open error [" << fname << "]\n";
	exit(1);
}

bool isdouble(std::string s) {
	for (size_t i = 1; i < s.size(); ++i) if (!isdigit(s[i]) && s[i] != '.') return false;
	return true;
}

bool isnumber(std::string s) {
	if (s.size() == 0) return false;
	if (s[0] == '-' && s.size() == 1) return false;
	size_t ini = (s[0] == '-') ? 1 : 0;
	for (size_t i = ini; i < s.size(); ++i) if (!isdigit(s[i])) return false;
	return true;
}

bool iseword(std::string s) {
	for (size_t i = 0; i < s.size(); ++i) if (!isalpha(s[i])) return false;
	return true;
}

} // namespace hybriddd

#endif // COMMONS_HPP
