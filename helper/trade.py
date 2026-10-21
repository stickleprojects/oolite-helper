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


def chart_advice(state):
    """Summarize chart-system data and estimated opportunities from current prices."""
    selected = state.chart_system
    if not isinstance(selected, dict):
        return ""

    economy = selected.get("economy")
    economy_name = (ECONOMIES[economy] if isinstance(economy, int)
                    and 0 <= economy < len(ECONOMIES) else f"Economy {economy}")
    lines = [
        f"{selected.get('name', 'Selected system')} — "
        f"{selected.get('distance', 0):.1f} ly",
        f"{economy_name} · Government {selected.get('government', '?')} · "
        f"Tech level {selected.get('techLevel', '?')}",
    ]

    estimates = selected.get("samplePrices") or {}
    origin_prices = state.origin_prices or {}
    held = []
    for cargo in state.manifest or []:
        commodity = cargo.get("name")
        destination_price = estimates.get(commodity)
        origin_price = origin_prices.get(commodity)
        if destination_price is None:
            continue
        margin = (destination_price - origin_price) if origin_price is not None else None
        if margin is not None and margin <= 0:
            continue
        held.append((destination_price, cargo, margin))
    held.sort(key=lambda item: item[0], reverse=True)
    lines.append("Sell from hold: " + (
        ", ".join(_cargo_estimate(cargo, price, margin)
                  for price, cargo, margin in held[:3])
        if held else "no higher estimated prices"
    ))

    buys = []
    for commodity, destination_price in estimates.items():
        origin_price = origin_prices.get(commodity)
        if origin_price is not None and destination_price > origin_price:
            buys.append((destination_price - origin_price, commodity))
    buys.sort(reverse=True)
    lines.append("Buy here: " + (
        ", ".join(
            f"{commodity.replace('_', ' ').title()} (+{_credits(margin)} cr/unit)"
            for margin, commodity in buys[:3]
        ) if buys else "no higher estimated prices"
    ))

    reachable = [
        system for system in state.systems
        if state.fuel is not None and system.get("distance", state.fuel + 1) <= state.fuel
    ]
    for label, predicate in (
        ("Agricultural", lambda value: isinstance(value, int) and 4 <= value <= 7),
        ("Industrial", lambda value: isinstance(value, int) and 0 <= value <= 3),
    ):
        candidates = [system for system in reachable if predicate(system.get("economy"))]
        candidates.sort(key=lambda system: (system.get("distance", float("inf")),
                                            system.get("name", "")))
        nearest = candidates[0] if candidates else None
        if nearest:
            world = f"{nearest.get('name', 'Unknown')} ({nearest.get('distance', 0):.1f} ly)"
        else:
            world = "none in range"
        lines.append(f"Nearest {label.lower()}: {world}")

    return "\n".join(lines)


def _cargo_estimate(cargo, destination_price, margin):
    label = cargo.get("displayName", cargo.get("name", "Cargo"))
    quantity = cargo.get("quantity", 0)
    estimate = f"{label} ×{quantity} ({_credits(destination_price)} cr/unit"
    if margin is not None:
        estimate += f", +{_credits(margin)} vs here"
    return estimate + ")"


def _credits(decicredits):
    return f"{decicredits / 10:.1f}"
