CC = clang
CFLAGS = -std=c11 -O2 -g -Wall -Wextra -Werror -D_DARWIN_C_SOURCE -D_FILE_OFFSET_BITS=64 -I/usr/local/include/fuse
LDLIBS = -L/usr/local/lib -Wl,-rpath,/usr/local/lib -lfuse-t -lpthread
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)
APP = SpindleGuard.app
APP_MACOS = $(APP)/Contents/MacOS
APP_RES = $(APP)/Contents/Resources
APP_HELP = $(APP)/Contents/Helpers
SWIFT_SRC = \
	macos/SpindleGuardApp.swift \
	macos/AppState.swift \
	macos/PathPolicy.swift \
	macos/SGPaths.swift \
	macos/BrokerService.swift \
	macos/ContentView.swift \
	macos/Panes.swift \
	macos/Wizard.swift

.PHONY: all test test-control test-bindcheck app setup verify verify-full

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

setup:
	python3 -B ./sg setup --json

verify:
	python3 -B ./sg verify --quick --json

verify-full:
	python3 -B ./sg verify --full --json

# Native SwiftUI bundle. Does not require FUSE-T so Doctor/Setup can open first.
# Overwrites bundle files in place; does not delete the tree.
ifeq ($(UNAME_S),Darwin)
ifeq ($(UNAME_M),arm64)
APP_TARGET = arm64-apple-macos13.0
else
APP_TARGET = x86_64-apple-macos13.0
endif
app:
	mkdir -p $(APP_MACOS) $(APP_RES) $(APP_HELP) $(APP_RES)/macos/Resources $(APP_RES)/bindcheck $(APP_RES)/python/sgcontrol $(APP_RES)/tools
	xcrun swiftc -parse-as-library -O \
		-sdk $$(xcrun --sdk macosx --show-sdk-path) \
		-target $(APP_TARGET) \
		-framework SwiftUI -framework AppKit -framework Combine -framework UniformTypeIdentifiers \
		-o $(APP_MACOS)/SpindleGuard \
		$(SWIFT_SRC)
	cp macos/Info.plist $(APP)/Contents/Info.plist
	printf 'APPL????' > $(APP)/Contents/PkgInfo
	cp sg $(APP_RES)/sg
	chmod +x $(APP_RES)/sg $(APP_MACOS)/SpindleGuard
	if [ -x build/spindleguard ]; then \
		cp build/spindleguard $(APP_HELP)/spindleguard; \
		chmod +x $(APP_HELP)/spindleguard; \
	else \
		echo "Note: broker helper not built yet (need FUSE-T). UI still opens; use Setup."; \
	fi
	cp -R bindcheck/*.py $(APP_RES)/bindcheck/
	cp -R python/sgcontrol/*.py $(APP_RES)/python/sgcontrol/
	cp python/__init__.py $(APP_RES)/python/__init__.py
	cp python/sgcontrol/__init__.py $(APP_RES)/python/sgcontrol/__init__.py
	cp tools/topology.py $(APP_RES)/tools/topology.py
	cp macos/Resources/*.json $(APP_RES)/
	cp macos/Resources/*.json $(APP_RES)/macos/Resources/
	cp macos/preview.html $(APP_RES)/preview.html
	@echo "Built $(APP)"
	@echo "  open $(APP)"
	@echo "  ./sg app"
	@echo "  ./sg setup"
else
app:
	@echo "Error: make app requires macOS (native SwiftUI bundle)."
	@echo "  make app"
	@echo "  Example: make -C outputs/spindleguard app"
	@exit 2
endif
