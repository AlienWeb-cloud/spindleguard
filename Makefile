.PHONY: all test
all:
	$(MAKE) -C outputs/spindleguard all
test:
	$(MAKE) -C outputs/spindleguard test
