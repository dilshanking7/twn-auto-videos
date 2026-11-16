# Image-to-video mode

Jab tum apni image se video banana chaaho to workflow ko dispatch karo
`mode = image` aur `image` me ya to repo me `images/` folder me daalo
(ya phir image ka public URL do).

Flow:
1. GitHub repo -> Actions -> "Daily TWN Reel" -> Run workflow.
2. `mode` = `image`, `image` = `images/meri-photo.jpg` (ya URL).
3. Workflow AI se video banake IG + FB + YT pe post kar dega.

Folder me abhi koi image nahi daala gaya, isliye ye workflow scheduled
(run-only) ko chhedta nahi.
