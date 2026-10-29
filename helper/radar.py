"""The radar (#100): what's on the scanner, coloured as the scanner colours it.

The add-on sends a "radar" message every second in flight. Each blip has its
scan class, whether it's hostile to the player, and any scanner colours a
script set. The colours here follow ShipEntity scannerDisplayColorForShip
(1.92.1). The scanner swaps between two colours every 0.25 s for some blips,
so a blip has a colour and, when it flashes, a second one shown in the flash
phase.
"""

GREY = (0.9, 0.9, 0.9)  # cargo_color
RED = (1.0, 0.25, 0.0)  # hostile_color: red-orange
YELLOW = (1.0, 1.0, 0.0)  # neutral_color
GREEN = (0.0, 1.0, 0.0)  # friendly_color
CYAN = (0.0, 1.0, 1.0)  # missile_color
POLICE = (0.5, 0.0, 1.0)  # police_color1: purple-blue
POLICE_HOSTILE = (1.0, 0.0, 0.5)  # police_color2: purple-red
MASCEM_FLASH = (0.3, 0.3, 0.3)  # mascem_color1: dark grey
MASCEM = (0.4, 0.1, 0.4)  # mascem_color2: purple

KINDS = {
    "CLASS_NEUTRAL": "ship",
    "CLASS_POLICE": "police",
    "CLASS_MILITARY": "military",
    "CLASS_THARGOID": "thargoid",
    "CLASS_MISSILE": "missile",
    "CLASS_STATION": "station",
    "CLASS_BUOY": "buoy",
    "CLASS_ROCK": "rock",
    "CLASS_CARGO": "cargo",
    "CLASS_MINE": "mine",
}


def _pair(first, second):
    """Two scripted colours ([r, g, b, a] or None): (colour, flash). With both
    set the scanner shows the first in the flash phase, the second otherwise."""
    if first and second:
        return tuple(second[:3]), tuple(first[:3])
    return tuple((first or second)[:3]), None


def colours(blip, has_filter=False):
    """(colour, flash colour or None) for a blip, as (r, g, b) from 0 to 1;
    None when the scanner draws it clear (a jamming ship, without a filter)."""
    hostile = bool(blip.get("hostile"))
    scripted = blip.get("colours") or (None, None, None, None)
    if hostile and (scripted[2] or scripted[3]):
        return _pair(scripted[2], scripted[3])
    if scripted[0] or scripted[1]:
        return _pair(scripted[0], scripted[1])
    if blip.get("jamming"):
        if not has_filter:
            return None
        return (RED if hostile else MASCEM), MASCEM_FLASH
    scan_class = blip.get("scanClass")
    if scan_class in ("CLASS_ROCK", "CLASS_CARGO"):
        return GREY, None
    if scan_class == "CLASS_THARGOID":
        return GREEN, RED
    if scan_class == "CLASS_MISSILE":
        return CYAN, None
    if scan_class == "CLASS_STATION":
        return GREEN, None
    if scan_class == "CLASS_BUOY":
        return YELLOW, GREEN
    if scan_class in ("CLASS_POLICE", "CLASS_MILITARY"):
        return POLICE, (POLICE_HOSTILE if hostile else None)
    if scan_class == "CLASS_MINE":
        return RED, YELLOW
    return (RED if hostile else YELLOW), None


def css(colour):
    """(r, g, b) from 0 to 1 as "#rrggbb"; None stays None."""
    if colour is None:
        return None
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in colour)


def doing(blip):
    """What a blip is doing, for people: "attacking you", "attacking Python",
    "fleeing", both joined, or None."""
    parts = []
    if blip.get("attacking") and blip.get("target"):
        parts.append(f"attacking {blip['target']}")
    if blip.get("fleeing"):
        parts.append("fleeing")
    return ", ".join(parts) or None


def blips(message):
    """The radar topic's rows from the last radar message (or None), nearest
    first, leaving out what the scanner draws clear."""
    if not message:
        return ()
    has_filter = bool(message.get("filter"))
    rows = []
    for blip in message.get("blips") or ():
        if not isinstance(blip, dict):
            continue
        shown = colours(blip, has_filter)
        if shown is None:
            continue
        distance = blip.get("distance")
        km = round(distance / 1000, 1) if isinstance(distance, int | float) else None
        rows.append(
            {
                "name": blip.get("name") or "Unknown",
                "kind": KINDS.get(blip.get("scanClass"), "ship"),
                "role": blip.get("role"),
                "distance_km": km,
                "bounty": blip.get("bounty") or 0,
                "doing": doing(blip),
                "hostile": bool(blip.get("hostile")),
                "colour": css(shown[0]),
                "flash": css(shown[1]),
            }
        )
    rows.sort(key=lambda row: (row["distance_km"] is None, row["distance_km"] or 0))
    return tuple(rows)
