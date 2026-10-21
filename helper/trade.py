"""Estimated trade advice for the system selected on the chart."""

ECONOMIES = (
    "Rich industrial",
    "Average industrial",
    "Poor industrial",
    "Mainly industrial",
    "Mainly agricultural",
    "Rich agricultural",
    "Average agricultural",
    "Poor agricultural",
)
GOVERNMENTS = (
    "Anarchy",
    "Feudal",
    "Multi-Government",
    "Dictatorship",
    "Communist",
    "Confederacy",
    "Democracy",
    "Corporate State",
)


def chart_advice(state):
    """Summarize chart-system data and estimated opportunities from current prices."""
    selected = state.chart_system
    if not isinstance(selected, dict):
        return ""

    economy = selected.get("economy")
    economy_name = (
        ECONOMIES[economy]
        if isinstance(economy, int) and 0 <= economy < len(ECONOMIES)
        else f"Economy {economy}"
    )
    government = selected.get("government")
    government_name = (
        GOVERNMENTS[government]
        if isinstance(government, int) and 0 <= government < len(GOVERNMENTS)
        else f"Government {government}"
    )
    tech = selected.get("techLevel")
    # techlevel is 0-based; the game shows it plus one (PlayerEntity.m, system data screen)
    tech_text = tech + 1 if isinstance(tech, int) else "?"
    current = selected.get("id") is not None and selected.get("id") == state.current_system
    where = "current system" if current else f"{selected.get('distance') or 0:.1f} ly"
    lines = [
        f"{selected.get('name', 'Selected system')} — {where}",
        f"{economy_name} · {government_name} · Tech level {tech_text}",
    ]

    if not current:
        lines += _trade_lines(state, selected.get("samplePrices") or {})
    lines += _nearest_lines(state)
    return "\n".join(lines)


def _trade_lines(state, estimates):
    market = state.origin_market or {}

    def local_price(commodity):
        entry = market.get(commodity)
        return entry.get("price") if isinstance(entry, dict) else None

    held = []
    for cargo in state.manifest or []:
        commodity = cargo.get("name")
        destination_price = estimates.get(commodity)
        if destination_price is None:
            continue
        origin_price = local_price(commodity)
        margin = destination_price - origin_price if origin_price is not None else None
        if margin is not None and margin <= 0:
            continue
        quantity = cargo.get("quantity", 0)
        # Best total profit first; cargo with no local price to compare goes last.
        rank = (margin is not None, (margin or destination_price) * quantity)
        held.append((rank, cargo, destination_price, margin))
    held.sort(key=lambda item: item[0], reverse=True)
    lines = [
        "Sell from hold: "
        + (
            ", ".join(_cargo_estimate(cargo, price, margin) for _, cargo, price, margin in held[:3])
            if held
            else "no higher estimated prices"
        )
    ]

    buys = []
    for commodity, destination_price in estimates.items():
        entry = market.get(commodity)
        if not isinstance(entry, dict) or not entry.get("quantity"):
            continue  # out of stock here
        origin_price = entry.get("price")
        if origin_price is not None and destination_price > origin_price:
            illegal = is_illegal(entry)
            buys.append((destination_price - origin_price, commodity, illegal))
    buys.sort(reverse=True)
    lines.append(
        "Buy here: "
        + (
            ", ".join(
                f"{commodity.replace('_', ' ').title()} (+{_credits(margin)} cr/unit"
                f"{', illegal' if illegal else ''})"
                for margin, commodity, illegal in buys[:3]
            )
            if buys
            else "no higher estimated prices"
        )
    )
    return lines


def _nearest_lines(state):
    reachable = [
        system
        for system in state.systems
        if state.fuel is not None and system.get("distance", state.fuel + 1) <= state.fuel
    ]
    lines = []
    for label, predicate in (
        ("Agricultural", lambda value: isinstance(value, int) and 4 <= value <= 7),
        ("Industrial", lambda value: isinstance(value, int) and 0 <= value <= 3),
    ):
        candidates = [system for system in reachable if predicate(system.get("economy"))]
        candidates.sort(
            key=lambda system: (system.get("distance", float("inf")), system.get("name", ""))
        )
        nearest = candidates[0] if candidates else None
        if nearest:
            world = f"{nearest.get('name', 'Unknown')} ({nearest.get('distance', 0):.1f} ly)"
        else:
            world = "none in range"
        lines.append(f"Nearest {label.lower()}: {world}")
    return lines


def is_illegal(entry):
    """Whether a market entry is illegal to trade here.

    The game reports legality_export/legality_import as strings ("0", "1"),
    so "0" must count as legal.
    """
    for key in ("legality_export", "legality_import"):
        try:
            if float(entry.get(key) or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _cargo_estimate(cargo, destination_price, margin):
    label = cargo.get("displayName", cargo.get("name", "Cargo"))
    quantity = cargo.get("quantity", 0)
    estimate = f"{label} ×{quantity} ({_credits(destination_price)} cr/unit"
    if margin is not None:
        estimate += f", +{_credits(margin)} vs here"
    return estimate + ")"


def _credits(decicredits):
    return f"{decicredits / 10:.1f}"
