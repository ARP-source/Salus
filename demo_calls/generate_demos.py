import os
import asyncio
import sys

# Add backend to path to import voice_response
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from voice_response import synthesize_dispatcher_voice

async def main():
    demos = [
        {"name": "en_cardiac_arrest.wav", "text": "This is the 911 dispatch center. We have received your call regarding a cardiac arrest. Help is on the way. Begin CPR immediately.", "voice": "Linda"},
        {"name": "es_structure_fire.wav", "text": "Este es el centro de emergencias 911. Hemos recibido su llamada sobre el incendio. La ayuda está en camino. Por favor, evacúe el edificio.", "voice": "Linda"},
        {"name": "hi_road_collision.wav", "text": "यह 911 आपातकालीन केंद्र है। हमें सड़क दुर्घटना के बारे में आपका कॉल प्राप्त हुआ है। एम्बुलेंस रास्ते में है। कृपया शांत रहें।", "voice": "Linda"}
    ]
    
    out_dir = os.path.dirname(__file__)
    for demo in demos:
        out_path = os.path.join(out_dir, demo["name"])
        print(f"Generating {demo['name']}...")
        audio_bytes = await synthesize_dispatcher_voice(demo["text"], voice=demo["voice"], speed=0.9)
        if audio_bytes:
            with open(out_path, "wb") as f:
                f.write(audio_bytes)
            print(f"Saved {demo['name']}")
        else:
            print(f"Failed to generate {demo['name']}")

if __name__ == "__main__":
    asyncio.run(main())
