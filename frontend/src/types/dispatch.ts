export interface DispatchResponse {
    emergency_type: 'FIRE' | 'MEDICAL' | 'POLICE' | 'TRAFFIC' | 'HAZMAT' | 'OTHER';
    severity: 'CRITICAL' | 'SERIOUS' | 'MODERATE' | 'UNKNOWN';
    location_mentioned: string | null;
    location_extracted: string | null;
    num_people: number | null;
    caller_state: 'PANICKED' | 'CRYING' | 'CALM' | 'WHISPER' | 'UNCONSCIOUS' | 'UNKNOWN';
    key_details: string[];
    language_detected: string;
    needs_translation: boolean;
    translation_english: string | null;
    suggested_units: Array<'AMBULANCE' | 'FIRE' | 'POLICE' | 'HAZMAT' | 'RESCUE'>;
    immediate_action: boolean;
    confidence_score: number;
    dispatcher_response_text: string;
}

export interface WebsocketMessage {
    type: 'audio' | 'start' | 'stop' | 'dispatch_update' | 'error' | 'simulate';
    data?: any;
    error?: string;
}
