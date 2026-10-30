// SNUfish B3 driver for NuFast-Earth: prints P(nu_i -> nu_beta) through the
// Earth on an (E, cos nadir) grid.
//
// The public Get_Solar_Night_Probabilities() returns Vsolar x (Earth matrix),
// i.e. already folded with the mass-state fractions at one solar production
// density. B3 needs the Earth matrix alone, which NuFast-Earth keeps in the
// private member solar_night_in_earth[E][cosz] (rows i, columns beta), so
// the header is included with private members exposed. NuFast-Earth itself
// is compiled unchanged. Every point checks Vsolar x (Earth matrix) against
// the public getter, and the driver fails if they differ.
//
// Usage: b3_driver MODEL s12sq s13sq s23sq delta_deg dm2_21 dm2_31 depth_km
//                  E_start E_stop E_step cos_start cos_stop cos_step
// MODEL: prem_prob3 | prem_four | prem_full | native | regions:FILE. Energies in MeV.
// FILE: one radial region per line, innermost first: outer radius (km), Ye, then the coefficients c_k of
// rho(x) = sum_k c_k x^k with x = r / 6371 km (the B3 spec's `regions`); NuFast-Earth takes each crossing's
// mean density, as for its own PREM models.
// Output, one line per grid point: E_MeV cos_nadir m00 m01 m02 m10 ... m22

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>

#include "Earth.h"
#include "Matrix.h"
#define private public
#include "NuFastEarth.h"
#undef private

using namespace NuFast;

#ifndef SOLAR_RHOYE
#define SOLAR_RHOYE (100. * 2. / 3.) // the value in NuFast-Earth's validation
#endif

class Regions : public Earth_Density
{
	public:
		explicit Regions(const char *path)
		{
			FILE *file = fopen(path, "r");
			if (!file) { fprintf(stderr, "cannot read %s\n", path); exit(1); }
			char line[4096];
			while (fgets(line, sizeof line, file))
			{
				std::vector<double> values;
				char *cursor = line, *end;
				for (double v = strtod(cursor, &end); end != cursor; v = strtod(cursor, &end))
				{
					values.push_back(v);
					cursor = end;
				}
				if (values.size() < 3) continue; // blank or comment
				outer.push_back(values[0]);
				ye.push_back(values[1]);
				coefficients.emplace_back(values.begin() + 2, values.end());
			}
			fclose(file);
			n_discontinuities = (int)outer.size();
			discontinuities = outer;
			constant_shells = false;
		}
		double rhoYe(double r)
		{
			for (unsigned int k = 0; k < outer.size(); k++)
				if (r <= outer[k])
				{
					double x = r / r_E, rho = 0, power = 1;
					for (double c : coefficients[k]) { rho += c * power; power *= x; }
					return ye[k] * rho;
				}
			return 0;
		}
	private:
		std::vector<double> outer, ye;
		std::vector<std::vector<double>> coefficients;
};

static std::vector<double> grid(double start, double stop, double step)
{
	std::vector<double> values;
	int n = (int)std::lround((stop - start) / step);
	for (int i = 0; i <= n; i++) values.push_back(start + i * step);
	return values;
}

int main(int argc, char **argv)
{
	if (argc != 15)
	{
		fprintf(stderr, "usage: %s MODEL s12sq s13sq s23sq delta_deg dm2_21 dm2_31 depth_km "
		                "E_start E_stop E_step cos_start cos_stop cos_step\n", argv[0]);
		return 1;
	}
	const char *model = argv[1];
	double p[13];
	for (int i = 0; i < 13; i++) p[i] = atof(argv[i + 2]);

	std::unique_ptr<Earth_Density> earth;
	if (!strcmp(model, "prem_prob3")) earth.reset(new PREM_Prob3());
	else if (!strcmp(model, "prem_four")) earth.reset(new PREM_Four());
	else if (!strcmp(model, "prem_full")) earth.reset(new PREM_Full());
	else if (!strcmp(model, "native")) earth.reset(new PREM_NDiscontinuityLayer(2, 10, 10, 5));
	else if (!strncmp(model, "regions:", 8)) earth.reset(new Regions(model + 8));
	else { fprintf(stderr, "unknown model %s\n", model); return 1; }

	std::vector<double> energies_mev = grid(p[7], p[8], p[9]);
	std::vector<double> cos_nadirs = grid(p[10], p[11], p[12]);
	std::vector<double> energies_gev, coszs;
	for (double e : energies_mev) energies_gev.push_back(1e-3 * e);
	for (double c : cos_nadirs) coszs.push_back(-c);

	Probability_Engine engine;
	engine.Set_Oscillation_Parameters(p[0], p[1], p[2], p[3] * M_PI / 180, p[4], p[5], true);
	engine.Set_Spectra(energies_gev, coszs);
	engine.Set_Earth(p[6], earth.get());
	// Required by an assertion in Get_Solar_Night_Probabilities, though the
	// mass-state-to-flavour night matrix does not depend on it.
	engine.Set_rhoYe_Sun(SOLAR_RHOYE);
	std::vector<std::vector<Matrix3r>> folded = engine.Get_Solar_Night_Probabilities();
	const std::vector<std::vector<Matrix3r>> &night = engine.solar_night_in_earth;
	double worst = 0;
	for (unsigned int i = 0; i < energies_mev.size(); i++)
		for (unsigned int j = 0; j < cos_nadirs.size(); j++)
		{
			Matrix3r product = engine.Vsolar[i] * night[i][j];
			for (int a = 0; a < 3; a++)
				for (int b = 0; b < 3; b++)
					worst = std::fmax(worst, std::fabs(product.arr[a][b] - folded[i][j].arr[a][b]));
		}
	if (worst > 1e-12)
	{
		fprintf(stderr, "Vsolar x Earth matrix differs from the public getter by %g\n", worst);
		return 2;
	}

	for (unsigned int i = 0; i < energies_mev.size(); i++)
		for (unsigned int j = 0; j < cos_nadirs.size(); j++)
		{
			printf("%.10g %.10g", energies_mev[i], cos_nadirs[j]);
			for (int a = 0; a < 3; a++)
				for (int b = 0; b < 3; b++)
					printf(" %.15g", night[i][j].arr[a][b]);
			printf("\n");
		}
	return 0;
}
