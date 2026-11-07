// nuSQuIDS driver for SNUfish B3: P(nu_i -> nu_e) after the Earth chord of nadir angle eta, detector at the
// surface, oscillations only. One single-energy nuSQUIDS per energy: GSL's step is then set by that energy's
// oscillation length, not by the lowest energy of the grid.
//
//   b3_driver <mode> s12 s13 s23 delta_deg dm21 dm31 rel_err abs_err E0 E1 dE  cos... < model
//
// mode "shells": constant shells. Each chord segment is a nuSQuIDS ConstantDensity body, evolved exactly
//   (Set_AllowConstantDensityOscillationOnlyEvolution: rotation to the propagation eigenstates, no GSL).
// mode "regions": PREM polynomials rho(x) = sum_k c_k x^k, x = r/R_E, evaluated along the chord by a Body
//   subclass; nuSQuIDS integrates with GSL (rel_err, abs_err), one EvolveState per region crossing so
//   that no step straddles a density jump.
// mode "native": nuSQuIDS's own Earth body (data/astro/EARTH_MODEL_PREM.dat, Akima spline), one track.
// model (stdin, modes shells and regions), one line per region from the centre out:
//   outer_radius_km ye c0 [c1 c2 ...]
// Output: E_MeV cos_nadir P1e P2e P3e per line.
#include <nuSQuIDS/nuSQuIDS.h>

#include <cmath>
#include <cstdio>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace nusquids;

struct Region { double outer_km, ye; std::vector<double> c; };
static const double R_EARTH_KM = 6371.0;  // B3 spec earth.radius_km

// position along the chord (eV^-1, 0 at the entry point) -> radius in km
static double radius_km(double x, double chord_km, const squids::Const& u) {
  double xkm = x / u.km;
  double r2 = R_EARTH_KM * R_EARTH_KM + xkm * xkm - chord_km * xkm;
  return r2 > 0 ? std::sqrt(r2) : 0.0;
}

// The spec's PREM polynomials along one chord.
class Chord : public Body {
 public:
  class Track : public Body::Track {
   public:
    Track(double xini, double xend) : Body::Track(xini, xini, xend) {}
    void Serialize(hid_t) const override { throw std::runtime_error("not serialisable"); }
  };
  Chord(std::vector<Region> regions, double chord_km) : regions(std::move(regions)), chord_km(chord_km) {}
  void Serialize(hid_t) const override { throw std::runtime_error("not serialisable"); }
  double density(const GenericTrack& t) const override { return eval(t, false); }
  double ye(const GenericTrack& t) const override { return eval(t, true); }

 private:
  std::vector<Region> regions;
  double chord_km;
  squids::Const u;
  double eval(const GenericTrack& t, bool want_ye) const {
    double r = radius_km(t.GetX(), chord_km, u);
    // the region of the segment's midpoint: segments never straddle a border, so this is unambiguous
    double rmid = radius_km(0.5 * (t.GetInitialX() + t.GetFinalX()), chord_km, u);
    const Region* reg = &regions.back();
    for (const auto& g : regions) if (rmid <= g.outer_km) { reg = &g; break; }
    if (want_ye) return reg->ye;
    double x = r / R_EARTH_KM, rho = 0, p = 1;
    for (double c : reg->c) { rho += c * p; p *= x; }
    return rho;
  }
};

// chord positions (km from the entry) where it crosses region borders, with the region of each segment
static std::vector<std::pair<double, double>> segments(const std::vector<Region>& regions, double cos_nadir,
                                                       std::vector<int>& which) {
  double chord = 2 * R_EARTH_KM * cos_nadir, b = R_EARTH_KM * std::sqrt(std::max(0.0, 1 - cos_nadir * cos_nadir));
  std::vector<double> cuts{0.0, chord};
  for (size_t k = 0; k + 1 < regions.size(); ++k) {
    double rk = regions[k].outer_km;
    if (rk > b) {
      double h = std::sqrt(rk * rk - b * b);
      cuts.push_back(chord / 2 - h);
      cuts.push_back(chord / 2 + h);
    }
  }
  std::sort(cuts.begin(), cuts.end());
  std::vector<std::pair<double, double>> out;
  which.clear();
  for (size_t k = 0; k + 1 < cuts.size(); ++k) {
    if (cuts[k + 1] - cuts[k] <= 0) continue;
    double mid = 0.5 * (cuts[k] + cuts[k + 1]), s = mid - chord / 2, r = std::sqrt(b * b + s * s);
    int w = regions.size() - 1;
    for (size_t g = 0; g < regions.size(); ++g) if (r <= regions[g].outer_km) { w = g; break; }
    out.push_back({cuts[k], cuts[k + 1]});
    which.push_back(w);
  }
  return out;
}

int main(int argc, char** argv) {
  if (argc < 14) { std::cerr << "usage: see the header of b3_driver.cpp\n"; return 1; }
  std::string mode = argv[1];
  double s12 = std::stod(argv[2]), s13 = std::stod(argv[3]), s23 = std::stod(argv[4]), delta = std::stod(argv[5]);
  double dm21 = std::stod(argv[6]), dm31 = std::stod(argv[7]), rel = std::stod(argv[8]), abs_err = std::stod(argv[9]);
  double e0 = std::stod(argv[10]), e1 = std::stod(argv[11]), de = std::stod(argv[12]);
  std::vector<double> cosines;
  for (int k = 13; k < argc; ++k) cosines.push_back(std::stod(argv[k]));

  std::vector<Region> regions;
  if (mode != "native") {
    std::string line;
    while (std::getline(std::cin, line)) {
      std::istringstream in(line);
      Region g;
      if (!(in >> g.outer_km >> g.ye)) continue;
      double c;
      while (in >> c) g.c.push_back(c);
      regions.push_back(g);
    }
  }

  squids::Const u;
  int n = static_cast<int>(std::lround((e1 - e0) / de)) + 1;
  marray<double, 1> energies({static_cast<size_t>(n)});
  for (int i = 0; i < n; ++i) energies[i] = (e0 + i * de) * u.MeV;

  auto native = std::make_shared<Earth>();
  for (double cn : cosines) {
    double chord_km = 2 * R_EARTH_KM * cn;
    std::vector<int> which;
    auto segs = segments(regions, cn, which);
    auto chord = std::make_shared<Chord>(regions, chord_km);
    for (int i = 0; i < n; ++i) {
      double prob[3];
      for (int state = 0; state < 3; ++state) {
        nuSQUIDS nus(marray<double, 1>({1}, {energies[i]}), 3, neutrino, false);
        nus.Set_MixingAngle(0, 1, std::asin(std::sqrt(s12)));
        nus.Set_MixingAngle(0, 2, std::asin(std::sqrt(s13)));
        nus.Set_MixingAngle(1, 2, std::asin(std::sqrt(s23)));
        nus.Set_CPPhase(0, 2, delta * M_PI / 180.0);
        nus.Set_SquareMassDifference(1, dm21);
        nus.Set_SquareMassDifference(2, dm31);
        nus.Set_rel_error(rel);
        nus.Set_abs_error(abs_err);
        nus.Set_ProgressBar(false);
        nus.Set_AllowConstantDensityOscillationOnlyEvolution(mode == "shells");
        nus.Set_Body(std::make_shared<Vacuum>());  // a body and track must be set before the initial state
        nus.Set_Track(std::make_shared<Vacuum::Track>(0.0));
        marray<double, 2> ini({1, 3});
        for (int k = 0; k < 3; ++k) ini[0][k] = (k == state);
        nus.Set_initial_state(ini, mass);
        if (chord_km > 0) {
          if (mode == "native") {
            nus.Set_Body(native);
            nus.Set_Track(std::make_shared<Earth::Track>(chord_km * u.km));
            nus.EvolveState();
          } else {
            for (size_t k = 0; k < segs.size(); ++k) {
              double xa = segs[k].first * u.km, xb = segs[k].second * u.km;
              if (mode == "shells") {
                const Region& g = regions[which[k]];
                nus.Set_Body(std::make_shared<ConstantDensity>(g.c.at(0), g.ye));
                nus.Set_Track(std::make_shared<ConstantDensity::Track>(xa, xb));
              } else {
                nus.Set_Body(chord);
                nus.Set_Track(std::make_shared<Chord::Track>(xa, xb));
              }
              nus.EvolveState();
            }
          }
        }
        prob[state] = nus.EvalFlavorAtNode(0, 0);
      }
      std::printf("%.10g %.10g %.17g %.17g %.17g\n", e0 + i * de, cn, prob[0], prob[1], prob[2]);
    }
    std::fflush(stdout);
  }
  return 0;
}
