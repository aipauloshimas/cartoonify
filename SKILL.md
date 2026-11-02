---
name: cartoonify
description: Use when someone wants their talking-head video cartoonified - the person stays real, cut out with a marker outline, in front of their own room redrawn as a hand-drawn cartoon set, with only the keywords popping in as giant type and doodles that pop and boil. Triggers on /cartoonify, "cartoonify my video", "turn my video into a cartoon", "hand-drawn background behind me", "doodle my room", or a dropped talking-head video with a cartoon/doodle request. Also in other languages, e.g. "cartooniza meu video", "transforma meu video em desenho", "caricaturiza mi video". Not for: making new footage, full captions, adding music or sound effects, or cartoon-filtering the person themself.
---

# Cartoonify

Turns a whole talking-head video, of any length, into a cartoon: from the first frame the person's real room is
replaced by the same room redrawn by hand (in one of 10 doodle styles), the person is cut out with Robust Video Matting
and gets a marker outline, and only the keywords pop in as giant type (one of 10 type styles). Every drawn line boils
(a new wobble 8 times a second). No sound is added: the original voice stays as recorded.

The plan is reviewed on a storyboard page before anything is built; the edit is reviewed in the HyperFrames player;
the render matches the upload's resolution, frame rate and bitrate.

**Runs in Claude Code only** (terminal or the desktop app's Code tab), on macOS and Windows.

## Rules

- **Talk in the user's language.** The storyboard page is in English.
- **The storyboard comes first.** Nothing is built before the user approves the storyboard (Done with every beat
  approved, or "go" in the chat). Nothing is rendered before they say "render".
- **People are cut out with RVM only** (`scripts/rvm_matte.py`). Never with u2net, rembg, `hyperframes
  remove-background` or keying: they chew hands and hair.
- **No sound**: no music, no effects. The voice stays.
- **Keywords only**: never full captions. A keyword is 1 to 3 words that carry the line; about one every 2 to 4 seconds.
- **Never change the user's video file.** Everything is written into the project folder.
- Install nothing without the user's OK (`doctor.py` asks; in Claude Code you ask in the chat, then pass `--yes`).

## Paths

`SKILL` = this folder. `CF` = `python SKILL/scripts/cartoonify.py` (`python3` on macOS when `python` is missing). `P` = the project folder (`init` prints it; default
`<video folder>/<video name>-cartoonify`). Long steps (`cutout`, `transcribe` on long videos, `render`) go in the
background (Bash `run_in_background`).

## The flow

### 0. Doctor (first run on a machine, or when a step fails with a missing tool)
`python SKILL/scripts/doctor.py`. All OK: go on. Something missing: show the user the install plan it prints (what,
from where, about how big), ask in the chat, and only on their yes run `python SKILL/scripts/doctor.py --install --yes`
(or `--only name,...`). Whisper also downloads its speech model (about 460 MB for `small`) on the first transcription:
say so before the first run.

### 1. Init
`CF init VIDEO`. Look at `P/work/contact.jpg` (six moments). Tell the user in one or two lines what you see (the room,
the framing) and the plan. Then start, in parallel:
- `CF cutout P` in the background. RVM runs on the CPU at downsample 0.75 (crisp hair and fingers on a framed talking
  head): about 4 s per frame, so 7 s of 30 fps video takes about 15 minutes and a minute about 2 hours. Say the
  estimate. For a long video offer `--downsample 0.5` (about twice as fast, slightly softer edges); 0.3 is the fastest
  and visibly soft on a close talking head;
- `CF transcribe P` (add `--language xx` if known; `--model base` for speed on long videos).

### 2. Keywords
`CF words P` prints every word with its start and end time. Write `P/keywords.json`:
```json
{"keywords": [
  {"t": 0.52, "end": 1.2, "lines": ["FOR THE LOVE", "OF GOD!"], "words": "love of God"},
  {"t": 5.2, "end": 5.95, "lines": ["ONE CLAUDE", "SKILL"], "words": "one Claude skill", "at": "top", "scale": 1.2}
]}
```
- `t` = the start of the first spoken word of the keyword, `end` = the end of its last word (the type holds a little
  longer, never into the next keyword).
- `lines`: 1 or 2 lines, short (up to about 12 letters a line), fix what Whisper misheard (it writes "clawed" for
  Claude), keep the speaker's words.
- `words`: the spoken words (they get highlighted in the storyboard's line).
- Optional: `at` = `top` | `bottom` | `left` | `right` | `[x, y, w, h]` in video pixels; `scale` (bigger or smaller).
- Pick the words a viewer should remember: the hook's punch, the product, the numbers, the payoff. Skip filler.

### 3. Redraw the room
When the cutout is done: `CF plate P` writes the empty room (`work/plate.png`, the person removed by stacking frames)
and `work/plate_grid.jpg` (a grid in video pixels). Read `reference/room-drawing.md`, look at the grid, and write
`P/room.js` with the prop library. Then `CF check-room P` and look at `work/check/compare.jpg` (the real room | your
drawing | the drawing over the room): fix positions and sizes until the big shapes line up (two or three passes).
It is a cartoon, not a tracing: the big furniture in the right place, simple shapes, nothing fussy.

### 4. Storyboard
1. Decide the recommended look for this video and write it into `P/cartoonify.json`:
   `"recommended": {"doodle": "D5", "type": "T3", "why": "One or two sentences on why, for this room and this person"}`,
   and set `"look"` to the same pick (the beats are drawn in it). Light walls keep dark clothes readable; dark styles
   (Chalkboard, Neon, Night sky) suit light clothes. The styles are listed in `reference/looks.md`.
2. `CF layout P` (where each keyword sits, in the free space around the person), then `CF storyboard P`.
3. Serve it on the first free port from 8300 (`python SKILL/storyboard/server.py P/storyboard --port N`):
   - in the Claude desktop app: add that command as a configuration in the session folder's `.claude/launch.json`
     (`"runtimeExecutable": "python"`, `"runtimeArgs": [...]`, `"port": N`) and open it with `preview_start`;
   - in the terminal: run it in the background and give the user `http://localhost:N` to open in their browser.
4. Start the waiter in the background: `python SKILL/storyboard/wait_done.py P/storyboard`. Tell the user: pick a look
   at the top (or describe their own), approve or change each beat, then click Done at the end. Then stop and wait.

The page: "Pick your look" (10 doodle styles on their own frame, 10 type styles, a free field for a custom look), the
timeline, the counter, one card per beat with its moments ("Planned edit | Original take" switch), Approve or Change
with a note, the Checks, general notes and the Done button.

### 5. Revise (each time the waiter wakes the session, or the user writes "reviewed")
Read the waiter's output (it prints the approvals, the notes and the look).
- **New look picked**: `CF look P` (copies the pick from review.json), then `CF outline P` is needed later for the
  build (the outline takes the style's ink).
- **Custom look asked for** in the free field: write `P/custom-look.js` (see `reference/looks.md`, "Custom looks"),
  `CF look P --doodle C1 --type T3` (or the custom type id).
- **Beat notes**: edit `keywords.json` (words, timing, `at`, `scale`) or `room.js`, then `CF layout P`.
- Then `CF storyboard P --bump --change "Beat 02: HERE'S HOW is bigger" ...` (one `--change` per change, in plain
  words). Changed beats come first, marked. The page shows "A new version is ready".
- Restart the waiter, stop, wait. Notes that ask for something beyond the edit get confirmed in the chat first.

### 6. Build (on go: Done with every beat approved, or "go" in the chat)
1. `CF outline P` (if the look changed since the last outline), then `CF build P`.
2. In `P/edit`: `npx hyperframes check`. Fix errors; `line_unread` on a short last keyword is fine to keep.
3. Look first: `npx hyperframes snapshot --at <a few times> --no-end -o ../work/snap` in `P/edit`, and 1:1 crops of the
   hands and the hair edges over the drawn room (the outline must hug the person, no light halo, no missing fingers).
4. Review in the HyperFrames player: run `npx hyperframes play --no-open --port <free port>` in `P/edit` in the
   background. In the Claude desktop app open its URL in the Browser pane (`preview_start` with the url); in the
   terminal give the user the URL.
5. Small fixes on the built video (a keyword's timing, size, place): edit `keywords.json`, `CF layout P`, `CF build P`.
   New or reordered keywords go back through the storyboard.

### 7. Render (only after the user says "render")
`CF render P` in the background. It renders with the HyperFrames CLI at the upload's size, the upload's frame rate and
at least its bitrate, then prints both side by side (`matches_upload`). Expect roughly 40 to 60 times the video's length
on a laptop at 1080x1920 (7 s took about 6 minutes). Give the user the file path.

## Files in a project

| File | Who writes it |
|---|---|
| `cartoonify.json` | `init` (the video's size, fps, bitrate), Claude (`recommended`), `look` |
| `keywords.json`, `room.js`, `custom-look.js` | Claude |
| `work/` | words.json, cut.webm (the RVM cutout), plate.png, plate_grid.jpg, layout.json, person.webm (cutout + outline), stills |
| `storyboard/` | storyboard.json, frames, index.html, review.json (the user's clicks) |
| `edit/` | the HyperFrames project: index.html, compositions/set.html and type.html, assets, renders |

## When something goes wrong

- A tool missing or failing to import: `doctor.py`.
- The cutout misses an arm or a hand: run `CF cutout P` again after deleting `work/cut.webm`, with `--downsample 0.5`
  for hands only in frame; the default 0.75 suits a framed talking head.
- The plate shows magenta (a part of the room never seen behind the person): draw what is most likely there.
- A keyword covers the face: give it `"at"` (another side) or a smaller `scale`, then `layout` again.
- Type unreadable on a style (light type on a light wall): pick another type style or suggest one in the chat.
