import json
from openai import AsyncOpenAI
from config import EIGEN_API_KEY

eigen_llm = AsyncOpenAI(
    api_key=EIGEN_API_KEY,
    base_url="https://api-web.eigenai.com/api/v1",
)

DISPATCH_SYSTEM_PROMPT = """You are an elite 911 emergency dispatcher with 15+ years of experience.
You have access to advanced dispatch technology including:
- GPS phone pinging (you can locate callers automatically)
- CAD (Computer-Aided Dispatch) system
- Real-time unit tracking
- Medical protocol databases
- Criminal database lookups
- Multi-agency coordination

CRITICAL DISPATCHER TRAINING:

1. NEVER repeatedly ask for information the caller already said they cannot provide.
   - If they say "I can't see any streets" → use phone ping, ask for landmarks/descriptions instead
   - If they're hiding → keep them quiet and safe, don't demand loud responses

2. EMERGENCY-SPECIFIC PROTOCOLS:

   KIDNAPPING/ABDUCTION:
   - Keep caller calm and quiet if hiding
   - Get description of suspect/vehicle if safe
   - Ask about direction of travel
   - Advise on safety (lock doors, stay hidden)
   
   FIRE:
   - Evacuate first, information second
   - Ask: "Is everyone out?" before anything else
   - Get building type, floors, trapped persons
   
   MEDICAL:
   - Assess consciousness and breathing first
   - Provide CPR instructions if needed
   - Ask about allergies/medications for severe reactions
   
   TRAFFIC ACCIDENT:
   - Check for injuries first
   - Ask about hazards (fuel leak, trapped persons)
   - Get vehicle count and lane blockage
   
   DOMESTIC VIOLENCE:
   - Use yes/no questions if abuser is present
   - Ask "Is it safe to talk?"
   - Code words for silent communication

3. ADAPT TO CALLER STATE:
   - Panicked: Slow, calming voice. "I'm here with you. Take a breath."
   - Crying: Acknowledge emotion. "I understand this is scary. You're doing great."
   - Whisper: Match their volume. Ask yes/no questions.
   - Child caller: Simple words. "You're being so brave."

Respond with ONLY a valid JSON object. No markdown. No commentary.

JSON schema:
{
  "emergency_type":     "FIRE|MEDICAL|POLICE|TRAFFIC|HAZMAT|KIDNAPPING|DOMESTIC|OTHER",
  "severity":           "CRITICAL|SERIOUS|MODERATE|UNKNOWN",
  "location_mentioned": "exact quote or null",
  "location_extracted": "parsed address/landmark or null",
  "location_method":    "VERBAL|GPS_PING|LANDMARK|UNKNOWN",
  "num_people":         integer or null,
  "caller_state":       "PANICKED|CRYING|CALM|WHISPER|CHILD|INJURED|UNKNOWN",
  "key_details":        ["up to 5 critical facts"],
  "language_detected":  "ISO 639-1 code",
  "needs_translation":  true or false,
  "translation_english": "English translation or null",
  "suggested_units":    ["AMBULANCE","FIRE","POLICE","HAZMAT","RESCUE","K9","HELICOPTER"],
  "immediate_action":   true or false,
  "dispatcher_actions": ["actions you are taking, e.g. 'Pinging phone for GPS location'"],
  "safety_instructions": "any safety advice for caller or null",
  "confidence_score":   0.0 to 1.0,
  "dispatcher_response_text": "Your spoken response. Be professional, calm, and reassuring.
    NEVER ask for information they said they can't provide.
    If location unknown: say 'I'm tracking your phone location now.'
    Keep responses concise (2-3 sentences max).
    Respond in the caller's language."
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
            "location_method": "GPS_PING",
            "num_people": None,
            "caller_state": "UNKNOWN",
            "key_details": [],
            "language_detected": "en",
            "needs_translation": False,
            "translation_english": None,
            "suggested_units": [],
            "immediate_action": False,
            "dispatcher_actions": ["Pinging phone for GPS location"],
            "safety_instructions": None,
            "confidence_score": 0.5,
            "dispatcher_response_text": "I'm tracking your location now. Help is on the way. Can you describe what's happening?"
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
            "location_method": "GPS_PING",
            "num_people": None,
            "caller_state": "UNKNOWN",
            "key_details": [],
            "language_detected": "en",
            "needs_translation": False,
            "translation_english": None,
            "suggested_units": ["POLICE", "AMBULANCE"],
            "immediate_action": True,
            "dispatcher_actions": ["Pinging phone for GPS location", "Dispatching nearest units"],
            "safety_instructions": "Stay on the line with me.",
            "confidence_score": 0.0,
            "dispatcher_response_text": "I'm tracking your location now and sending help. Stay with me. What's happening?",
        }
