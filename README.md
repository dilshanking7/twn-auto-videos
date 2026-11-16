# TWN Auto Videos

100% free, zero-laptop-storage cloud pipeline jo roz Tech & World News reel
banata hai aur Instagram + Facebook + YouTube pe auto-post karta hai.
GitHub Actions (cloud) chalta hai — laptop band ya internet band ho tab bhi.

## Pipeline

1. **Content** (`scripts/content.py`) — Gemini se topic + Hinglish script + caption + hashtags + search keywords.
2. **Video engine** (`scripts/video_engine.py`) — provider ladder:
   Hugging Face (CogVideoX) -> free.ai -> Pollinations -> Pexels/Pixabay stock -> Ken Burns still.
   Koi ek rung fail ho to agle pe jaata hai; har run me `engine_report.json` likha jaata hai.
3. **Render** (`scripts/render.py`) — FFmpeg 1080x1920 + edge-tts voiceover + ASS captions + logo.
4. **Release** — final MP4 GitHub Release asset ke roop me upload hota hai (public URL).
5. **Publish** (`scripts/publish.py`) — Meta Graph API (Instagram Reels + Facebook Page)
   aur YouTube Data API (Shorts). Success signal = media id / video id.

## Image-to-video

`images/` folder me photo daalo, phir Actions -> Daily TWN Reel -> Run workflow,
`mode = image`, `image = images/aapki-photo.jpg`.

## Secrets

Repo Settings -> Secrets and variables -> Actions:

| Naam | Kya chahiye |
|---|---|
| `GEMINI_API_KEY` | script/caption generation |
| `PIXABAY_API_KEY` | stock footage fallback |
| `PEXELS_API_KEY` | extra stock footage (optional) |
| `HF_TOKEN` | AI text-to-video rung (optional, free signup) |
| `FREEAI_API_KEY` | AI video rung (optional, free signup) |
| `IG_USER_ID` | Instagram business account id |
| `IG_ACCESS_TOKEN` | long-lived token (60 din; refresh zaroori) |
| `FB_PAGE_ID` | Facebook Page id |
| `FB_PAGE_ACCESS_TOKEN` | Page access token (optional; IG token use hota hai) |
| `YT_TOKEN` | Google OAuth JSON (expire hota hai; periodic refresh) |

Secrets ke bina corresponding platform skip ho jaata hai — pipeline rukti nahi.

## Zero storage rule

Media sirf GitHub Releases/Artifacts me rehti hai. Repo me code, config aur
chhote JSON state files hote hain. `.gitignore` media ko rokta hai.
