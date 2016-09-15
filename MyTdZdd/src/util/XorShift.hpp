#ifndef XORSHIFT_HPP
#define XORSHIFT_HPP

// randomizer
struct XorShift {
	unsigned int x, y, z, w;
	
	XorShift() {
		init();
	}
	
	XorShift(unsigned int seed) {
		init(seed);
	}
	
	void init(unsigned int seed = 88675123) {
		x = 123456789;
		y = 362436069;
		z = 521288629;
		w = seed;		
	}
	
	unsigned int nextInt(unsigned int n) {
		unsigned int t = x ^ (x << 11);
		x = y;
		y = z;
		z = w;
		w = (w ^ (w >> 19)) ^ (t ^ (t >> 8));
		return w % n;
	}

	unsigned int nextInt() {
		unsigned int t = x ^ (x << 11);
		x = y;
		y = z;
		z = w;
		return w = (w ^ (w >> 19)) ^ (t ^ (t >> 8));
	}

	double nextDouble() {
		unsigned int i = nextInt();
		return i * (1.0 / 0xFFFFFFFFu);
	}
};

#endif // XORSHIFT_HPP
