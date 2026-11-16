#!/usr/bin/env python3
"""Publish reel to Instagram Reels + Facebook Page + YouTube Shorts.

Video file pehle GitHub Release asset me upload hota hai; RELEASE_URL wahi
public URL hai. Instagram/Facebook khud us URL se fetch karte hain.
YouTube ko bytes chahiye, wo runner pe local file hai.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, WORK, load_json, save_json, log  # noqa: E402

import requests  # noqa: E402

META = "https://graph.facebook.com/v21.0"


def ig_publish(video_url, caption, report):
    ig_id = os.environ.get("IG_USER_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not ig_id or not token:
        report["ig"] = "skipped (no IG creds)"
        return
    try:
        r = requests.post(
            f"{META}/{ig_id}/media",
            data={"media_type": "VIDEO", "video_url": video_url,
                  "caption": caption, "access_token": token},
            timeout=120,
        )
        j = r.json()
        cid = j.get("id")
        if not cid:
            report["ig"] = f"fail: {str(j)[:250]}"
            return
        for _ in range(40):
            st = requests.get(
                f"{META}/{cid}",
                params={"fields": "status_code,status", "access_token": token},
                timeout=60,
            ).json()
            code = st.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                report["ig"] = f"fail: {st}"
                return
            time.sleep(3)
        pub = requests.post(
            f"{META}/{ig_id}/media_publish",
            data={"creation_id": cid, "access_token": token},
            timeout=120,
        ).json()
        report["ig"] = f"ok media_id={pub.get('id')}" if pub.get("id") else f"fail: {str(pub)[:250]}"
    except Exception as e:
        report["ig"] = f"fail: {str(e)[:250]}"


def fb_publish(video_url, caption, report):
    page = os.environ.get("FB_PAGE_ID", "").strip()
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip() or os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not page or not token:
        report["fb"] = "skipped (no FB creds)"
        return
    try:
        r = requests.post(
            f"{META}/{page}/videos",
            data={"file_url": video_url, "description": caption,
                  "published": "true", "access_token": token},
            timeout=180,
        )
        j = r.json()
        report["fb"] = f"ok id={j.get('id')}" if j.get("id") else f"fail: {str(j)[:250]}"
    except Exception as e:
        report["fb"] = f"fail: {str(e)[:250]}"


def yt_publish(title, desc, tags, report):
    tok = os.environ.get("YT_TOKEN", "").strip()
    if not tok:
        report["yt"] = "skipped (no YT_TOKEN)"
        return
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = Credentials.from_authorized_user_info(json.loads(tok))
        if not creds.valid:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title[:100],
                "description": desc[:4000],
                "tags": tags[:10] if tags else ["shorts"],
                "categoryId": "28",
            },
            "status": {
                "privacyStatus": os.environ.get("PRIVACY", "public"),
                "selfDeclaredMadeForKids": False,
            },
        }
        req = yt.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(
                os.path.join(ROOT, "reel.mp4"),
                mimetype="video/mp4",
                resumable=True,
            ),
        )
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        report["yt"] = f"ok video_id={resp.get('id')}"
    except Exception as e:
        report["yt"] = f"fail: {str(e)[:250]}"


def main():
    data = load_json(os.path.join(ROOT, "data.json"), {"videos": []})
    content = load_json(os.path.join(WORK, "content.json"))
    url = os.environ.get("RELEASE_URL", "")
    tag = os.environ.get("TAG", "")

    caption_path = os.path.join(ROOT, "caption.txt")
    caption = open(caption_path, encoding="utf-8").read().strip() if os.path.exists(caption_path) else ""

    report = {}
    ig_publish(url, caption, report)
    fb_publish(url, caption, report)
    yt_publish(content.get("title", ""), caption,
               content.get("hashtags", []), report)

    save_json(os.path.join(WORK, "publish_report.json"), report)

    videos = data.get("videos", [])
    videos.append({
        "topic": content.get("topic"),
        "title": content.get("title"),
        "tag": tag,
        "url": url,
        "report": report,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    data["videos"] = videos[-200:]  # sirf aakhri 200 record rakho
    save_json(os.path.join(ROOT, "data.json"), data)

    log("publish report:", json.dumps(report, ensure_ascii=False))

    fails = [v for v in report.values() if str(v).startswith("fail")]
    if len(fails) == 3:
        sys.exit(1)


if __name__ == "__main__":
    main()
