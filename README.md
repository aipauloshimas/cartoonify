# Cartoonify

A [Claude Code](https://claude.com/claude-code) skill that turns your whole talking-head video into a cartoon:

- **your own room, redrawn by hand**: Claude looks at your video, removes you from it, and redraws the room behind
  you (your sofa, your shelf, your plant, your window) as a cartoon set, from the very first frame;
- **you stay real**, cut out with [Robust Video Matting](https://github.com/PeterL1n/RobustVideoMatting) and outlined
  with a hand-drawn marker line;
- **only the keywords** pop in as giant type (no full captions), from a transcript of every word, each one measured in
  its real font so it always fits inside the Instagram Reels safe zone;
- **doodles pop and boil**: every drawn line wobbles 8 times a second, like a hand-drawn animation;
- **10 doodle styles x 10 type styles**, or describe your own;
- **no sound added**: your voice stays exactly as recorded.

Any length, vertical or horizontal. Everything runs on your computer.

## How it works

1. You give Claude a video: "cartoonify C:\videos\take.mp4".
2. It transcribes every word, cuts you out, rebuilds the empty room and redraws it.
3. It opens a **storyboard** in your browser: pick your look at the top (each option is your own room in that style),
   then approve or change each beat, and click **Done**. Claude gets your review on its own and makes a new version
   if you asked for changes.
4. After your go, it builds the edit and opens it in the **HyperFrames player** to watch.
5. When you say "render", it renders an MP4 at the same resolution, frame rate and bitrate as your video.

## Install

Needs [Claude Code](https://claude.com/claude-code) on macOS or Windows.

macOS:
```bash
git clone https://github.com/aipauloshimas/cartoonify ~/.claude/skills/cartoonify
```

Windows (PowerShell):
```powershell
git clone https://github.com/aipauloshimas/cartoonify "$env:USERPROFILE\.claude\skills\cartoonify"
```

Then open Claude Code and say "cartoonify my video" with the path to a talking-head video, or type `/cartoonify`.

The first run checks what your computer needs with `scripts/doctor.py` and shows you what is missing before
installing anything (Homebrew on macOS, winget on Windows):

| Needs | For |
|---|---|
| ffmpeg | reading and writing video |
| Node.js 18+ and npx | the [HyperFrames](https://hyperframes.dev) CLI (the player and the render) |
| Python 3.9+ with numpy, opencv-python, onnxruntime, openai-whisper, playwright | cutout, transcript, stills |
| Playwright Chromium | the storyboard stills |
| the RVM model (about 15 MB, from the RVM GitHub release v1.0.0) | the cutout |

You can run it yourself: `python ~/.claude/skills/cartoonify/scripts/doctor.py` (add `--install` to install what is
missing; it asks first). Whisper downloads its speech model (about 460 MB) on the first transcription.

## Speed

Everything runs on the CPU. On a laptop, the cutout takes about 4 seconds per frame at its sharpest setting (a
faster, slightly softer one is offered for long videos), and the render about 30 to 50 times the video's length at
1080x1920. A 7-second test took about 15 minutes to cut out and 5 minutes to render.

## What is inside

| Path | |
|---|---|
| `SKILL.md` | the instructions Claude follows |
| `scripts/cartoonify.py` | the pipeline: init, transcribe, cutout, plate, check-room, layout, outline, storyboard, look, build, render |
| `scripts/rvm_matte.py`, `scripts/outline_layer.py` | the cutout and the marker outline |
| `scripts/doctor.py` | the prerequisite check and installer |
| `kit/cartoon.js` | the drawing kit: the prop library, the 10 doodle styles, the 10 type styles |
| `kit/fonts/` | the open fonts the type styles use |
| `storyboard/` | the storyboard page, its local review server and the Done waiter |
| `reference/` | how Claude redraws a room, the looks and how to make a custom one |
| `examples/` | two example rooms |
| `tests/` | `python -m pytest tests -q` |

## License

The code is MIT (see `LICENSE`). Third-party parts keep their own licenses:
- the fonts in `kit/fonts` are under the SIL Open Font License or the Apache License 2.0 (license files included);
- the RVM model is downloaded from the [RobustVideoMatting](https://github.com/PeterL1n/RobustVideoMatting) release
  (GPL-3.0) and is not included here;
- the HyperFrames CLI, Whisper, GSAP (loaded by the edit at render time) and Playwright are installed or loaded from
  their own sources under their own licenses.
