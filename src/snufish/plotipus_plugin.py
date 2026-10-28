"""plotipus plugin: labels for SNUfish columns."""

QUANTITY_LABELS = {"P1e": r"$P_{1e}$", "P2e": r"$P_{2e}$", "P3e": r"$P_{3e}$"}


def _quantity_label(value, n_unique):
    return QUANTITY_LABELS.get(value)


def setup(registry):
    registry.add_label_hook("Quantity", _quantity_label)
