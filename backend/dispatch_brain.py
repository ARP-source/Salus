import json
from openai import AsyncOpenAI
from config import EIGEN_API_KEY

eigen_llm = AsyncOpenAI(
    api_key=EIGEN_API_KEY,
    base_url="https://api-web.eigenai.com/api/v1",
)

DISPATCH_SYSTEM_PROMPT = """You are an emergency dispatch intelligence
system for a government public safety operations center. You receive
transcripts from 911 emergency calls. Your analysis directly informs
life-safety dispatch decisions. Respond with ONLY a valid JSON object.
No markdown fences. No commentary. No text outside the JSON.

CRITICAL: The caller may be panicked, crying, breathing heavily, or in distress.
You must parse their words accurately despite emotional delivery.

JSON schema — every field required:
{
  "emergency_type":     "FIRE|MEDICAL|POLICE|TRAFFIC|HAZMAT|OTHER",
  "severity":           "CRITICAL|SERIOUS|MODERATE|UNKNOWN",
  "location_mentioned": "exact quote from transcript, or null",
  "location_extracted": "parsed address or landmark, or null",
  "num_people":         integer or null,
  "caller_state":       "PANICKED|CRYING|CALM|WHISPER|UNCONSCIOUS|UNKNOWN",
  "key_details":        ["up to 5 critical facts as strings"],
  "language_detected":  "ISO 639-1 code e.g. en es hi zh fr ar pt ko ja de",
  "needs_translation":  true or false,
  "translation_english":"full English translation of transcript, or null",
  "suggested_units":    ["AMBULANCE","FIRE","POLICE","HAZMAT","RESCUE"],
  "immediate_action":   true or false,
  "confidence_score":   0.0 to 1.0,
  "dispatcher_response_text": "Exact words to speak to the caller in
    THEIR detected language. Use a FOCUSED but COMFORTING tone.
    Be calm, reassuring, and professional - the caller needs to feel
    safe and heard while you gather critical information.
    Two sentences maximum. Sentence 1: Acknowledge their emergency and
    confirm help is on the way (be warm but efficient).
    Sentence 2: Ask for the single most critical missing information,
    prioritizing location if unknown. If switching languages, respond
    in the caller's native language."
}"""

async def run_dispatch_llm(transcript: str, audio_analysis: dict, history: list) -> dict:
    """
    Process transcript through GPT-OSS to extract emergency information
    and generate dispatcher response.
    """
    import re
    import traceback
    
    user_msg = (
        f"Caller transcript:\n{transcript}\n\n"
        f"Audio analysis: {json.dumps(audio_analysis)}"
    )
    
    try:
        print(f"[LLM] Calling Eigen GPT-OSS with transcript: {transcript[:100]}...")
        
        # Build messages - skip empty history entries
        messages = [{"role": "system", "content": DISPATCH_SYSTEM_PROMPT}]
        for h in history[-6:]:
            if h.get("content"):
                messages.append(h)
        messages.append({"role": "user", "content": user_msg})
        
        resp = await eigen_llm.chat.completions.create(
            model="gpt-oss-120b",
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
        )
        raw = (resp.choices[0].message.content or "").strip()
        print(f"[LLM] Got response: {raw[:300]}...")
        
        # Strip markdown fences
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            
        # Extract JSON object
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            raw = match.group(0)
        
        result = json.loads(raw)
        
        # Ensure required fields exist with defaults
        defaults = {
            "emergency_type": "UNKNOWN",
            "severity": "UNKNOWN",
            "location_mentioned": None,
            "location_extracted": None,
            "num_people": None,
            "caller_state": "UNKNOWN",
            "key_details": [],
            "language_detected": "en",
            "needs_translation": False,
            "translation_english": None,
            "suggested_units": [],
            "immediate_action": False,
            "confidence_score": 0.5,
            "dispatcher_response_text": "I'm here to help. Can you tell me exactly where you are?"
        }
        for key, default in defaults.items():
            if key not in result:
                result[key] = default
                
        return result
        
    except Exception as e:
        print(f"[LLM] Exception: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {
            "emergency_type": "UNKNOWN",
            "severity": "UNKNOWN",
            "location_mentioned": None,
            "location_extracted": None,
            "num_people": None,
            "caller_state": "UNKNOWN",
            "key_details": [],
            "language_detected": "en",
            "needs_translation": False,
            "translation_english": None,
            "suggested_units": [],
            "immediate_action": False,
            "confidence_score": 0.0,
            "dispatcher_response_text": "I'm here to help you. Please stay on the line and tell me exactly where you are.",
        }
