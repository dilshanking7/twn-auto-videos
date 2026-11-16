#!/usr/bin/env python3
"""Render final 1080x1920 reel: FFmpeg Ken Burns + TTS + ASS captions + logo."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, WORK, load_json, save_json, log, run, dur_of  # noqa: E402

VOICE = os.environ.get("TTS_VOICE", "en-IN-NeerjaNeural")
CLIPS = os.path.join(WORK, "clips")
SEGS = os.path.join(WORK, "segs")


def make_voice(text, path):
    async def go():
        import edge_tts
        await edge_tts.Communicate(text, VOICE, rate="+5%").save(path)
    asyncio.run(go())


def make_ass(script, dur, path):
    words = script.replace("{", "").replace("}", "").split()
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 4 or (w.endswith((".", "?", "!", ",")) and len(cur) >= 2):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    if not chunks:
        chunks = [["..."]]
    total = sum(len(" ".join(c)) for c in chunks) or 1
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Cap,DejaVu Sans,78,&H0000FFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,70,70,520,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    def t(sec):
        cs = int(round(sec * 100))
        return f"{cs // 360000}:{(cs // 6000) % 60:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}"

    lines = []
    acc = 0.0
    for c in chunks:
        d = dur * (len(" ".join(c)) / total)
        lines.append(f"Dialogue: 0,{t(acc)},{t(acc + d)},Cap,,0,0,0,,{' '.join(c)}")
        acc += d
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines))


def prep_segment(clip, out, seg_dur):
    vf = ("scale=1080:1920:force_original_aspect_ratio=increase,"
          "crop=1080:1920,setsar=1,"
          "zoompan=z='min(zoom+0.0015,1.3)':d=125:s=1080x1920:fps=25")
    run(["ffmpeg", "-y", "-i", clip, "-vf", vf, "-t", str(max(1.0, seg_dur)),
         "-r", "25", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", out],
        timeout=240)


def synthetic_clip(out, seg_dur):
    run(["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"testsrc2=size=1080x1920:rate=25:duration={seg_dur}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", out], timeout=120)


def main():
    content = load_json(os.path.join(WORK, "content.json"))
    script = content.get("script", "")
    voice_path = os.path.join(WORK, "voice.mp3")
    if not os.path.exists(voice_path) or os.path.getsize(voice_path) < 1000:
        make_voice(script, voice_path)
    D = dur_of(voice_path)

    clips = []
    if os.path.isdir(CLIPS):
        clips = sorted(os.path.join(CLIPS, f) for f in os.listdir(CLIPS) if f.endswith(".mp4"))

    os.makedirs(SEGS, exist_ok=True)
    n = max(3, min(8, len(clips) or 5))
    seg = D / n
    segs = []
    for i in range(n):
        src = clips[i % len(clips)] if clips else None
        out = os.path.join(SEGS, f"seg{i:02d}.mp4")
        try:
            prep_segment(src, out, seg) if src else synthetic_clip(out, seg)
        except Exception as e:
            log("segment fail", i, str(e)[:150])
            synthetic_clip(out, seg)
        segs.append(out)

    list_path = os.path.join(WORK, "list.txt")
    with open(list_path, "w") as f:
        for s in segs:
            f.write(f"file '{s}'\n")

    base = os.path.join(WORK, "reel_base.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
         "-i", voice_path, "-filter_complex",
         "[0:v]setpts=PTS-STARTPTS[v];[1:a]volume=1.1[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-shortest", base], timeout=300)

    ass = os.path.join(WORK, "subs.ass")
    make_ass(script, D, ass)
    sub = os.path.join(WORK, "reel_sub.mp4")
    run(["ffmpeg", "-y", "-i", base, "-vf", f"subtitles={ass}", "-c:a", "copy", sub],
        timeout=300)

    final = os.path.join(ROOT, "reel.mp4")
    logo = os.path.join(ROOT, "logo.png")
    if os.path.exists(logo):
        run(["ffmpeg", "-y", "-i", sub, "-i", logo,
             "-filter_complex", "overlay=W-w-24:H-h-24", "-c:a", "copy", final],
            timeout=300)
    else:
        os.replace(sub, final)

    caption = content.get("caption", "")
    hashtags = " ".join(content.get("hashtags", []))
    with open(os.path.join(ROOT, "caption.txt"), "w", encoding="utf-8") as f:
        f.write((caption + "\n\n" + hashtags).strip())

    save_json(os.path.join(WORK, "render_report.json"),
              {"duration": round(D, 2), "segments": n, "clips": len(clips)})
    log("reel ready:", final, round(D, 1), "sec")


if __name__ == "__main__":
    main()
