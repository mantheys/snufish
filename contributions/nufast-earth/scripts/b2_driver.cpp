// SNUfish B2 driver for NuFast-Earth: |V_ei|^2 at a solar production point,
// from Probability_Engine::Calculate_Solar_Probability (adiabatic; private,
// so the header is included with private members exposed; NuFast-Earth is
// compiled unchanged).
//
// Usage: b2_driver s12sq s13sq s23sq delta_deg dm2_21 dm2_31 < points
// points: lines "E_MeV rhoYe" (rhoYe = n_e in N_A/cm^3). Output: E rhoYe F1 F2 F3

#include <cmath>
#include <cstdio>
#include <cstdlib>

#include "Earth.h"
#include "Matrix.h"
#define private public
#include "NuFastEarth.h"
#undef private

using namespace NuFast;

int main(int argc, char **argv)
{
	if (argc != 7)
	{
		fprintf(stderr, "usage: %s s12sq s13sq s23sq delta_deg dm2_21 dm2_31 < points\n", argv[0]);
		return 1;
	}
	double p[6];
	for (int i = 0; i < 6; i++) p[i] = atof(argv[i + 1]);

	Probability_Engine engine;
	engine.Set_Oscillation_Parameters(p[0], p[1], p[2], p[3] * M_PI / 180, p[4], p[5], true);
	engine.Precalc();

	double energy_mev, rhoYe;
	while (scanf("%lf %lf", &energy_mev, &rhoYe) == 2)
	{
		Matrix3r prob = engine.Calculate_Solar_Probability(rhoYe * 1e-3 * energy_mev);
		printf("%.10g %.10g %.15g %.15g %.15g\n", energy_mev, rhoYe, prob.arr[0][0], prob.arr[0][1], prob.arr[0][2]);
	}
	return 0;
}
