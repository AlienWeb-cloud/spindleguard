.PHONY: all test test-control test-bindcheck app setup verify verify-full
all:
	$(MAKE) -C outputs/spindleguard all
test:
	$(MAKE) -C outputs/spindleguard test
test-control:
	$(MAKE) -C outputs/spindleguard test-control
test-bindcheck:
	$(MAKE) -C outputs/spindleguard test-bindcheck
app:
	$(MAKE) -C outputs/spindleguard app
setup:
	$(MAKE) -C outputs/spindleguard setup
verify:
	$(MAKE) -C outputs/spindleguard verify
verify-full:
	$(MAKE) -C outputs/spindleguard verify-full
