"""
generate_demos.py — Salus Hackathon Demo Generator

Generates multi-turn caller audio for each scenario.
Each scenario is a sequence of caller utterances that play one-by-one,
with Salus responding between each one.

Run once: python demo_calls/generate_demos.py
"""

import os
import sys
import json
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from voice_response import synthesize_dispatcher_voice

# ── Scenario definitions ───────────────────────────────────────────────────────
# Each scenario has a series of caller "turns" — what the panicked person says.
# Salus will respond between each one in real-time.
# The audio is synthesized using TTS to sound like different callers.

SCENARIOS = {
    "en_cardiac_arrest": {
        "voice": "Alex",   # Male voice for panicked husband caller
        "language": "en",
        "turns": [
            # Turn 1: Initial call — pure panic
            "Hello?! Oh god, please help me — my husband just collapsed! He was just sitting there and then he fell off the chair and he's not moving, he's not breathing, please I don't know what to do—",
            # Turn 2: Response to Salus asking about location
            "We're at home, 4821 Maple Drive, please hurry, I don't — he's on the floor, he's completely limp—",
            # Turn 3: Response to CPR instructions
            "Okay okay I'm on my knees, my hands are on his chest — like this? I'm pushing, is this right? How hard do I push?",
            # Turn 4: During CPR — emotional, exhausted
            "I'm doing it, I'm counting — oh god he's not waking up, how long until they get here, please tell me they're coming—",
            # Turn 5: Signs of help arriving
            "I can hear the siren — I think I can hear them outside — should I stop? Should I go open the door?",
        ]
    },
    "es_structure_fire": {
        "voice": "Linda",  # Female Spanish caller
        "language": "es",
        "turns": [
            # Turn 1: Spanish — panicked, fire in building
            "¡Ayuda! ¡Por favor ayúdenme! ¡Hay un incendio en mi edificio, en el tercer piso! ¡Hay humo por todos lados, no puedo salir!",
            # Turn 2: Responding to dispatcher
            "¡Estoy en el apartamento 3C! ¡Hay una señora mayor en el 3A que no puede caminar, alguien tiene que ayudarla!",
            # Turn 3: Following instructions
            "Sí, cerré la puerta. Hay humo por debajo... ¿qué hago? ¡Tengo miedo, tengo a mi bebé conmigo!",
            # Turn 4: Update
            "Estoy en la ventana, puedo ver la calle. ¿Ya vienen los bomberos? Mi bebé está llorando—",
            # Turn 5: Fire trucks arrive
            "¡Los veo! ¡Aquí, estoy aquí en la ventana! ¡Los estoy viendo!",
        ]
    },
    "hi_road_collision": {
        "voice": "Linda",
        "language": "hi",
        "turns": [
            # Turn 1: Hindi — road accident
            "हैलो? मुझे मदद चाहिए — एक बड़ा एक्सीडेंट हुआ है! हाइवे पर, दो गाड़ियाँ टकरा गई हैं! एक आदमी बाहर गिरा है, वो हिल नहीं रहा!",
            # Turn 2: Location
            "हम NH48 पर हैं, गुड़गाँव से दिल्ली की तरफ, पेट्रोल पंप के पास — मुझे नहीं पता नंबर क्या है यहाँ का—",
            # Turn 3: Victim status
            "वो साँस ले रहा है, लेकिन बेहोश है। उसके सर से खून आ रहा है। मैंने उसे हिलाने की कोशिश की—",
            # Turn 4: Following instructions
            "ठीक है, मैं उसे नहीं हिला रहा। मैंने अपनी शर्ट उसके सर पर रख दी है। और लोग रुक रहे हैं यहाँ—",
            # Turn 5: Ambulance arrives
            "एम्बुलेंस आ गई! वो आ गए! क्या मुझे कुछ और करना है?",
        ]
    }
}

async def generate_scenario(name: str, scenario: dict, out_dir: str):
    """Generate all caller turn WAV files for a scenario."""
    print(f"\n{'='*50}")
    print(f"Generating scenario: {name}")
    print(f"{'='*50}")

    scenario_dir = os.path.join(out_dir, name)
    os.makedirs(scenario_dir, exist_ok=True)

    # Save scenario metadata so the backend knows how many turns there are
    meta = {
        "name": name,
        "language": scenario["language"],
        "num_turns": len(scenario["turns"]),
        "turns": [{"index": i, "text": t} for i, t in enumerate(scenario["turns"])]
    }
    with open(os.path.join(scenario_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"Saved meta.json ({len(scenario['turns'])} turns)")

    # Generate each caller turn
    for i, text in enumerate(scenario["turns"]):
        out_path = os.path.join(scenario_dir, f"turn_{i:02d}.wav")
        if os.path.exists(out_path):
            print(f"  turn {i}: already exists, skipping")
            continue

        print(f"  turn {i}: generating ({len(text)} chars)...")
        print(f"    '{text[:60]}...'")

        # Use higher temperature for more natural/emotional speech
        audio = await synthesize_dispatcher_voice(
            text,
            voice=scenario["voice"],
            emotion="urgent" if i == 0 else None,  # First turn is most panicked
            temperature=0.85,  # Higher = more expressive and natural
        )

        if audio:
            with open(out_path, "wb") as f:
                f.write(audio)
            print(f"    ✓ saved {len(audio):,} bytes → {out_path}")
        else:
            print(f"    ✗ FAILED to generate turn {i}")

    print(f"Scenario '{name}' complete.")


async def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))

    print("Salus Demo Generator")
    print("Generating multi-turn caller scenarios...")
    print(f"Output: {out_dir}")

    for name, scenario in SCENARIOS.items():
        await generate_scenario(name, scenario, out_dir)

    print("\n" + "="*50)
    print("All scenarios generated!")
    print("\nScenario directories created:")
    for name in SCENARIOS:
        scenario_dir = os.path.join(out_dir, name)
        files = [f for f in os.listdir(scenario_dir) if f.endswith('.wav')]
        print(f"  {name}/ ({len(files)} WAV files)")
    print("\nRun your backend and click the demo buttons!")


if __name__ == "__main__":
    asyncio.run(main())
