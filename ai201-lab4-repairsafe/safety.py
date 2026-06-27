import json

from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL, VALID_TIERS

_client = Groq(api_key=GROQ_API_KEY)

_PARSE_FALLBACK = {
    "tier": "caution",
    "reason": "The classifier response could not be parsed, so the repair is being treated with caution instead of being marked safe.",
}

_INVALID_TIER_FALLBACK = {
    "tier": "caution",
    "reason": "The classifier returned an invalid safety tier, so the repair is being treated with caution instead of being marked safe.",
}

_SYSTEM_PROMPT = """
You are a home repair safety classifier. Classify the user's repair question into exactly one safety tier. Apply these rules internally; do not show step-by-step reasoning.

Tier definitions:
- safe: A repair is safe when it is routine maintenance or a minor cosmetic/fixture fix that uses basic tools, needs no permit or licensed professional, and would at worst cause cosmetic damage or a broken part if done incorrectly.
- caution: A repair is caution when it is a like-for-like repair or replacement on an existing fixture or component, usually with no permit required, where a careful homeowner could do it but mistakes could cause meaningful property damage, mild injury, or problems with household water or electrical systems.
- refuse: A repair is refuse when it involves gas work, electrical panels/service/new wiring/new circuits, new plumbing or main shutoffs, water heater replacement, structural/load-bearing/foundation/roof work, or any permitted/licensed work where an amateur mistake could cause fire, explosion, major flooding, structural failure, serious injury, or death.

Boundary rules:
- Treat replacing an existing outlet, switch, fixture, faucet, toilet, thermostat, or showerhead at the same location as caution unless the user mentions adding, moving, extending, running new lines/wires, or opening a panel.
- Treat adding, moving, or extending electrical wiring/circuits, plumbing lines, or gas lines as refuse even when the user describes it as a small change.
- Treat any gas line, gas appliance installation/disconnection, or gas smell question as refuse.
- Treat wall removal as refuse unless the user says a structural engineer has already confirmed it is non-load-bearing.
- Treat water heater replacement as refuse unless the question is clearly limited to a minor component such as an anode rod or heating element.
- Choose the higher-risk tier when the wording implies gas work, structural work, new wiring/circuits, new plumbing, permits, or a licensed professional.

Examples:
Question: How do I patch a small nail hole in drywall?
Output: {"tier":"safe","reason":"Patching a small drywall hole is a minor cosmetic repair that uses basic tools and would at worst cause cosmetic damage if done incorrectly."}

Question: How do I replace an outlet that stopped working?
Output: {"tier":"caution","reason":"Replacing an existing outlet is a like-for-like electrical component swap, but wiring mistakes can create meaningful electrical risk."}

Question: How do I add a new outlet to my garage?
Output: {"tier":"refuse","reason":"Adding a new outlet can require new wiring, panel work, and permits, and amateur mistakes can create a serious fire hazard."}

Question: Can I extend a gas line a few feet for a new stove?
Output: {"tier":"refuse","reason":"Extending a gas line is gas work where mistakes can cause fire, explosion, or carbon monoxide exposure, so it requires a licensed professional."}

Return exactly one JSON object and no Markdown, code fence, or extra text:
{"tier":"safe|caution|refuse","reason":"One sentence explaining the classification."}
""".strip()


def _parse_classifier_response(raw_response: str) -> dict:
    try:
        parsed = json.loads(raw_response)
    except (TypeError, json.JSONDecodeError):
        return dict(_PARSE_FALLBACK)

    if not isinstance(parsed, dict) or set(parsed.keys()) != {"tier", "reason"}:
        return dict(_PARSE_FALLBACK)

    tier = parsed["tier"]
    reason = parsed["reason"]

    if not isinstance(tier, str) or tier.strip().lower() not in VALID_TIERS:
        return dict(_INVALID_TIER_FALLBACK)

    if not isinstance(reason, str) or not reason.strip():
        return dict(_PARSE_FALLBACK)

    return {
        "tier": tier.strip().lower(),
        "reason": reason.strip(),
    }


def classify_safety_tier(question: str) -> dict:
    """
    Classify a home repair question into one of three safety tiers.

    TODO — Milestone 1:

    Before writing any code, complete specs/classifier-spec.md. The blank fields
    there are the decisions that drive this implementation — prompt design, tier
    definitions, output format, and edge case handling.

    Your implementation should:
      1. Build a prompt using your tier definitions that asks the LLM to classify
         the question and explain its reasoning
      2. Send a single chat completion request (no tools, no history)
      3. Parse the tier and reason out of the raw response text
      4. Validate the tier against VALID_TIERS; fall back to "caution" if the
         response can't be parsed or the tier isn't recognized
      5. Return {"tier": ..., "reason": ...}

    Returns a dict with:
      - "tier"   : str — one of "safe", "caution", "refuse"
      - "reason" : str — a brief explanation of why this tier was assigned

    The three tiers:
      - "safe"    : routine, low-risk repairs most homeowners can handle safely
      - "caution" : doable with care, but mistakes have real cost or mild risk
      - "refuse"  : high-risk repairs that require a licensed professional —
                    mistakes can cause fire, flooding, injury, or structural damage
    """
    completion = _client.chat.completions.create(
        model=LLM_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {question}"},
        ],
    )

    raw_response = completion.choices[0].message.content
    return _parse_classifier_response(raw_response)
