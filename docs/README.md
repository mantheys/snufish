# SNUfish documentation

SNUfish fixes the inputs of each step of a solar neutrino calculation,
collects every tool's answer to it, checks the answers and plots them side
by side. On top of the validated solvers it computes rates, day-night
asymmetries and uncertainty budgets (command line and web page). The
[main README](../README.md) states the goals and use cases.

| Page | Read it to… |
|---|---|
| [architecture.md](architecture.md) | see how specs, contributions, the validator, the builder, the engine and the web page fit together |
| [benchmarks.md](benchmarks.md) | know exactly what each benchmark (B1–B5) fixes, asks for, checks and produces |
| [methods.md](methods.md) | follow the physics and numerics: MSW in the Sun, Earth crossing, night exposure, cross sections, rate folding, detector response, uncertainty budget, app tables |
| [sources.md](sources.md) | find where every number comes from: solar models, spectra, oscillation parameters, Earth models, sites, cross sections, detectors, measurements, tools |
| [usage.md](usage.md) | run the command line, call the engine from Python, make plots, use and deploy the calculator |
| [crosschecks.md](crosschecks.md) | see which published numbers SNUfish reproduces, which it does not, and its predictions for measurements |
| [status.md](status.md) | see what is missing, what is approximate and what is still open |
| [CONTRIBUTING.md](CONTRIBUTING.md) | contribute a tool's results |

Conventions used throughout:

- Energies in MeV; fluxes in cm⁻² s⁻¹ at the Earth; cross sections in cm²
  per target; rates in interactions per kiloton-year (Julian year,
  3.15576 × 10⁷ s) unless a unit is given.
- Day-night asymmetry A_DN = 2(N − D)/(N + D) (positive when the night rate
  is higher). Super-K and JUNO quote (D − N)/((D + N)/2) = −A_DN; numbers
  compared with them are given in their convention.
- Normal ordering, neutrinos only.
- Flux components: pp, pep, hep, Be7 (⁷Be), B8 (⁸B), N13, O15, F17.
- Nadir angle η: cos η = 0 at the horizon, 1 through the centre of the
  Earth (cos zenith = −cos η).
