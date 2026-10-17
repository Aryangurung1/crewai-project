"""CrewAI tools. Each one wraps deterministic code so the LLM never invents data.

The chart is computed once by Ganita and kept in SESSION, so Shastra only has
to pick a topic: it cannot pass a garbled chart to the rule engine.
"""

import json
from datetime import datetime
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from astro.ganita import compute_chart
from astro.shastra import TOPICS, match_rules

LEDGER_PATH = Path(__file__).resolve().parent / "data" / "ledger.json"

# Shared state for one consultation. main.py resets it before each run.
SESSION: dict = {"chart": None, "matched_rule_ids": set()}


# --- Ganita -----------------------------------------------------------------

class ChartInput(BaseModel):
    date: str = Field(..., description="Birth date as YYYY-MM-DD")
    time: str = Field(..., description="Local birth time as HH:MM (24h)")
    latitude: float = Field(..., description="Birth place latitude")
    longitude: float = Field(..., description="Birth place longitude")
    timezone: str = Field(..., description="IANA timezone, e.g. Asia/Kathmandu")


class ChartCalculatorTool(BaseTool):
    name: str = "chart_calculator"
    description: str = (
        "Computes the sidereal (Lahiri) birth chart with Swiss Ephemeris: lagna, "
        "planet signs/houses/dignities, Moon nakshatra and running Vimshottari dasha."
    )
    args_schema: type[BaseModel] = ChartInput

    def _run(self, date: str, time: str, latitude: float, longitude: float, timezone: str) -> str:
        try:
            chart = compute_chart(date, time, latitude, longitude, timezone)
        except Exception as exc:  # bad date/time/timezone: tell the agent, don't crash
            return f"ERROR: could not compute chart ({exc}). Check the input format."
        SESSION["chart"] = chart
        return json.dumps(chart, indent=1)


# --- Shastra ----------------------------------------------------------------

class RuleInput(BaseModel):
    topic: str = Field(..., description=f"One of: {', '.join(TOPICS)}")


class RuleLookupTool(BaseTool):
    name: str = "rule_lookup"
    description: str = (
        "Matches the computed chart against the classical rule library for one topic. "
        "Returns rule IDs, readings and the chart evidence for each match."
    )
    args_schema: type[BaseModel] = RuleInput

    def _run(self, topic: str) -> str:
        chart = SESSION["chart"]
        if chart is None:
            return "ERROR: no chart computed yet. The chart must be calculated first."
        topic = topic.strip().lower()
        matches = match_rules(chart, topic)
        SESSION["matched_rule_ids"].update(m["rule_id"] for m in matches)
        strength = "strong" if len(matches) >= 3 else "moderate" if len(matches) == 2 else "limited"
        return json.dumps({"topic": topic, "evidence_strength": strength, "matches": matches}, indent=1)


# --- Smriti -----------------------------------------------------------------

def read_ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    return json.loads(LEDGER_PATH.read_text())


def write_ledger(entries: list[dict]) -> None:
    LEDGER_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False))


def append_prediction(name: str, question: str, answer: str, rule_ids: list[str]) -> None:
    """Called by code after the Guardian approves, never by an agent."""
    entries = read_ledger()
    entries.append({
        "id": len(entries) + 1,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "name": name,
        "question": question,
        "answer": answer,
        "rule_ids": sorted(rule_ids),
        "outcome": None,  # filled in later: "happened" / "did_not_happen"
    })
    write_ledger(entries)


class MemoryInput(BaseModel):
    name: str = Field(..., description="The person's name exactly as given")


class LedgerRecallTool(BaseTool):
    name: str = "ledger_recall"
    description: str = (
        "Returns this person's past questions, past answers and recorded outcomes "
        "from the Prediction Ledger."
    )
    args_schema: type[BaseModel] = MemoryInput

    def _run(self, name: str) -> str:
        mine = [e for e in read_ledger() if e["name"].lower() == name.strip().lower()]
        if not mine:
            return "No past consultations for this person. This is their first visit."
        return json.dumps(mine[-5:], indent=1, ensure_ascii=False)
