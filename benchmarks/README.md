# Benchmarks

Full description of every benchmark: [docs/benchmarks.md](../docs/benchmarks.md).

The benchmarks are the calculator's steps, in the same order and under the
same names: B1 Oscillation parameters, B2 Sun, B3 Earth, B4 Interaction,
B5 Detector. Each benchmark fixes the inputs (grids, oscillation parameters, matter
model) in `<id>/spec.yaml`, so that contributions differ only by the tool.

| id | Compares | Status |
|---|---|---|
| B1_osc | Oscillation parameters: measurements and global fits in one format (reference/oscillation/parameter_sets.yaml); B2 and B3 run on them | draft 0.1.0 |
| B2_sun | The Sun: standard solar models (B16, BS05, B23: ten compositions; fluxes, electron density, production profiles in one format), and the mass-eigenstate fractions leaving the Sun, F_i(E, r0), for every model, averaged over each flux component's production profile | draft 0.2.0 |
| B3_earth | Earth crossing: P(nu_i -> nu_e) against energy and nadir angle; night averages per site | draft 0.3.0 |
| B4_xsec | Cross sections per channel (ES all flavours, nu_e CC on 40Ar, 16O, 13C, d); nuclear models of 40Ar as variants | draft 0.1.0 |
| B5_rates | Part 1: interaction rates per solar model, detector, channel and flux component (SNUfish folds every B4 model with B2 fluxes and oscillations); full-chain tool rates as contributions. Part 2: the published detector response of Super-K IV, SNO (salt), Borexino and DUNE: observed spectra and rates above threshold, contributions with the spec's response or their own | draft 0.4.0 |

B2 x B3 gives the day-night asymmetry (`snufish build` writes it as
B23_DayNight): P_ee(day) = sum_i F_i |U_ei|^2, P_ee(night) = sum_i F_i
<P_ie>_night, A_DN = 2 (N - D) / (N + D), per tool, solar model, Earth
model, site and flux component.
