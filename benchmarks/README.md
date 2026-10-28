# Benchmarks

Each benchmark fixes the inputs (grids, oscillation parameters, matter
model) in `<id>/spec.yaml`, so that contributions differ only by the tool.

| id | Compares | Status |
|---|---|---|
| B1_flux | Solar flux spectra and normalisations per solar model | planned |
| B2_sun | Survival probability from MSW in the Sun (nu_i fractions at Earth) | planned |
| B3_earth | Earth crossing: P(nu_i -> nu_e) against energy and nadir angle | draft 0.1.0 |
| B4_xsec | Cross sections: nu-e ES (radiative corrections), CC on Ar-40, d, C-13 | planned |
| B5_rates | Observed spectra and rates per detector (SNOwGLoBES chain) | planned |
| D | Detector response library: smearing, efficiency, thresholds | planned |

B2 x B3 gives the day-night asymmetry: P_ee(night) = sum_i f_i P_ie, with
f_i the nu_i fractions arriving from the Sun.
