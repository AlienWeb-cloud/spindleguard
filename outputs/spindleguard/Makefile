CC = clang
CFLAGS = -std=c11 -O2 -g -Wall -Wextra -Werror -D_DARWIN_C_SOURCE -D_FILE_OFFSET_BITS=64 -I/usr/local/include/fuse
LDLIBS = -L/usr/local/lib -Wl,-rpath,/usr/local/lib -lfuse-t -lpthread

.PHONY: all test test-control test-bindcheck

all: build/spindleguard

build/spindleguard: Makefile src/main.c src/loopback_subset.h
	mkdir -p build
	$(CC) $(CFLAGS) src/main.c -o $@ $(LDLIBS)

test: all
	python3 -B tests/test_topology.py
	python3 -B tests/proof.py

# No FUSE mounts, no hdiutil, no host /dev or /Volumes.
test-control:
	python3 -B tests/strict.py

# Rewrite each named refusal, expect RED, restore sha256-identical.
test-bindcheck:
	python3 -B tests/run_bindcheck_mutations.py
