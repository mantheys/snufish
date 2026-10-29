// Sources of every input the calculator uses: shown by each step's info button (rates.html)
// and listed on the home page (index.html). Identifiers are checked against the papers;
// a reference without a verified link is given as text.

export function link(ref) {
  // an arXiv id, DOI or Zenodo DOI (as written in the data files) -> URL, or null
  const arxiv = ref.match(/(?:arXiv:)?(\d{4}\.\d{4,5}|(?:hep-ph|astro-ph|nucl-th|hep-ex)\/\d{7})/);
  if (arxiv) return `https://arxiv.org/abs/${arxiv[1]}`;
  const doi = ref.match(/(10\.\d{4,9}\/[^\s,;)]+)/);
  if (doi) return `https://doi.org/${doi[1]}`;
  return null;
}

const S = (text, ref = null, url = null) => ({ text, ref, url: url || (ref ? link(ref) : null) });

export const SOURCES = {
  nufit: S("NuFIT 6.0 global fit (θ₁₃, θ₂₃, δ, Δm²₃₁ for every set)", "arXiv:2410.05380"),
  sk_solar: S("Super-Kamiokande solar analysis: day-night asymmetry, solar global fit, SNO NC ⁸B flux as applied", "arXiv:2312.12907"),
  juno: S("JUNO, first measurement of Δm²₂₁ and sin²θ₁₂", "arXiv:2511.14593"),
  kamland: S("KamLAND, Phys. Rev. D 88, 033001 (2013)", "10.1103/PhysRevD.88.033001"),
  b16: S("B16 standard solar models: Vinyoles et al. 2017", "arXiv:1611.09867"),
  bs05: S("BS05 standard solar models: Bahcall, Serenelli & Basu 2005", "astro-ph/0412440"),
  b23: S("B23 / SF-III standard solar models: Herrera & Serenelli, data release", "10.5281/zenodo.10174172"),
  b23_papers: S("with Magg et al., A&A 661, A140 (2022), and Solar Fusion III, Rev. Mod. Phys. 97, 035002 (2025)"),
  peanuts: S("PEANUTS (B16 and BS05 tables taken from its data directory)", "arXiv:2303.15527"),
  shape_pp_hep: S("pp and hep spectra: Bahcall, Phys. Rev. C 56, 3391 (1997)", "10.1103/PhysRevC.56.3391"),
  shape_b8: S("⁸B spectrum: Winter et al., Phys. Rev. C 73, 025503 (2006)", "10.1103/PhysRevC.73.025503"),
  shape_cno: S("¹³N, ¹⁵O, ¹⁷F spectra: Bahcall & Ulrich, Rev. Mod. Phys. 60, 297 (1988)", "10.1103/RevModPhys.60.297"),
  prem: S("PREM: Dziewonski & Anderson, Phys. Earth Planet. Inter. 25, 297 (1981)", "10.1016/0031-9201(81)90046-7"),
  nufast: S("NuFast-Earth (P(νᵢ → νₑ) through the Earth; the PREM variants)", "arXiv:2511.04735"),
  nufast_code: S("NuFast-Earth code", null, "https://github.com/PeterDenton/NuFast-Earth"),
  exposure: S("Night exposure per latitude: Lisi & Montanino 1997", "hep-ph/9702343"),
  surf: S("SURF latitude (DUNE far detector)", "arXiv:1707.02322"),
  borexino: S("Borexino Phase-II: pp, ⁷Be, pep rates, electron density, fiducial mass, exposure (table II, sec. II)", "arXiv:1707.09279"),
  sno: S("SNO combined analysis: D₂O, fiducial volume, thresholds, live times, energy scale", "arXiv:1109.0763"),
  dune_snb: S("DUNE supernova-burst paper: 40 kt LAr, 5 MeV detected-energy threshold, resolution ~20 % (MARLEY + LArSoft)", "arXiv:2008.06647"),
  dune_solar: S("Capozzi, Li, Zhu & Beacom, DUNE as the next-generation solar neutrino experiment: 7 % resolution, 5 MeV, 100 kt·yr", "arXiv:1808.08232"),
  sno_salt: S("SNO salt phase: φ_CC/φ_NC = 0.340 ± 0.023 (stat) −0.031 +0.029 (syst) above T_eff = 5.5 MeV, 391 live days", "nucl-ex/0502021"),
  nakamura: S("ν-deuteron CC and NC cross sections: Nakamura et al., Nucl. Phys. A 707, 561 (2002), table 1 (±1 %; SNOwGLoBES's xs_nue_d.dat is the same table from 5 MeV)", "nucl-th/0201062"),
  nc_capture: S("NC on deuterium: the neutron's capture γ (6.25 MeV on ²H, pure D₂O) is the visible energy, whatever the neutrino's; set the efficiency to the neutron capture × detection probability (SNO D₂O: 49 % of neutrons capture on ²H at the centre)", "nucl-ex/0502021"),
  hyperk: S("Hyper-K design report: fiducial volume, solar threshold, energy-scale and resolution uncertainties, site", "arXiv:1805.04163"),
  juno_b8: S("JUNO ⁸B study: LAB electron density, 2 MeV threshold, 3 %/√E, energy scale and efficiency uncertainties", "arXiv:2006.11760"),
  es_tree: S("ES at tree level in the Standard Model, sin²θ_W = 0.23857 (PDG 2024, MS-bar at Q² → 0)"),
  es_radiative: S("ES with electroweak, QCD and QED radiative corrections: Bahcall, Kamionkowski & Sirlin, PRD 51, 6146 (1995); sin²θ_W(m_Z) = 0.2317, ρ = 1.0126, κ(T)", "astro-ph/9502003"),
  snowglobes: S("SNOwGLoBES cross-section tables", null, "https://github.com/SNOwGLoBES/snowglobes"),
  marley: S("MARLEY (νₑ CC on ⁴⁰Ar), as tabulated by SNOwGLoBES in 2018 (zero below 5 MeV)", "arXiv:2101.11867"),
  bgt_pn: S("B(GT) from ⁴⁰Ar(p,n): Bhattacharya et al., Phys. Rev. C 80, 055501 (2009)", "10.1103/PhysRevC.80.055501"),
  bgt_ti: S("B(GT) from ⁴⁰Ti β decay (SNOwGLoBES does not say which of the two 1998 measurements)"),
  marley2: S("MARLEY 2.0.0 (31 July 2026): HF-CRPA for the continuum, measured B(GT) for bound levels", "10.5281/zenodo.21880925"),
  marley_prc: S("MARLEY's ⁴⁰Ar model: Gardiner, Phys. Rev. C 103, 044604 (2021)", "10.1103/PhysRevC.103.044604"),
  bgt_liu: S("B(GT) from ⁴⁰Ti β decay: Liu et al., Phys. Rev. C 58, 2677 (1998)", "10.1103/PhysRevC.58.2677"),
  bgt_b1998: S("B(GT) from ⁴⁰Ti β decay: Bhattacharya et al., Phys. Rev. C 58, 3677 (1998)", "10.1103/PhysRevC.58.3677"),
  marley_code: S("MARLEY code", null, "https://github.com/MARLEY-MC/marley"),
  klmv: S("KLMV: Kolbe, Langanke, Martínez-Pinedo & Vogel (νₑ CC on ⁴⁰Ar), as tabulated in SNOwGLoBES"),
  plotipus: S("plotipus (figures)", null, "https://github.com/mantheys/plotipus"),
  pyodide: S("Pyodide (Python in the browser, for plotipus figures)", null, "https://pyodide.org"),
  plotly: S("Plotly.js (interactive figures)", null, "https://plotly.com/javascript/"),
  hyparquet: S("hyparquet-writer (Parquet files)", null, "https://github.com/hyparam/hyparquet-writer"),
  fflate: S("fflate (zip files)", null, "https://github.com/101arrowz/fflate"),
};

export function render(sources) {
  // <li> list of sources (text, with a link where one is known)
  return `<ul class="sources">${sources.filter(Boolean).map((s) => {
    const ref = s.ref ? ` <span class="ref">${s.ref}</span>` : "";
    return s.url ? `<li><a href="${s.url}" target="_blank" rel="noopener">${s.text}</a>${ref}</li>` : `<li>${s.text}${ref}</li>`;
  }).join("")}</ul>`;
}

export function forStep(step, setup, quantity, inputs, setName, preset = "custom") {
  // the sources behind what is selected in one step of the calculator
  const d = inputs.data;
  if (step === 0) {
    const out = [S("Rates: interactions per kiloton-year; A_DN = 2(N − D)/(N + D) of the night and day rates")];
    if (quantity === "adn" && setup.channel === "es" && setup.site === "Kamioka") out.push(SOURCES.sk_solar);
    return out;
  }
  if (step === 1) {
    const set = d.parameter_sets.sets[setName];
    return [S(`${set.label}: ${set.source}`, null, link(set.source)), SOURCES.nufit];
  }
  if (step === 2) {
    const model = d.solar_models[setup.solar_model], out = [];
    if (model.family === "B16") out.push(SOURCES.b16, SOURCES.peanuts);
    if (model.family === "BS05") out.push(SOURCES.bs05, SOURCES.peanuts);
    if (model.family === "B23") out.push(SOURCES.b23, SOURCES.b23_papers);
    const c = setup.components;
    if (c.includes("pp") || c.includes("hep")) out.push(SOURCES.shape_pp_hep);
    if (c.includes("B8")) out.push(SOURCES.shape_b8);
    if (c.some((x) => ["N13", "O15", "F17"].includes(x))) out.push(SOURCES.shape_cno);
    if (c.includes("B8") && setup.b8_flux === "sno_nc") out.push(SOURCES.sk_solar);
    return out;
  }
  if (step === 3) {
    const site = d.sites[setup.site];
    return [S(`${setup.site}: latitude ${site.latitude_deg}° N (${site.source})`, null, link(site.source)),
            SOURCES.exposure, SOURCES.prem, SOURCES.nufast, SOURCES.nufast_code];
  }
  if (step === 4) {
    if (setup.channel === "es") return [...{ bks: [SOURCES.es_radiative], snowglobes: [SOURCES.snowglobes], tree: [SOURCES.es_tree] }[setup.es_model],
                                        S("Model range: BKS against SNOwGLoBES's tables; tree level is selectable but not in the range")];
    if (setup.channel === "cc_nue_d") return [SOURCES.nakamura];
    if (setup.channel === "nc_d") return [SOURCES.nakamura, SOURCES.nc_capture];
    const out = [SOURCES.snowglobes];
    const m = setup.xsec_model;
    if (m === "ar40_marley" || m === "ar40_marley1") out.push(SOURCES.marley, m === "ar40_marley" ? SOURCES.bgt_pn : SOURCES.bgt_ti);
    if (m.startsWith("ar40_marley2_") || m === "ar40_marley1_bhattacharya2009") {
      out.splice(0, out.length, SOURCES.marley2, SOURCES.marley_prc, SOURCES.marley, SOURCES.marley_code);
      out.push(m.endsWith("liu1998") ? SOURCES.bgt_liu : m.endsWith("bhattacharya1998") ? SOURCES.bgt_b1998 : SOURCES.bgt_pn);
      if ((d.xsec_levels?.[setup.channel] || {})[m]) out.push(S(`Measured B(GT) uncertainties of ${d.xsec_levels[setup.channel][m].length} levels, propagated (MARLEY's reaction file)`));
    }
    if (setup.channel === "cc_nue_ar40") out.push(S("Model range: the selectable models except the two zero below 5 MeV"));
    if (setup.xsec_model.includes("klmv")) out.push(SOURCES.klmv);
    return out;
  }
  const sk = "arXiv:2312.12907";
  const out = [];
  if (preset === "borexino" || setup.detector === "scintillator_pc") out.push(SOURCES.borexino);
  if (preset === "juno" || setup.detector === "scintillator_lab") out.push(SOURCES.juno_b8);
  if (preset === "sno" || setup.detector === "heavy_water") out.push(SOURCES.sno);
  if (preset === "sno_salt") out.push(SOURCES.sno_salt);
  if (preset === "hyperk") out.push(SOURCES.hyperk);
  if (preset === "dune") out.push(SOURCES.dune_snb, SOURCES.dune_solar);
  if (preset === "sk4" || setup.resolution_poly.length)
    out.push(S("Super-K IV energy resolution: eq. 9", sk));
  if (preset === "sk4")
    out.push(S("Super-K IV threshold 3.49 MeV and other rate systematics ±1.1 %: table IV", sk),
             S("Super-K IV energy scale ±0.48 %: table II; resolution ±3 %: sec. IV A 3", sk),
             S("Super-K IV 22.5 kt fiducial volume (fig. 28) and 2970 days live time (sec. V A 1)", sk));
  if (setup.smearing_table) out.push(S(`Imported smearing matrix: ${setup.smearing_table.name || "file"} (your own source)`));
  const curve = setup.efficiency_table?.curve && d.efficiency_curves?.[setup.efficiency_table.curve];
  if (curve) out.push(S(`Efficiency: ${curve.label}, ${curve.note}. Read from a figure: ${curve.method}`, curve.source.split(",")[0]));
  else if (setup.efficiency_table) out.push(S(`Imported efficiency curve: ${setup.efficiency_table.name || "file"} (your own source)`));
  return [...out, S("Generic detector response: Gaussian resolution σ = √((a√E)² + (bE)²), a logistic efficiency turn-on and a hard threshold, all in observed energy (ES: electron kinetic energy; CC: E_ν − Q). Statistics: Poisson, no backgrounds.")];
}

// The home page's credits, grouped
export const CREDITS = [
  ["Measurements and fits", [SOURCES.sk_solar, SOURCES.borexino, SOURCES.juno, SOURCES.kamland, SOURCES.nufit]],
  ["Solar models and spectra", [SOURCES.b16, SOURCES.bs05, SOURCES.b23, SOURCES.b23_papers, SOURCES.shape_pp_hep, SOURCES.shape_b8, SOURCES.shape_cno]],
  ["Earth", [SOURCES.prem, SOURCES.nufast, SOURCES.exposure, SOURCES.surf]],
  ["Detectors", [SOURCES.sk_solar, SOURCES.hyperk, SOURCES.dune_snb, SOURCES.dune_solar, SOURCES.sno, SOURCES.sno_salt, SOURCES.borexino, SOURCES.juno_b8]],
  ["Cross sections", [SOURCES.es_tree, SOURCES.es_radiative, SOURCES.nakamura, SOURCES.snowglobes, SOURCES.marley2, SOURCES.marley_prc, SOURCES.marley,
                      SOURCES.bgt_pn, SOURCES.bgt_liu, SOURCES.bgt_b1998, SOURCES.klmv]],
  ["Tools", [SOURCES.nufast_code, SOURCES.snowglobes, SOURCES.marley_code, SOURCES.peanuts, SOURCES.plotipus]],
  ["Software in this page", [SOURCES.plotly, SOURCES.pyodide, SOURCES.hyparquet, SOURCES.fflate]],
];
