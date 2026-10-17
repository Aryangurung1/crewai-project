"""Guardrails in plain code: cheap, predictable and testable.

1. check_question   runs BEFORE any LLM call and refuses off-limits questions.
2. evidence_guardrail runs on Parashar's draft: it must cite real, matched rule IDs.
3. safety_guardrail runs on the Guardian's final answer: no fear, no harm, no upsell.

Task guardrails return (False, feedback) to send the work back to the agent
with the reason, so the agent fixes it instead of the run failing.
"""

import re
from typing import Any, Tuple

from tools import SESSION

BLOCKED_QUESTIONS = [
    (r"\b(die|death|dying|lifespan|life span|how long will i live|longevity|ayu)\b",
     "lifespan or death"),
    (r"\b(disease|illness|cancer|sick|surgery|pregnan\w*|diagnos\w*|cure)\b",
     "health or medical matters"),
    (r"\b(court|lawsuit|legal case|verdict|jail|arrest\w*|bail)\b",
     "legal outcomes"),
    (r"\b(suicide|kill myself|self[- ]harm)\b",
     "self-harm"),
]

UNSAFE_ANSWER_PATTERNS = [
    (r"\b(will|going to)\b[^.]{0,40}\b(die|death|disease|illness|accident|divorce|cancer)\b",
     "predicts death, illness, accident or divorce"),
    (r"\b(curse\w*|doom\w*|cursed|black magic|evil eye)\b",
     "uses fear-mongering language"),
    (r"\b(buy|purchase|order)\b[^.]{0,50}\b(gemstone|gem|stone|yantra|rudraksha|puja|ritual)\b",
     "pushes a paid remedy"),
    (r"(₹|\$|\bRs\.?\s?\d|\bNPR\b|\bINR\b)",
     "mentions prices or money for remedies"),
    (r"\b(guaranteed|definitely will|100%|certainly will)\b",
     "states a prediction as certain"),
]

RULE_ID = re.compile(r"\bR-[A-Z]{3}-[A-Z0-9]{2,3}\b")
SELF_HARM_HELP = (
    "If you are having thoughts of harming yourself, please reach out to someone now. "
    "In Nepal you can call the TUTH suicide prevention helpline at 1166."
)


def check_question(question: str) -> tuple[bool, str]:
    q = question.lower()
    for pattern, topic in BLOCKED_QUESTIONS:
        if re.search(pattern, q):
            message = (
                f"I can't make predictions about {topic}. Jyotisha is a guide for "
                "reflection, not a substitute for a doctor, lawyer or counsellor. "
                "Ask me about career, relationships, studies, travel, finances or timing instead."
            )
            if topic == "self-harm":
                message = SELF_HARM_HELP
            return False, message
    return True, ""


def evidence_guardrail(output) -> Tuple[bool, Any]:
    cited = set(RULE_ID.findall(output.raw))
    if not cited:
        return False, (
            "Evidence Mode is required: cite at least one rule ID (e.g. R-CAR-01) from "
            "Shastra's findings next to the claim it supports."
        )
    invented = cited - SESSION["matched_rule_ids"]
    if invented:
        return False, (
            f"You cited rule IDs that Shastra did not match: {sorted(invented)}. "
            f"Use only these: {sorted(SESSION['matched_rule_ids'])}."
        )
    return True, output.raw


def safety_guardrail(output) -> Tuple[bool, Any]:
    text = output.raw
    for pattern, problem in UNSAFE_ANSWER_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return False, (
                f"The answer {problem} (found: '{match.group(0)}'). Rewrite that part "
                "in calm, non-fatalistic language. Keep every rule ID citation."
            )
    if not RULE_ID.search(text):
        return False, "The final answer lost its rule ID citations. Put them back."
    return True, text
