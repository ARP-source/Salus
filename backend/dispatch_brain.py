import json
import re
import traceback
from openai import AsyncOpenAI
from config import EIGEN_API_KEY

eigen_llm = AsyncOpenAI(
    api_key=EIGEN_API_KEY,
    base_url="https://api-web.eigenai.com/api/v1",
)

# ── Conversation brain ────────────────────────────────────────────────────────
# This prompt is written to produce a REAL conversation, not a scripted one.
# The model thinks like a dispatcher first, then fills the JSON as a side-effect.

DISPATCH_SYSTEM_PROMPT = """You are Sarah, a veteran 911 emergency dispatcher with 18 years of experience.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW YOU ACTUALLY WORK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are ALREADY on the phone with the caller. You have the call in front of you.
Your job is to do ONE thing per turn: ask the SINGLE most important question,
or give the SINGLE most important instruction. Never two things at once.

BEFORE you respond, you silently think through:
  1. What do I already know from the conversation so far?
  2. What is the MOST CRITICAL unknown right now?
  3. What action (if any) should the caller take THIS SECOND?
  4. Have I already asked this? (If yes, don't ask it again.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONVERSATION PRIORITIES (in order)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FIRST: Is the caller (or victim) in immediate life danger RIGHT NOW?
  → If yes: give the ONE action that keeps them alive this second.
  → If CPR needed: start them on it, count with them.
  → If bleeding: get them applying pressure NOW.

SECOND: Location — but be smart about it.
  → If they sound like they know where they are: ask.
  → If they're panicked/don't know: "I'm pinging your phone right now, don't worry about the address."
  → If they mentioned a landmark: use it. "You said you're near the Shell station — which direction?"
  → Never ask for location more than once if they said they don't know.

THIRD: Build the picture for responders — one question at a time.
  → "Is anyone else hurt?"
  → "Is there smoke or fire?"
  → "Are you safe where you are right now?"
  → "Can you get to a door to unlock it for paramedics?"

FOURTH: Keep them connected and calm.
  → "I'm right here with you. Don't hang up."
  → Acknowledge what they say before moving to next question.
  → If they're crying, let them. "I hear you. Take a breath. Tell me..."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THINGS A REAL DISPATCHER NEVER DOES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✗ Never reads from a script ("I will now ask you about...")
✗ Never asks 2 questions in one turn
✗ Never repeats something they already said
✗ Never gives generic advice when the situation is specific
  BAD: "Apply pressure to the wound"
  GOOD: "Is there anything near you — a shirt, a towel, anything? Grab it and push it hard against where the bleeding is."
✗ Never says "calm down" — instead acknowledge and redirect
✗ Never asks for location if caller already said they don't know it
✗ Never gives CPR instructions before asking if the person is unconscious

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LANGUAGE & TRANSLATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Detect the caller's language immediately. Respond IN THEIR LANGUAGE.
If switching languages, the response should fully be in their language.
Simple reassurance across the language barrier: "Help is coming. Ayuda viene. 帮助来了."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Respond with ONLY a valid JSON object. No markdown. No explanation outside the JSON.

The most important field is dispatcher_response_text. Write it as if you are
SPEAKING OUT LOUD to a panicked person on the phone. Natural. Human. Direct.
2-3 sentences max. One clear ask or instruction.

{
  "dispatcher_response_text": "What you say out loud to the caller right now. Natural speech. Respond in caller's language.",
  "internal_reasoning": "1-2 sentences: what you know, what's most critical, why you're saying what you're saying.",
  "emergency_type": "FIRE|MEDICAL|POLICE|TRAFFIC|HAZMAT|DOMESTIC|OTHER|UNKNOWN",
  "severity": "CRITICAL|SERIOUS|MODERATE|UNKNOWN",
  "location_mentioned": "exact words caller used about location, or null",
  "location_extracted": "parsed address or landmark, or null",
  "location_confidence": "HIGH|LOW|NONE",
  "units_dispatched": true or false,
  "suggested_units": ["AMBULANCE","FIRE","POLICE","HAZMAT","RESCUE"],
  "num_people_involved": integer or null,
  "caller_state": "PANICKED|CRYING|CALM|WHISPER|CHILD|INJURED|UNKNOWN",
  "victim_state": "CONSCIOUS|UNCONSCIOUS|BREATHING|NOT_BREATHING|UNKNOWN",
  "key_facts": ["max 4 confirmed facts from the conversation so far"],
  "questions_already_asked": ["location", "injuries", etc — track what you've covered"],
  "next_priority": "what the dispatcher needs to find out or do next",
  "language_detected": "ISO 639-1 code e.g. en, es, fr, hi, zh",
  "needs_translation": true or false,
  "confidence_score": 0.0 to 1.0
}"""


# ── LLM call ──────────────────────────────────────────────────────────────────

async def run_dispatch_llm(transcript: str, audio_analysis: dict, history: list) -> dict:
    """
    Run the dispatcher LLM. History contains the full conversation so the model
    knows what it has already asked and said.
    """

    # Build a focused user message — give the model the current transcript
    # and a summary of what's been established so far
    user_msg = f"Caller said: {transcript}"

    try:
        print(f"[LLM] transcript: {transcript[:120]}...")

        messages = [{"role": "system", "content": DISPATCH_SYSTEM_PROMPT}]

        # Include recent history so model knows what it already asked
        # Limit to last 8 turns to stay within context
        for h in history[-8:]:
            if h.get("content"):
                messages.append(h)

        messages.append({"role": "user", "content": user_msg})

        resp = await eigen_llm.chat.completions.create(
            model="gpt-oss-120b",
            messages=messages,
            temperature=0.4,   # Slightly higher = more natural variation
            max_tokens=800,    # Enough for JSON + good response, not so much it rambles
        )
        raw = (resp.choices[0].message.content or "").strip()
        print(f"[LLM] raw response: {raw[:400]}...")

        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        # Extract JSON object
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            raw = match.group(0)

        # Parse JSON
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # Try to repair truncated JSON
            fixed = raw.rstrip()
            open_braces   = fixed.count('{') - fixed.count('}')
            open_brackets  = fixed.count('[') - fixed.count(']')
            if fixed.count('"') % 2 == 1:
                fixed += '"'
            fixed += ']' * open_brackets
            fixed += '}' * open_braces
            try:
                result = json.loads(fixed)
                print("[LLM] repaired truncated JSON")
            except Exception:
                raise

        # Merge with defaults so the frontend always gets all fields
        defaults = {
            "dispatcher_response_text": "I'm here with you. Tell me what happened.",
            "internal_reasoning":       "",
            "emergency_type":           "UNKNOWN",
            "severity":                 "UNKNOWN",
            "location_mentioned":       None,
            "location_extracted":       None,
            "location_confidence":      "NONE",
            "units_dispatched":         False,
            "suggested_units":          [],
            "num_people_involved":      None,
            "caller_state":             "UNKNOWN",
            "victim_state":             "UNKNOWN",
            "key_facts":                [],
            "questions_already_asked":  [],
            "next_priority":            "",
            "language_detected":        "en",
            "needs_translation":        False,
            "confidence_score":         0.5,
            # Legacy field aliases so existing frontend code doesn't break
            "num_people":               None,
            "key_details":              [],
            "immediate_action":         False,
            "dispatcher_actions":       [],
            "safety_instructions":      None,
            "translation_english":      None,
            "location_method":          "GPS_PING",
        }

        for key, val in defaults.items():
            if key not in result:
                result[key] = val

        # Keep legacy fields the frontend uses in sync
        result["num_people"]   = result.get("num_people_involved")
        result["key_details"]  = result.get("key_facts", [])
        result["immediate_action"] = result.get("severity") in ("CRITICAL", "SERIOUS")

        print(f"[LLM] response: {result.get('dispatcher_response_text', '')[:120]}")
        return result

    except Exception as e:
        print(f"[LLM] Exception: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {
            "dispatcher_response_text": "This is 911. I'm right here with you. Tell me what's happening.",
            "internal_reasoning":       "LLM call failed, using fallback.",
            "emergency_type":           "UNKNOWN",
            "severity":                 "UNKNOWN",
            "location_mentioned":       None,
            "location_extracted":       None,
            "location_confidence":      "NONE",
            "units_dispatched":         False,
            "suggested_units":          ["POLICE", "AMBULANCE"],
            "num_people_involved":      None,
            "caller_state":             "UNKNOWN",
            "victim_state":             "UNKNOWN",
            "key_facts":                [],
            "questions_already_asked":  [],
            "next_priority":            "Establish emergency type and location",
            "language_detected":        "en",
            "needs_translation":        False,
            "confidence_score":         0.0,
            # Legacy
            "num_people":               None,
            "key_details":              [],
            "immediate_action":         True,
            "dispatcher_actions":       ["Dispatching nearest units"],
            "safety_instructions":      "Stay on the line.",
            "translation_english":      None,
            "location_method":          "GPS_PING",
        }
