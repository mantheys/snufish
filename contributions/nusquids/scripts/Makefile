# Builds the B3 driver against the nuSQuIDS that build_nusquids.sh installs in ./local.
NUSQUIDS = local
CONFIG = $(NUSQUIDS)/bin/nusquids-config

all: b3_driver

b3_driver: b3_driver.cpp $(CONFIG)
	g++ -O3 -std=c++17 $< -o $@ $$($(CONFIG) --cflags --libs) -Wl,-rpath,$(abspath $(NUSQUIDS))/lib

$(CONFIG):
	./build_nusquids.sh

clean:
	rm -f b3_driver
