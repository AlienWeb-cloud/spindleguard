.PHONY: all test test-control test-bindcheck app
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
