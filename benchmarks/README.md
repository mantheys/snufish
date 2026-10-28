# Benchmarks

Each benchmark fixes the inputs (grids, oscillation parameters, matter
model) in `<id>/spec.yaml`, so that contributions differ only by the tool.

| id | Compares | Status |
|---|---|---|
| B1_flux | Solar flux spectra and normalisations per solar model | planned |
| B2_sun | Mass-eigenstate fractions leaving the Sun, F_i(E, r0), on the B16-GS98 density; averaged over each flux component's production profile | draft 0.1.0 |
| B3_earth | Earth crossing: P(nu_i -> nu_e) against energy and nadir angle; night averages per site | draft 0.3.0 |
| B4_xsec | Cross sections per channel (ES all flavours, nu_e CC on 40Ar, 16O, 13C, d); nuclear models of 40Ar as variants | draft 0.1.0 |
| B5_rates | Interaction rates per detector, channel and flux component (SNUfish folds every B4 model with B16 fluxes and B2 oscillations); full-chain tool rates as contributions | draft 0.1.0 |
| D | Detector response library: smearing, efficiency, thresholds | planned |

B2 x B3 gives the day-night asymmetry (`snufish build` writes it as
B23_DayNight): P_ee(day) = sum_i F_i |U_ei|^2, P_ee(night) = sum_i F_i
<P_ie>_night, A_DN = 2 (N - D) / (N + D), per tool, solar model, Earth
model, site and flux component.
