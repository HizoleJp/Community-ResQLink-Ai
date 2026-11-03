"""
ResQLink AI Chatbot with conversation memory.
Keeps the last N messages per session and uses them for context.
"""
import time
from typing import List, Dict, Optional

# ---------- Session memory ----------
# { session_id: { "messages": [ {role, text, ts} ], "last": ts } }
_SESSIONS: Dict[str, Dict] = {}
MAX_TURNS = 12         # keep last 12 messages (6 user + 6 bot)
SESSION_TTL = 1800     # 30 minutes


def _cleanup():
    """Remove expired sessions."""
    now = time.time()
    dead = [sid for sid, s in _SESSIONS.items() if now - s["last"] > SESSION_TTL]
    for sid in dead:
        _SESSIONS.pop(sid, None)


def get_history(session_id: str) -> List[Dict]:
    _cleanup()
    if not session_id:
        return []
    return _SESSIONS.get(session_id, {}).get("messages", [])


def add_turn(session_id: str, role: str, text: str):
    if not session_id:
        return
    _cleanup()
    sess = _SESSIONS.setdefault(session_id, {"messages": [], "last": time.time()})
    sess["messages"].append({"role": role, "text": text, "ts": time.time()})
    sess["messages"] = sess["messages"][-MAX_TURNS:]
    sess["last"] = time.time()


def clear_session(session_id: str):
    _SESSIONS.pop(session_id, None)


# ---------- Response templates ----------
FIRE_SAFETY = (
    "<b>🔥 Fire Safety Guidance:</b><br>"
    "1. Stay low to the ground to avoid inhaling dense smoke.<br>"
    "2. Feel doors with the back of your hand before opening.<br>"
    "3. Never use elevators during a fire evacuation.<br>"
    "4. If trapped, seal doors with wet cloths & signal from a window."
)

FIRST_AID = (
    "<b>🩹 First Aid Basics:</b><br>"
    "• <b>Burns:</b> Cool under cool running water for 10–20 minutes. Never apply ice or butter.<br>"
    "• <b>Bleeding:</b> Apply direct, firm pressure with a clean cloth.<br>"
    "• <b>Breathing issues:</b> Keep person seated upright and clear surrounding smoke."
)

FLOOD_SAFETY = (
    "<b>🌊 Flood Safety:</b><br>"
    "1. Move to higher ground immediately.<br>"
    "2. Never walk or drive through floodwater — 15 cm can knock you down.<br>"
    "3. Turn off electricity at the main breaker if safe to do so.<br>"
    "4. Boil drinking water after the flood until authorities say it's safe."
)

EARTHQUAKE_SAFETY = (
    "<b>🌍 Earthquake Safety:</b><br>"
    "1. <b>Duck, Cover, Hold.</b> Get under a sturdy table and hold on.<br>"
    "2. Stay away from windows and tall furniture.<br>"
    "3. If outdoors, move to an open area away from buildings and power lines.<br>"
    "4. After shaking stops, evacuate calmly and check for injuries."
)

EMERGENCY_NUMBERS = (
    "<b>🚨 Emergency Numbers:</b><br>"
    "• National Emergency: <b>911</b><br>"
    "• Bureau of Fire Protection (BFP): <b>(02) 8426-0219</b><br><br>"
    "Tap <b>Emergency Call</b> in the app to dial 911 directly."
)

EVACUATION_TIP = (
    "<b>🧭 Evacuation Tip:</b> Switch to the <b>Rescue Me</b> tab and press "
    "<i>'Find Safe Route'</i>. I will calculate real-time safe routes away from known hazards."
)

FALLBACK = (
    "🤖 I am standing by to assist. Ask me about <b>fire safety procedures</b>, "
    "<b>safe evacuation centers</b>, <b>first aid</b>, or tap <b>Emergency Call</b> "
    "for immediate emergency dispatch."
)


# ---------- Intent detection ----------
def _has_any(text: str, words) -> bool:
    return any(w in text for w in words)


def _last_topic(history: List[Dict]) -> Optional[str]:
    """Return the most recent user intent tag if we stored one."""
    for turn in reversed(history):
        if turn.get("role") == "meta" and turn.get("text"):
            return turn["text"]
    return None


def generate_reply(
    message: str,
    session_id: str = None,
    user_name: str = None,
    user_pos: tuple = None,
    centers: list = None,
) -> dict:
    q = (message or "").lower().strip()
    centers = centers or []
    history = get_history(session_id) if session_id else []

    # Detect "follow-up" style questions (short, or using anaphora)
    followup = _has_any(q, ("that", "it", "there", "those", "them", "more", "again")) or len(q) < 12
    last_topic = _last_topic(history)

    # ---------------- Intent matching ----------------
    intent = None
    reply = None

    # Fire
    if _has_any(q, ("fire", "smoke", "burn", "flame")):
        intent, reply = "fire_safety", FIRE_SAFETY

    # Flood
    elif _has_any(q, ("flood", "water rising", "baha")):
        intent, reply = "flood_safety", FLOOD_SAFETY

    # Earthquake
    elif _has_any(q, ("earthquake", "shaking", "lindol")):
        intent, reply = "earthquake_safety", EARTHQUAKE_SAFETY

    # First aid
    elif _has_any(q, ("first aid", "hurt", "injury", "bleed", "wound")):
        intent, reply = "first_aid", FIRST_AID

    # Emergency contacts
    elif _has_any(q, ("call", "phone", "911", "contact", "number", "hotline")):
        intent, reply = "contacts", EMERGENCY_NUMBERS

    # Evacuation
    elif _has_any(q, ("evacuat", "center", "route", "safe", "shelter")):
        if centers:
            closest = centers[0]
            name = closest.get("name", "the nearest center")
            dist = closest.get("distanceKm") or closest.get("distance_km") or 0
            reply = (
                f"<b>🧭 Evacuation Info:</b><br>There are "
                f"<b>{len(centers)} centers</b> loaded nearby. The closest is "
                f"<b>{name}</b> ({dist:.2f} km away).<br><br>"
                f"Tap <i>'Find Safe Route'</i> on the Rescue Me tab for live dynamic navigation."
            )
            intent = "evacuation_with_data"
        else:
            intent, reply = "evacuation", EVACUATION_TIP

    # Location
    elif _has_any(q, ("status", "where am i", "location", "gps", "my pos")):
        if user_pos:
            reply = (
                f"<b>📍 Location Status:</b><br>"
                f"Coordinates: {user_pos[0]:.5f}, {user_pos[1]:.5f}.<br>"
                f"Your GPS signal is active and live-tracking."
            )
            intent = "location"
        else:
            reply = (
                "<b>📍 Location Status:</b> Currently acquiring GPS fix... "
                "Please ensure location permissions are granted."
            )
            intent = "location_no_fix"

    # Greetings
    elif q in ("hi", "hey", "hello", "helo", "yo") or _has_any(q, ("hello", "good morning", "good evening")):
        name = user_name or "there"
        intent = "greeting"
        reply = (
            f"Hello {name}! I'm your AI Emergency Assistant. "
            f"I can help with fire safety advice, locating evacuation centers, "
            f"or guiding emergency reports. How can I help?"
        )

    # "help" keyword
    elif q == "help" or q.startswith("help "):
        intent = "help"
        reply = (
            "<b>🤖 How I can help:</b><br>"
            "• <b>Fire safety</b> — ask 'what to do during fire'<br>"
            "• <b>Flood safety</b> — ask 'flood tips'<br>"
            "• <b>Earthquake</b> — ask 'earthquake safety'<br>"
            "• <b>First aid</b> — ask 'how to treat burns'<br>"
            "• <b>Evacuation</b> — ask 'nearest evacuation center'<br>"
            "• <b>Location</b> — ask 'where am I'<br>"
            "• <b>Emergency numbers</b> — ask 'how to call 911'"
        )

    # ---------------- Follow-up handling ----------------
    if not reply and followup and last_topic:
        # Re-answer based on last topic with a "more" flavor
        followups = {
            "fire_safety": "<b>🔥 More fire tips:</b><br>"
                "• Close doors behind you as you leave to slow the fire.<br>"
                "• If your clothes catch fire: Stop, Drop, and Roll.<br>"
                "• Once out, stay out — never re-enter a burning building.<br>"
                "• Call 911 from a safe location.",
            "flood_safety": "<b>🌊 More flood tips:</b><br>"
                "• Keep a 72-hour emergency kit ready (water, food, flashlight, radio).<br>"
                "• Photograph your home before the flood for insurance.<br>"
                "• Avoid contact with floodwater — it may carry sewage or chemicals.",
            "earthquake_safety": "<b>🌍 More earthquake tips:</b><br>"
                "• Prepare a 'Go Bag' with documents, medicine, and water.<br>"
                "• Know your building's evacuation route in advance.<br>"
                "• Expect aftershocks — they can be as strong as the main quake.",
            "first_aid": "<b>🩹 More first-aid tips:</b><br>"
                "• For sprains: Rest, Ice, Compression, Elevation (RICE).<br>"
                "• For shock: Lay the person down, keep them warm, do not give food.<br>"
                "• For choking: 5 back blows, then 5 abdominal thrusts.",
            "evacuation": "<b>🧭 More evacuation tips:</b><br>"
                "• Bring only essentials — you may not return for days.<br>"
                "• Lock your home and turn off utilities before leaving.<br>"
                "• Follow official routes — shortcuts may be blocked.",
            "contacts": "<b>🚨 Additional hotlines:</b><br>"
                "• NDRRMC: (02) 8911-1406<br>"
                "• Philippine Red Cross: 143 or (02) 8790-2300<br>"
                "• MMDA: 136",
            "location": "<b>📍 More about your location:</b><br>"
                "• Your live GPS is enabled and shared with responders.<br>"
                "• Tap 'Share Location' on the home screen to send it via SMS or Messenger.",
        }
        if last_topic in followups:
            reply = followups[last_topic]
            intent = last_topic + "_followup"

    # ---------------- Fallback ----------------
    if not reply:
        intent = "fallback"
        reply = FALLBACK

    # ---------------- Store memory ----------------
    if session_id:
        add_turn(session_id, "user", message)
        add_turn(session_id, "bot", reply)
        # Store a lightweight meta-tag for follow-up detection
        add_turn(session_id, "meta", intent)

    return {"reply": reply, "intent": intent}