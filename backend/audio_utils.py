import io
import base64
import soundfile as sf
import torchaudio
import torch
import numpy as np

from config import (
    VAD_THRESHOLD,
    VAD_MIN_SPEECH_MS,
    VAD_MIN_SILENCE_MS,
    VAD_SPEECH_PAD_MS
)

# Load Silero VAD globally
try:
    silero_model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,
        trust_repo=True
    )
    (get_speech_timestamps, _, read_audio, _, _) = utils
except Exception as e:
    print(f"Failed to load silero-vad: {e}")
    # Fallback to a dummy if no internet for some reason, but we expect it to work in full build.
    silero_model = None

def chunk_audio_file(file_path: str) -> tuple[list[str], dict]:
    """
    1. Load audio via soundfile
    2. Mix stereo to mono
    3. Resample to 16kHz
    4. Run Silero VAD
    5. Fill gaps between segments
    6. Split any segment > 4s (64,000 samples)
    7. Pad chunks shorter than 1600 samples
    8. Encode integer PCM -> WAV -> Base64
    """
    target_sr = 16000
    
    # 1. Load audio
    waveform, sr = torchaudio.load(file_path)
    
    # 2. Mix to mono
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)
        
    # 3. Resample
    if sr != target_sr:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=target_sr)
        waveform = resampler(waveform)
        
    wav_mono = waveform[0]
    total_samples = len(wav_mono)
    
    # 4. Run VAD
    timestamps = []
    if silero_model is not None:
        try:
            timestamps = get_speech_timestamps(
                wav_mono, 
                silero_model,
                threshold=VAD_THRESHOLD,
                sampling_rate=target_sr,
                min_speech_duration_ms=VAD_MIN_SPEECH_MS,
                min_silence_duration_ms=VAD_MIN_SILENCE_MS,
                speech_pad_ms=VAD_SPEECH_PAD_MS
            )
        except Exception as e:
            print(f"VAD error: {e}")
    
    # 5. Fill gaps to cover full audio (a simple contiguous block strategy)
    # If timestamps are empty, just use the whole audio
    if not timestamps:
        timestamps = [{'start': 0, 'end': total_samples}]
    else:
        filled = []
        last_end = 0
        for ts in timestamps:
            if ts['start'] > last_end:
                filled.append({'start': last_end, 'end': ts['start']})
            filled.append(ts)
            last_end = ts['end']
        if last_end < total_samples:
            filled.append({'start': last_end, 'end': total_samples})
        timestamps = filled

    # 6. Split > 4s
    max_samples = 4 * target_sr
    final_chunks = []
    for ts in timestamps:
        start = ts['start']
        end = ts['end']
        while (end - start) > max_samples:
            final_chunks.append({'start': start, 'end': start + max_samples})
            start += max_samples
        if end > start:
            final_chunks.append({'start': start, 'end': end})
            
    # 7 & 8: Padding & Base64 Generation
    b64_chunks = []
    for chunk in final_chunks:
        c_wav = wav_mono[chunk['start']:chunk['end']]
        
        # Pad if < 1600 samples
        if len(c_wav) < 1600:
            pad_len = 1600 - len(c_wav)
            c_wav = torch.nn.functional.pad(c_wav, (0, pad_len))
            
        # float32 -> int16
        c_int16 = (c_wav * 32767.0).clamp(-32768, 32767).numpy().astype(np.int16)
        
        # In-memory WAV bytes
        buf = io.BytesIO()
        sf.write(buf, c_int16, target_sr, format='WAV', subtype='PCM_16')
        wav_bytes = buf.getvalue()
        
        # Base64 string
        b64 = base64.b64encode(wav_bytes).decode('utf-8')
        b64_chunks.append(b64)
        
    metadata = {
        "num_chunks": len(b64_chunks),
        "total_samples": total_samples,
        "sample_rate": target_sr
    }
        
    return b64_chunks, metadata
