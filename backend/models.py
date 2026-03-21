from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class DispatchResponse(BaseModel):
    emergency_type: Literal["FIRE", "MEDICAL", "POLICE", "TRAFFIC", "HAZMAT", "OTHER"]
    severity: Literal["CRITICAL", "SERIOUS", "MODERATE", "UNKNOWN"]
    location_mentioned: Optional[str] = Field(None, description="exact quote from transcript")
    location_extracted: Optional[str] = Field(None, description="parsed address or landmark")
    num_people: Optional[int] = None
    caller_state: Literal["PANICKED", "CRYING", "CALM", "WHISPER", "UNCONSCIOUS", "UNKNOWN"]
    key_details: List[str] = Field(..., max_items=5)
    language_detected: str = Field(..., description="ISO 639-1 code")
    needs_translation: bool
    translation_english: Optional[str] = None
    suggested_units: List[Literal["AMBULANCE", "FIRE", "POLICE", "HAZMAT", "RESCUE"]]
    immediate_action: bool
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    dispatcher_response_text: str = Field(..., description="Exact words to speak to caller")
