# Builds the B2 and B3 drivers against the pinned NuFast-Earth sources (submodule).
NUFAST = NuFast-Earth
LIB = $(addprefix $(NUFAST)/src/,NuFastEarth.cpp Oscillation.cpp Earth.cpp Geometry.cpp Solar.cpp)

all: b2_driver b3_driver

b%_driver: b%_driver.cpp $(LIB)
	g++ -O3 -std=c++17 -I$(NUFAST)/include $< $(LIB) -o $@

clean:
	rm -f b2_driver b3_driver
