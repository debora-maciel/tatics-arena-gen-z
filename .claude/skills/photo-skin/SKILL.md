---
name: photo-skin
description: Turn a real-person photo into a Tactics Arena unit skin — face-aware crops for the shop splash and the round thumb, then re-skin an existing unit (name, emoji, ability name, pictures) in units.ts without touching its stats. Use whenever the user drops a photo in public/assets/characters/ and asks to add someone to the game.
---

# Photo skin

Replaces the by-hand routine we used for every singer and actor: crop a 3:2 splash and a square thumb centred on the face, then rewrite one unit's name, fallback emoji, ability name and picture fields. The unit's id, cost, traits and stats stay as they are, so pools, saves and balance are unaffected.

## Files

- `scripts/skin.py` — does everything. Face detection is OpenCV's YuNet (`face_detection_yunet_2023mar.onnx`, bundled); AVIF/HEIC are converted through `sips` first.
- `scripts/roster.py` — lists units; `--unskinned` shows which still have placeholder art, grouped by cost.
- `.venv/` — numpy, Pillow, opencv-python-headless. Recreate with `python3 -m venv .venv && .venv/bin/pip install numpy pillow opencv-python-headless` if missing.

Run from this folder:

```bash
cd .claude/skills/photo-skin
.venv/bin/python scripts/roster.py --unskinned
.venv/bin/python scripts/skin.py ../../../public/assets/characters/<file> --unit <id> --name "Name" --ability "Song" --emoji 🎤
```

## Workflow

1. **Find the photo.** New files land in `public/assets/characters/`. If the user only gave a name, `ls -t` that folder; the newest file is theirs.
2. **Pick the unit to replace.** Run `roster.py --unskinned`. Prefer the same cost tier the user implied ("1 star" = 1-cost, "legend" = 5-cost). Match origin/role to the person's vibe when there is a choice (a rocker on Ember Warrior, a healer-type on Support). Never add a new roster entry unless the user asks for one; the roster is balanced at 30.
3. **Name the ability** after a song, film or catchphrase of theirs; keep it two or three words.
4. **Run `skin.py`.** It prints the detected face box and the patched block. If it warns that no face was found, or the face box looks wrong for a group photo, Read `public/units/<folder>/photo.png` and re-run with a pre-cropped source, or hand-crop with `sips -c H W --cropOffset Y X`.
5. **Look at both crops** (`photo.png`, `splash.png`) with Read. The thumb should show the whole head with a little shoulder; the splash should keep the face in the upper middle and not cut the chin.
6. `npx tsc --noEmit && npm run lint`, then check the shop card and bench on the dev server.

## Rules of thumb

- **Small sources.** Below ~400 px the crops are made at native size; tell the user a larger photo would sharpen the roster view.
- **Group photos.** The script takes the largest face. If the wrong person wins, crop the source first.
- **Magazine logos** in a corner: the face-centred crops usually avoid them, but check the splash.
- **Legends deserve legends.** 5-cost slots are the rarest sightings; put the biggest names there only if the user agrees, since they'll rarely see them in play.
- One person per unit. If the user wants someone swapped out, re-run on the same unit id.
