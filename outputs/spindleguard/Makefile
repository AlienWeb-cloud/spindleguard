CC = clang
CFLAGS = -std=c11 -O2 -g -Wall -Wextra -Werror -D_DARWIN_C_SOURCE -D_FILE_OFFSET_BITS=64 -I/usr/local/include/fuse
LDLIBS = -L/usr/local/lib -lfuse-t -lpthread

all: build/spindleguard

build/spindleguard: src/main.c src/loopback_subset.h
	mkdir -p build
	$(CC) $(CFLAGS) src/main.c -o $@ $(LDLIBS)

test: all
	python3 tests/proof.py
