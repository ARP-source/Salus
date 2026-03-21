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
    THEIR detected language. Professional, controlled, authoritative.
    Two sentences maximum. Sentence 1: confirm you have received the
    call and help is being dispatched. Sentence 2: ask for the single
    most critical missing piece of information, prioritizing location
    if it has not been provided."
}"""

async def run_dispatch_llm(transcript: str, audio_analysis: dict, history: list) -> dict:
    user_msg = (
        f"Caller transcript:\n{transcript}\n\n"
        f"Audio analysis: {json.dumps(audio_analysis)}"
    )
    resp = await eigen_llm.chat.completions.create(
        model="gpt-oss-120b",
        messages=[
            {"role": "system", "content": DISPATCH_SYSTEM_PROMPT},
            *history[-6:],
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
        extra_body={"reasoning_effort": "high"},
        max_tokens=700,
        stream=False,
    )
    raw = (resp.choices[0].message.content or "").strip()
    return json.loads(raw)
