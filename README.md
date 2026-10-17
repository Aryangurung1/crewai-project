# Jyotisha Council: a 5-agent CrewAI app

A small working version of the AI Jyotisha concept. A **council of specialist agents** answers a
question about a birth chart. The maths and the rules are deterministic code, and the LLM only
explains them. Every claim cites a rule ID, and a Guardian agent reviews the answer before the
user sees it.

Built with **CrewAI 1.15** and **OpenAI** (`gpt-5-mini`). Any CrewAI-supported model works by changing one line in `.env`.

## Quick start

```bash
cd crewai-project
source .venv/bin/activate        # once per terminal; your prompt shows (.venv)
cd jyotisha_council
python crew.py
```

It asks you for:

1. Your name
2. Birth date (`YYYY-MM-DD`)
3. Birth time (`HH:MM`, 24-hour)
4. Birth place (built-in Nepal/India cities listed, default Kathmandu; any other place asks for latitude, longitude and timezone)
5. Your question
6. Answer language (English / Nepali, default English)

Then the five agents run one after another and print the final answer.

### Example output

> Taking the Japan offer aligns well with a broader phase of foreign growth and professional
> expansion... balance your enthusiasm with careful due diligence.
>
> **Why (Evidence Mode):**
> * Your running Jupiter Mahadasha marks an expansive phase centered on learning, mentors, and personal growth [R-DAS-JUP].
> * The 9th lord placed in the 11th house connects long-distance movement and fortune with rewarding gains [R-GEN-03].
> * Having the 1st lord in the 1st house grants you a resilient sense of self [R-GEN-02].
>
> **Timing:** Jupiter Mahadasha supports expansion through March 2036...
> **Confidence:** Moderate...
> **Practical Suggestion:** write down your non-negotiable personal values alongside the job offer's daily realities...

## How it works

```
 user question ──► [Input guardrail] ── blocked? → kind refusal, no LLM call
                         │
                         ▼
  ┌─────────┐  chart  ┌─────────┐  rules + IDs  ┌──────────┐  draft  ┌──────────┐
  │ Ganita  │───────► │ Shastra │─────────────► │ Parashar │───────► │ Guardian │──► answer
  │ (calc)  │         │ (rules) │       ┌─────► │ (writer) │         │ (ethics) │      │
  └────┬────┘         └────┬────┘       │       └────┬─────┘         └────┬─────┘      ▼
       │                   │      ┌─────┴────┐       │                    │     Prediction
  chart_calculator    rule_lookup │  Smriti  │  evidence_guardrail   safety_guardrail  Ledger
  (Swiss Ephemeris)   (rules.json)│ (memory) │  (must cite real IDs) (no fear/harm/upsell)
                                  └────┬─────┘
                                  ledger_recall
```

| Agent | Job | Tool |
|---|---|---|
| **Ganita** | Sidereal chart, nakshatra, Vimshottari dasha | `chart_calculator` (Swiss Ephemeris) |
| **Shastra** | Matches chart facts against classical rules, for up to 2 topics the question touches (e.g. a job abroad is career + travel) | `rule_lookup` (`data/rules.json`) |
| **Smriti** | Recalls past questions and outcomes | `ledger_recall` (`data/ledger.json`) |
| **Parashar** | Writes the answer in Evidence Mode | none |
| **Guardian** | Removes anything unsafe, keeps citations | none |

### Soft handoffs
Agents don't call each other directly. Each task ends with a `HANDOFF to <agent>:` note, and
CrewAI's `context=[...]` passes those outputs on. Parashar reads Ganita, Shastra and Smriti;
Guardian reads Parashar. When a guardrail rejects a draft, the agent gets the **reason** and
rewrites it (up to 2 retries) instead of the run crashing.

### Guardrails (three layers, all plain code)
1. **Input guardrail:** questions about death, health, legal cases or self-harm are refused before any LLM call.
2. **Evidence guardrail:** Parashar's draft must cite rule IDs, and only IDs that Shastra actually matched, so made-up evidence is rejected.
3. **Safety guardrail:** the final answer can't contain fatalistic predictions, fear language, "guaranteed", prices or paid remedies.

### Why it's built this way
- **The LLM explains and never calculates.** Planet positions come from Swiss Ephemeris and rule matches from a rules file. The LLM can't invent a placement.
- **The chart is shared in session state**, so Shastra only picks a *topic*. It can't pass a garbled chart to the rule engine.
- **The Prediction Ledger** saves every answer. On your next visit under the same name it asks "Did things turn out as the reading suggested?", which is the start of measuring accuracy.

## Demo ideas

| Try | What it shows |
|---|---|
| `python crew.py`, ask about a job abroad | All 5 agents, tools, handoffs and both task guardrails |
| Run again with the **same name** | Prediction Ledger asks for feedback on the earlier reading; Smriti mentions the history |
| Ask `When will I die?` | Input guardrail refuses instantly, with no LLM call |
| Choose `Nepali` as the language | Same evidence, answer in Nepali (rule IDs stay in English) |

## Setup (first time only)

Needs **Python 3.10–3.13**. CrewAI does not support 3.14 yet.

```bash
cd crewai-project
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # then paste your key into .env
```

Get an OpenAI API key at https://platform.openai.com/api-keys and add credit under
**Settings → Billing** (a ChatGPT Plus subscription does not include API credit).
A consultation costs a few cents.

## Configuration

All settings live in `.env` (never commit it; it is in `.gitignore`):

```bash
OPENAI_API_KEY=your-key-here
LLM_MODEL=openai/gpt-5-mini               # swap provider with one line
# LLM_MODEL=openai/gpt-5                  # stronger, pricier
# LLM_MODEL=anthropic/claude-sonnet-5-5   # needs ANTHROPIC_API_KEY
# LLM_MODEL=gemini/gemini-3.8-flash       # needs GEMINI_API_KEY
# LLM_MODEL=ollama/qwen2.5:7b             # local, free
MAX_RPM=30                                # requests per minute cap
```

If you switch to the **Gemini free tier**, set `MAX_RPM=4`: it allows only 5 requests per minute
and 20 per day for `gemini-3.8-flash`, which is about one or two consultations a day.

## Other ways to run

```bash
# Everything on one line, no prompts
python main.py --name Sita --date 1998-04-12 --time 06:30 --place Kathmandu \
    --question "Should I take the Japan job offer?" --language English

python main.py --quiet ...      # hide the agents' step-by-step log, show only the answer
pytest                          # tests for the deterministic layer, no API key needed
```

## Troubleshooting

| Error | Fix |
|---|---|
| `command not found: python` or `No module named crewai` | Run `source .venv/bin/activate` from the `crewai-project` folder first |
| `Missing OPENAI_API_KEY` | Create `.env` from `.env.example` and paste your key |
| `no API credit` | Add credit at https://platform.openai.com/settings/organization/billing (can take a few minutes to apply) |
| `404 ... model is no longer available` | Google retired that model; set a current one in `LLM_MODEL` (the error message names it) |
| `rate limit hit` | Wait about a minute, or lower `MAX_RPM` |
| `daily free quota is used up` (Gemini) | Wait for the reset or switch `LLM_MODEL` |

## Files
```
crewai-project/
  .env / .env.example   API key, model, rate limit
  requirements.txt
  jyotisha_council/
    crew.py             5 agents, 5 tasks, handoff wiring; `python crew.py` starts a consultation
    main.py             prompts and flags, input guardrail, Prediction Ledger follow-up
    config/agents.yaml  roles, goals, instructions
    config/tasks.yaml   task instructions and handoff notes
    tools.py            3 CrewAI tools around deterministic code
    guardrails.py       input, evidence and safety guardrails
    astro/ganita.py     Swiss Ephemeris chart + Vimshottari dasha
    astro/shastra.py    rule engine
    data/rules.json     starter rule library (to be reviewed by an astrologer)
    data/ledger.json    Prediction Ledger (created on first run)
    tests/              unit tests
```

## Limits (on purpose, to keep it basic)
- 29 starter rules, whole-sign houses, D1 chart only, no divisional charts or transits.
- Rule readings are illustrative and need review by an astrologer before real use.
- CLI only, and a small built-in city list (other places take coordinates).
