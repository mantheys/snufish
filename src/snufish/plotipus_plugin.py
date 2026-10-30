"""plotipus plugin: legend labels for SNUfish columns (ids as they are written in
the data -> short display names)."""

QUANTITY_LABELS = {"P1e": r"$P_{1e}$", "P2e": r"$P_{2e}$", "P3e": r"$P_{3e}$"}

COMPONENT_LABELS = {"pp": "pp", "pep": "pep", "hep": "hep", "Be7": r"$^7$Be", "B8": r"$^8$B",
                    "N13": r"$^{13}$N", "O15": r"$^{15}$O", "F17": r"$^{17}$F", "all": "all"}

SOLAR_MODEL_LABELS = {"b16_gs98": "B16-GS98", "b16_agss09met": "B16-AGSS09met", "bs05_op": "BS05-OP",
                      "bs05_agsop": "BS05-AGSOP", "b23_gs98": "B23-GS98", "b23_agss09": "B23-AGSS09",
                      "b23_c11": "B23-C11", "b23_aag21": "B23-AAG21", "b23_mb22m": "B23-MB22m",
                      "b23_mb22p": "B23-MB22p", "exponential": "Exponential $n_e$"}

EARTH_MODEL_LABELS = {"prem_crust1": "PREM + local crust", "prem_full": "PREM", "prem_four": "PREM, 4 regions", "prem_prob3": "4 constant shells",
                      "native": "NuFast-Earth default"}

TOOL_LABELS = {"snufish-reference": "SNUfish reference", "nufast-earth": "NuFast-Earth", "snowglobes": "SNOwGLoBES",
               "marley": "MARLEY 2"}

# B4/B5 `Model` values are "<tool>: <variant>"
XSEC_LABELS = {
    "marley: default": "MARLEY 2",
    "marley: ar40_marley2_bhattacharya2009": "MARLEY 2",
    "marley: ar40_marley2_liu1998": "MARLEY 2, B(GT) Liu 98",
    "marley: ar40_marley2_bhattacharya1998": "MARLEY 2, B(GT) Bh. 98",
    "marley: ar40_marley1_bhattacharya2009": "MARLEY v1 model",
    "snowglobes: default": "SNOwGLoBES default",
    "snowglobes: ar40_klmv": "KLMV",
    "snowglobes: ar40_marley": "SNOwGLoBES MARLEY",
    "snowglobes: ar40_marley1": "SNOwGLoBES MARLEY1",
    "snufish-reference: default": "Tree level",
}


# One colour per flux component and per cross-section model in every figure (palette slots)
COMPONENT_COLORS = {"pp": "C0", "Be7": "C1", "B8": "C2", "O15": "C3", "hep": "C4", "pep": "C5", "N13": "C6",
                    "F17": "C7"}
XSEC_COLORS = {"marley: default": "C0", "marley: ar40_marley2_bhattacharya2009": "C0",
               "marley: ar40_marley2_liu1998": "C1", "snowglobes: ar40_klmv": "C2", "snowglobes: ar40_marley": "C3",
               "marley: ar40_marley1_bhattacharya2009": "C4", "marley: ar40_marley2_bhattacharya1998": "C5",
               "snowglobes: ar40_marley1": "C6", "snowglobes: default": "C7", "snufish-reference: default": "C8"}


def _quantity_label(value, n_unique):
    return QUANTITY_LABELS.get(value)


def _component_label(value, n_unique):
    return COMPONENT_LABELS.get(value)


def _model_label(value, n_unique):
    # `Model` is a solar model in B1 and a cross-section model in B4/B5
    return SOLAR_MODEL_LABELS.get(value) or XSEC_LABELS.get(value)


def _variant_label(value, n_unique):
    return SOLAR_MODEL_LABELS.get(value) or EARTH_MODEL_LABELS.get(value)


def _tool_label(value, n_unique):
    # `Label` is "<tool> <version>"
    tool = str(value).split(" ")[0]
    return TOOL_LABELS.get(tool)


def setup(registry):
    registry.add_label_hook("Quantity", _quantity_label)
    registry.add_label_hook("Component", _component_label)
    registry.add_label_hook("Model", _model_label)
    registry.add_label_hook("SolarModel", lambda value, n: SOLAR_MODEL_LABELS.get(value))
    registry.add_label_hook("SunVariant", lambda value, n: SOLAR_MODEL_LABELS.get(value))
    registry.add_label_hook("EarthVariant", lambda value, n: EARTH_MODEL_LABELS.get(value))
    registry.add_label_hook("Variant", _variant_label)
    registry.add_label_hook("Label", _tool_label)
    registry.add_color_hook("Component", COMPONENT_COLORS.get)
    registry.add_color_hook("Model", XSEC_COLORS.get)
