# Builds the B3 driver against the pinned NuFast-Earth sources (submodule).
NUFAST = NuFast-Earth
SOURCES = b3_driver.cpp $(addprefix $(NUFAST)/src/,NuFastEarth.cpp Oscillation.cpp Earth.cpp Geometry.cpp Solar.cpp)

b3_driver: $(SOURCES)
	g++ -O3 -std=c++17 -I$(NUFAST)/include $(SOURCES) -o $@

clean:
	rm -f b3_driver
