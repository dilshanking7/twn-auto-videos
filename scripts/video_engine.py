#!/usr/bin/env python3
"""Video engine: text-to-video / image-to-video provider ladder.

Ladder (jab tak na chale, agle rung pe jaata hai):
  1. Hugging Face serverless (CogVideoX)  -> HF_TOKEN (optional)
  2. free.ai                                 -> FREEAI_API_KEY (optional)
  3. Pollinations (keyless, rate-limited)
  4. Pexels/Pixabay stock clips (guaranteed fallback)
  5. Agar sab fail: Pollinations image + FFmpeg Ken Burns

Output: work/clips/*.mp4 + work/engine_report.json
"""
import base64
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, WORK, load_json, save_json, log  # noqa: E402

import requests  # noqa: E402

CLIPS = os.path.join(WORK, "clips")


def _is_video(resp):
    ct = resp.headers.get("content-type", "")
    if "video" in ct:
        return True
    head = resp.content[:32]
    return b"ftyp" in head or len(resp.content) > 20000


def _save(resp, path):
    with open(path, "wb") as f:
        f.write(resp.content)
    return os.path.getsize(path) > 5000


# ---------------------------------------------------------------- HF rung
def hf_t2v(prompt, out):
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        return False
    for model in ["THUDM/CogVideoX-5b", "THUDM/CogVideoX-2b"]:
        try:
            r = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers={"Authorization": f"Bearer {token}"},
                json={"inputs": prompt},
                timeout=240,
            )
            if r.status_code == 200 and _is_video(r) and _save(r, out):
                log("HF t2v ok:", model)
                return True
            log("HF t2v", model, r.status_code, r.text[:120].replace("\n", " "))
        except Exception as e:
            log("HF t2v err", model, str(e)[:150])
    return False


def hf_i2v(image, prompt, out):
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        return False
    try:
        if image.startswith("http"):
            img = requests.get(image, timeout=90).content
        else:
            with open(image, "rb") as f:
                img = f.read()
        payload = {
            "image": "data:image/jpeg;base64," + base64.b64encode(img).decode(),
            "prompt": prompt,
        }
        r = requests.post(
            "https://api-inference.huggingface.co/models/THUDM/CogVideoX-5b-i2v",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"inputs": payload},
            timeout=240,
        )
        if r.status_code == 200 and _is_video(r) and _save(r, out):
            log("HF i2v ok")
            return True
        log("HF i2v", r.status_code, r.text[:150].replace("\n", " "))
    except Exception as e:
        log("HF i2v err", str(e)[:150])
    return False


# ------------------------------------------------------------ free.ai rung
def freeai(prompt, out, image_url=None):
    key = os.environ.get("FREEAI_API_KEY", "").strip()
    if not key:
        return False
    try:
        body = {"prompt": prompt, "duration": 5}
        if image_url:
            body["image_url"] = image_url
        r = requests.post(
            "https://api.free.ai/v1/video/generate/",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        j = r.json() if r.status_code == 200 else {}
        log("free.ai submit", r.status_code, str(j)[:150])
        task = j.get("id") or j.get("task_id") or (j.get("data") or {}).get("id")
        video_url = j.get("video_url") or j.get("url")
        if video_url:
            rr = requests.get(video_url, timeout=180)
            return rr.status_code == 200 and _is_video(rr) and _save(rr, out)
        if not task:
            return False
        for _ in range(24):
            time.sleep(5)
            st = requests.get(
                f"https://api.free.ai/v1/video/status/{task}",
                headers={"Authorization": f"Bearer {key}"},
                timeout=60,
            )
            sj = st.json() if st.status_code == 200 else {}
            u = sj.get("video_url") or sj.get("url")
            status = str(sj.get("status", "")).lower()
            if u:
                rr = requests.get(u, timeout=180)
                return rr.status_code == 200 and _is_video(rr) and _save(rr, out)
            if status in ("failed", "error"):
                log("free.ai failed:", str(sj)[:150])
                return False
        return False
    except Exception as e:
        log("free.ai err", str(e)[:150])
        return False


# ------------------------------------------------------- Pollinations rung
def pollinations_video(prompt, out):
    try:
        url = "https://gen.pollinations.ai/video/" + urllib.parse.quote(prompt)
        r = requests.get(url, params={"model": "seedance"}, timeout=240, stream=True)
        if r.status_code == 200:
            tmp = out + ".part"
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
            if os.path.getsize(tmp) > 5000:
                os.replace(tmp, out)
                log("Pollinations video ok")
                return True
            os.remove(tmp)
        log("Pollinations video", r.status_code)
    except Exception as e:
        log("Pollinations video err", str(e)[:150])
    return False


def pollinations_image(prompt, out):
    try:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and len(r.content) > 5000:
            with open(out, "wb") as f:
                f.write(r.content)
            log("Pollinations image ok")
            return True
    except Exception as e:
        log("Pollinations image err", str(e)[:150])
    return False


# ---------------------------------------------------------- stock footage
def _download(url, path):
    try:
        with requests.get(url, stream=True, timeout=120,
                         headers={"User-Agent": "Mozilla/5.0"}) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_content(1 << 20):
                    f.write(chunk)
        return os.path.getsize(path) > 5000
    except Exception as e:
        log("download fail", str(e)[:120])
        return False


def stock_clips(keywords, n=6):
    clips = []
    pix = os.environ.get("PIXABAY_API_KEY", "").strip()
    pex = os.environ.get("PEXELS_API_KEY", "").strip()

    queries = list(keywords) + ["technology", "computer", "coding", "futuristic", "data", "internet"]

    if pix:
        for q in queries:
            if len(clips) >= n:
                break
            try:
                r = requests.get(
                    "https://pixabay.com/api/videos/",
                    params={"key": pix, "q": q, "per_page": 12, "safesearch": "true"},
                    timeout=60,
                )
                hits = r.json().get("hits", []) if r.status_code == 200 else []
                for h in hits:
                    vids = h.get("videos", {})
                    url = (vids.get("medium") or vids.get("small") or {}).get("url")
                    if not url:
                        continue
                    path = os.path.join(CLIPS, f"stock{len(clips):02d}.mp4")
                    if _download(url, path):
                        clips.append(path)
                        break
            except Exception as e:
                log("pixabay err", str(e)[:120])

    if pex and len(clips) < n:
        for q in queries:
            if len(clips) >= n:
                break
            try:
                r = requests.get(
                    "https://api.pexels.com/videos/search",
                    params={"query": q, "per_page": 12, "orientation": "portrait"},
                    headers={"Authorization": pex},
                    timeout=60,
                )
                items = r.json().get("videos", []) if r.status_code == 200 else []
                for it in items:
                    files = it.get("video_files", [])
                    pick = next((f for f in files if f.get("quality") == "hd"), None) or (files[0] if files else None)
                    if not pick:
                        continue
                    path = os.path.join(CLIPS, f"stock{len(clips):02d}.mp4")
                    if _download(pick.get("link"), path):
                        clips.append(path)
                        break
            except Exception as e:
                log("pexels err", str(e)[:120])

    return clips


def kenburns_still(image_path, out, duration=5):
    """Image ko Ken Burns motion deta hai — sabse aakhri fallback."""
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,"
        f"zoompan=z='min(zoom+0.0015,1.3)':d=125:s=1080x1920:fps=25"
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    from common import run
    run(["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-vf", vf,
         "-t", str(duration), "-r", "25", "-an", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", out], timeout=180)
    return os.path.exists(out)


# ------------------------------------------------------------------- main
def main():
    os.makedirs(CLIPS, exist_ok=True)
    content = load_json(os.path.join(WORK, "content.json"))
    prompt = content.get("script") or content.get("topic") or "technology news"
    image = os.environ.get("INPUT_IMAGE", "").strip()
    mode = os.environ.get("MODE", "text").strip().lower()

    used = []
    ok = False

    if mode == "image" and image and (os.path.exists(image) or image.startswith("http")):
        log("mode=image, source:", image[:120])
        out = os.path.join(CLIPS, "ai0.mp4")
        ok = hf_i2v(image, prompt, out)
        used.append("hf_i2v" if ok else "")
        if not ok:
            ok = freeai(prompt, out, image_url=image if image.startswith("http") else None)
            used.append("freeai_i2v" if ok else "")
        if not ok:
            # still image -> Ken Burns (guaranteed)
            still = os.path.join(CLIPS, "still.jpg")
            if image.startswith("http"):
                try:
                    r = requests.get(image, timeout=90)
                    if r.status_code == 200:
                        with open(still, "wb") as f:
                            f.write(r.content)
                except Exception:
                    pass
            elif os.path.exists(image):
                still = image
            if os.path.exists(still) and kenburns_still(still, out, duration=5):
                ok = True
                used.append("kenburns_still")

    if not ok:
        out = os.path.join(CLIPS, "ai0.mp4")
        ok = hf_t2v(prompt, out)
        used.append("hf_t2v" if ok else "")
        if not ok:
            ok = freeai(prompt, out)
            used.append("freeai" if ok else "")
        if not ok:
            ok = pollinations_video(prompt, out)
            used.append("pollinations" if ok else "")

    if not ok:
        log("AI rungs fail — stock footage fallback")
        used.append("stock")
        clips = stock_clips(content.get("search_keywords", []), n=6)
        if clips:
            # stock clips ko seedha CLIPS me daal do
            for c in clips:
                dst = os.path.join(CLIPS, f"stock{len(os.listdir(CLIPS)):02d}.mp4")
                os.replace(c, dst)
            used.append(f"stock:{len(clips)}")
        else:
            # aakhri fallback: image lo, Ken Burns do
            img = os.path.join(CLIPS, "fallback.jpg")
            if pollinations_image(prompt, img):
                used.append("kenburns")
                ok = kenburns_still(img, os.path.join(CLIPS, "ken0.mp4"), duration=5)
            else:
                # emergency synthetic clip
                from common import run
                run(["ffmpeg", "-y", "-f", "lavfi",
                     "-i", "testsrc2=size=1080x1920:rate=25:duration=5",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p",
                     os.path.join(CLIPS, "synth0.mp4")], timeout=120)
                used.append("synthetic")

    report = {"rungs_used": [u for u in used if u], "mode": mode or "text"}
    save_json(os.path.join(WORK, "engine_report.json"), report)
    log("engine report:", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
