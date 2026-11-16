#!/usr/bin/env python3
"""Topic + script + caption generator (Gemini, free).

Reads data.json (posted history) and config/topics.json, then asks Gemini
for a fresh Hinglish reel script. Saves work/content.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, WORK, load_json, save_json, log  # noqa: E402

import requests  # noqa: E402

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
VOICE = os.environ.get("TTS_VOICE", "en-IN-NeerjaNeural")

FALLBACK = {
    "topic": "AI tools jo aapka kaam aasan karte hain",
    "title": "5 AI tools jo aapka kaam aadha kar denge",
    "script": (
        "Kya aap jaante hain ki aaj ke AI tools aapka kaam aadha kar sakte hain? "
        "Yeh tools aapke liye waqt bachat hain aur productivity badha dete hain. "
        "Inhe aaj hi try karo."
    ),
    "caption": "Ye AI tools try karke dekho. Follow karo aur share karo.",
    "hashtags": ["#Tech", "#AI", "#Shorts"],
    "search_keywords": [
        "technology", "artificial intelligence", "computer", "office",
        "coding", "robot", "data", "internet",
    ],
}


def gemini(prompt):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    r = requests.post(
        url,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
        },
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    text = text.removeprefix("```json").removesuffix("```").strip()
    return json.loads(text)


def main():
    data = load_json(os.path.join(ROOT, "data.json"), {"videos": []})
    topics = load_json(os.path.join(ROOT, "config", "topics.json"), {})
    pillars = topics.get("pillars") or ["Tech news", "AI tools", "World events"]
    videos = data.get("videos", [])
    pillar = pillars[len(videos) % len(pillars)]
    recent = [v.get("topic") for v in videos[-40:]]

    prompt = f"""Tum ek Hinglish tech/world-news Instagram Reels creator ho (Roman Hindi + English mix).
Aaj ka pillar: {pillar}
Pichle topics (repeat mat karna): {recent}

Kaam: ek naya, sahi aur verified topic chuno aur 20-30 second ka reel banane ke liye content do.

Rules:
- Pehli line 8 shabd se chhoti aur curiosity wali ho.
- Chhote tez vakya likho; sirf pakke facts, guess ya jhoot mat likhna.
- Script me sirf bolne wale shabd hon (koi emoji, hashtag ya bracket nahi), lagbhag 45-60 shabd.
- Title 70 character se chhota ho.
- search_keywords: stock footage dhundhne ke liye 8 ENGLISH keywords do.

Sirf JSON do:
{{"topic":"...","title":"...","script":"...","caption":"2-3 line Hinglish caption","hashtags":["#..."],"search_keywords":["..."],"pillar":"..."}}"""

    try:
        c = gemini(prompt)
    except Exception as e:
        log("Gemini fail, fallback content use ho raha hai:", str(e)[:200])
        c = dict(FALLBACK)

    c.setdefault("pillar", pillar)
    c["voice"] = VOICE
    save_json(os.path.join(WORK, "content.json"), c)
    log("topic:", c.get("topic"))


if __name__ == "__main__":
    main()
