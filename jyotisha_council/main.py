"""Run a consultation with the Jyotisha Council.

    python main.py                       # interactive
    python main.py --name Sita --date 1998-04-12 --time 06:30 --place Kathmandu \
        --question "Should I take the Japan job offer?"
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from guardrails import check_question  # noqa: E402
from tools import SESSION, append_prediction, read_ledger, write_ledger  # noqa: E402

# Small built-in gazetteer: (latitude, longitude, timezone)
PLACES = {
    "kathmandu": (27.7172, 85.3240, "Asia/Kathmandu"),
    "lalitpur": (27.6588, 85.3247, "Asia/Kathmandu"),
    "bhaktapur": (27.6710, 85.4298, "Asia/Kathmandu"),
    "pokhara": (28.2096, 83.9856, "Asia/Kathmandu"),
    "biratnagar": (26.4525, 87.2718, "Asia/Kathmandu"),
    "bharatpur": (27.6833, 84.4333, "Asia/Kathmandu"),
    "butwal": (27.7006, 83.4483, "Asia/Kathmandu"),
    "dharan": (26.8065, 87.2846, "Asia/Kathmandu"),
    "janakpur": (26.7288, 85.9263, "Asia/Kathmandu"),
    "nepalgunj": (28.0500, 81.6167, "Asia/Kathmandu"),
    "delhi": (28.6139, 77.2090, "Asia/Kolkata"),
    "mumbai": (19.0760, 72.8777, "Asia/Kolkata"),
    "varanasi": (25.3176, 82.9739, "Asia/Kolkata"),
}

DISCLAIMER = (
    "Jyotisha is offered for reflection and guidance, not as certainty. "
    "Your choices shape your life. For health, legal or money decisions, "
    "please consult a qualified professional."
)


def ask(prompt: str, default: str | None = None) -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or (default or "")


def resolve_place(place: str) -> tuple[float, float, str]:
    if place.lower() in PLACES:
        return PLACES[place.lower()]
    print(f"'{place}' is not in the built-in list. Please enter coordinates.")
    return float(ask("Latitude")), float(ask("Longitude")), ask("Timezone", "Asia/Kathmandu")


def explain_llm_error(exc: Exception) -> str:
    """Turn provider errors into one actionable line instead of a traceback."""
    text = str(exc).lower()
    if "insufficient_quota" in text or "exceeded your current quota" in text and "openai" in text:
        return ("your OpenAI account has no API credit. Add credit at "
                "https://platform.openai.com/settings/organization/billing and try again.")
    if "credit balance is too low" in text:
        return ("your Anthropic account has no API credit. Add credit at "
                "https://console.anthropic.com/settings/billing and try again.")
    if "per day" in text or "perday" in text:
        return "the model's daily free quota is used up. Try tomorrow or switch LLM_MODEL in .env."
    if "429" in text or "rate limit" in text or "resource_exhausted" in text:
        return "rate limit hit. Wait a minute, or lower MAX_RPM in .env."
    if "401" in text or "authentication" in text or "api key" in text or "api_key" in text:
        return "the API key was rejected. Check the key in .env."
    if "404" in text or "not_found" in text or "no longer available" in text:
        return "the model in LLM_MODEL is not available. Pick another one in .env."
    return f"{type(exc).__name__}: {str(exc)[:300]}"


def review_past_predictions(name: str) -> None:
    """Prediction Ledger: ask 'did this happen?' about earlier answers."""
    entries = read_ledger()
    pending = [e for e in entries if e["name"].lower() == name.lower() and e["outcome"] is None]
    if not pending:
        return
    print(f"\nWelcome back, {name}. You have {len(pending)} earlier reading(s) without feedback.")
    for e in pending:
        print(f"\n  [{e['timestamp'][:10]}] You asked: {e['question']}")
        reply = ask("  Did things turn out as the reading suggested? (y / n / skip)", "skip").lower()
        if reply in ("y", "n"):
            e["outcome"] = "happened" if reply == "y" else "did_not_happen"
    write_ledger(entries)


def main() -> None:
    parser = argparse.ArgumentParser(description="Consult the Jyotisha Council")
    parser.add_argument("--name")
    parser.add_argument("--date", help="YYYY-MM-DD")
    parser.add_argument("--time", help="HH:MM, 24h local time")
    parser.add_argument("--place", help=f"One of: {', '.join(PLACES)}")
    parser.add_argument("--question")
    parser.add_argument("--language", help="English or Nepali")
    parser.add_argument("--quiet", action="store_true", help="Hide the agents' step-by-step log")
    args = parser.parse_args()

    provider = os.getenv("LLM_MODEL", "openai/").split("/")[0]
    needed = {"openai": ["OPENAI_API_KEY"], "anthropic": ["ANTHROPIC_API_KEY"],
              "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"]}
    if provider in needed and not any(os.getenv(k) for k in needed[provider]):
        sys.exit(f"Missing {needed[provider][0]}. Copy .env.example to .env and add your key.")

    print("=== Jyotisha Council ===")
    name = args.name or ask("Your name")
    review_past_predictions(name)
    date = args.date or ask("Birth date (YYYY-MM-DD)")
    time = args.time or ask("Birth time (HH:MM, 24h)")
    latitude, longitude, timezone = resolve_place(args.place or ask(f"Birth place ({', '.join(p.title() for p in PLACES)}, or any other)", "Kathmandu"))
    question = args.question or ask("Your question")
    language = args.language or ask("Answer language (English / Nepali)", "English")

    # Guardrail 1: refuse off-limits questions before spending a single LLM call.
    ok, message = check_question(question)
    if not ok:
        print(f"\n{message}")
        return

    from crew import JyotishaCouncil  # imported late so --help works without a key

    SESSION["chart"], SESSION["matched_rule_ids"] = None, set()
    try:
        result = JyotishaCouncil(verbose=not args.quiet).crew().kickoff(inputs={
            "name": name, "date": date, "time": time, "latitude": latitude,
            "longitude": longitude, "timezone": timezone, "question": question,
            "language": language,
        })
    except Exception as exc:
        sys.exit(f"\nThe council could not finish: {explain_llm_error(exc)}")

    answer = result.raw.strip()
    print("\n" + "=" * 60 + f"\n{answer}\n\n_{DISCLAIMER}_\n" + "=" * 60)

    append_prediction(name, question, answer, list(SESSION["matched_rule_ids"]))
    print("Saved to your Prediction Ledger. Next visit, I'll ask how it turned out.")


if __name__ == "__main__":
    main()
