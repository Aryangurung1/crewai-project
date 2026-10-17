"""Shastra: deterministic rule engine. Matches chart facts against rules.json."""

import json
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "rules.json"
TOPICS = ["general", "career", "marriage", "wealth", "education", "travel"]


def load_rules() -> list[dict]:
    return json.loads(RULES_PATH.read_text())["rules"]


def _holds(cond: dict, chart: dict) -> bool:
    planets = chart["planets"]
    kind = cond["type"]
    if kind == "planet_in_house":
        return planets[cond["planet"]]["house"] in cond["houses"]
    if kind == "planet_dignity":
        return planets[cond["planet"]]["dignity"] in cond["dignity"]
    if kind == "house_lord_in_house":
        lord = chart["house_lords"][cond["house"]]
        return planets[lord]["house"] in cond["houses"]
    if kind == "planet_from_planet":
        offset = (planets[cond["planet"]]["house"] - planets[cond["from"]]["house"]) % 12 + 1
        return offset in cond["houses"]
    if kind == "mahadasha":
        return chart["dasha"]["mahadasha"] == cond["lord"]
    raise ValueError(f"Unknown condition type: {kind}")


def match_rules(chart: dict, topic: str) -> list[dict]:
    """Return every rule for `topic` whose conditions all hold, with its evidence."""
    topic = topic if topic in TOPICS else "general"
    matched = []
    for rule in load_rules():
        if topic in rule["topics"] and all(_holds(c, chart) for c in rule["conditions"]):
            matched.append({
                "rule_id": rule["id"],
                "name": rule["name"],
                "reading": rule["reading"],
                "evidence": [_describe(c, chart) for c in rule["conditions"]],
            })
    return matched


def _describe(cond: dict, chart: dict) -> str:
    """Human-readable 'why' for Evidence Mode."""
    p = chart["planets"]
    kind = cond["type"]
    if kind == "planet_in_house":
        name = cond["planet"]
        return f"{name} in house {p[name]['house']} ({p[name]['sign']})"
    if kind == "planet_dignity":
        name = cond["planet"]
        return f"{name} is {p[name]['dignity']} in {p[name]['sign']}"
    if kind == "house_lord_in_house":
        lord = chart["house_lords"][cond["house"]]
        return f"Lord of house {cond['house']} is {lord}, placed in house {p[lord]['house']}"
    if kind == "planet_from_planet":
        offset = (p[cond["planet"]]["house"] - p[cond["from"]]["house"]) % 12 + 1
        return f"{cond['planet']} is in house {offset} counted from {cond['from']}"
    if kind == "mahadasha":
        return f"Running {chart['dasha']['mahadasha']} mahadasha until {chart['dasha']['mahadasha_until']}"
    return kind
