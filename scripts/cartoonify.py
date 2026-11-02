"""Cartoonify pipeline: a talking-head video -> the person, cut out, in front of their own room redrawn as a cartoon,
with the keywords as giant type. Every step is one command; Claude runs them in the order SKILL.md gives.

  python cartoonify.py init VIDEO [--project DIR]    probe the video, make the project folder, sample frames to look at
  python cartoonify.py transcribe PROJECT [--model small]   every word with its time (Whisper) -> work/words.json
  python cartoonify.py words PROJECT                 print the transcript with times, to pick the keywords
  python cartoonify.py cutout PROJECT                RVM cutout of the person -> work/cut.webm (slow: run in background)
  python cartoonify.py plate PROJECT                 the empty room (person removed) + a coordinate grid, to redraw from
  python cartoonify.py check-room PROJECT [--style D5]   room.js drawn over the plate, side by side, to compare
  python cartoonify.py layout PROJECT                where each keyword goes (the free space around the person)
  python cartoonify.py outline PROJECT               the cutout with a marker outline in the look's ink -> work/person.webm
  python cartoonify.py storyboard PROJECT [--bump] [--change TEXT]...   stills + storyboard.json + the page
  python cartoonify.py build PROJECT                 the HyperFrames project in PROJECT/edit
  python cartoonify.py safecheck PROJECT             every keyword and its doodle inside the safe zone? (render runs it first)
  python cartoonify.py render PROJECT [--force]      render at the upload's resolution, frame rate and bitrate
  python cartoonify.py status PROJECT                what is done and what is next

PROJECT is the folder `init` made (default: <video folder>/<video name>-cartoonify)."""
import argparse, json, math, os, re, shutil, subprocess, sys, urllib.parse
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
KIT, SB_TOOLS = SKILL / "kit", SKILL / "storyboard"
NPX = shutil.which("npx.cmd") or shutil.which("npx") or "npx"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------- small helpers ----------
def run(*a, **kw):
    return subprocess.run([str(x) for x in a], check=True, **kw)


def ff(*a):
    run("ffmpeg", "-v", "error", "-y", *a)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,bit_rate,duration:format=duration,bit_rate",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    vb = int(v.get("bit_rate") or 0) or int(j["format"].get("bit_rate") or 0) - int((a or {}).get("bit_rate") or 0)
    return {"width": v["width"], "height": v["height"], "fps": round(num / den, 3), "fps_str": v["r_frame_rate"] if den != 1 else str(num),
            "bitrate": vb, "duration": float(v.get("duration") or j["format"]["duration"]),
            "audio": a["codec_name"] if a else None}


def load(project):
    p = Path(project).resolve()
    cfg = json.loads((p / "cartoonify.json").read_text(encoding="utf8"))
    return p, cfg


def save(p, cfg):
    (p / "cartoonify.json").write_text(json.dumps(cfg, indent=2), encoding="utf8")


def look(cfg):
    lk = cfg.get("look") or {}
    return lk.get("doodle", "D5"), lk.get("type", "T3")


def node_eval(js, *paths):
    """Run a bit of JS in Node with the kit (and a room.js) loaded; returns stdout."""
    pre = "const vm=require('vm');const fs=require('fs');global.window=undefined;" + "".join(
        f"vm.runInThisContext(fs.readFileSync({json.dumps(str(x))},'utf8'));" for x in [KIT / "cartoon.js", *paths])
    return subprocess.run(["node", "-e", pre + js], capture_output=True, text=True, check=True, encoding="utf8").stdout


def custom_files(p):
    f = p / "custom-look.js"
    return [f] if f.exists() else []


def tc(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


# ---------- init ----------
def cmd_init(a):
    video = Path(a.video).resolve()
    p = Path(a.project).resolve() if a.project else video.parent / f"{video.stem}-cartoonify"
    (p / "work" / "frames").mkdir(parents=True, exist_ok=True)
    info = probe(video)
    cfg = {"video": str(video), **info, "look": {"doodle": "D5", "type": "T3", "custom": ""},
           "recommended": {"doodle": "D5", "type": "T3", "why": ""}}
    if (p / "cartoonify.json").exists():
        old = json.loads((p / "cartoonify.json").read_text(encoding="utf8"))
        cfg.update({k: old[k] for k in ("look", "recommended") if k in old})
    save(p, cfg)
    # six frames across the video and a contact sheet, so Claude can look at the room and the person
    n = 6
    for i in range(n):
        t = info["duration"] * (i + 0.5) / n
        ff("-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=720:-2", "-q:v", "3", p / "work" / "frames" / f"f{i}.jpg")
    ff("-ss", "0", "-i", video, "-frames:v", "1", p / "work" / "first.png")
    ff(*sum((["-i", str(p / "work" / "frames" / f"f{i}.jpg")] for i in range(n)), []), "-filter_complex",
       "".join(f"[{i}:v]scale=360:-2[v{i}];" for i in range(n)) + "".join(f"[v{i}]" for i in range(n)) + f"hstack=inputs={n}",
       p / "work" / "contact.jpg")
    print(json.dumps({"project": str(p), **info}, indent=2))
    print(f"\nLook at {p / 'work' / 'contact.jpg'} (six moments). Next: transcribe, and cutout in the background.")


# ---------- transcribe ----------
def cmd_transcribe(a):
    p, cfg = load(a.project)
    import whisper
    model = whisper.load_model(a.model)
    r = model.transcribe(cfg["video"], word_timestamps=True, language=a.language, verbose=False)
    words = [{"w": w["word"].strip(), "s": round(w["start"], 2), "e": round(w["end"], 2)} for seg in r["segments"] for w in seg.get("words", [])]
    segs = [{"s": round(s["start"], 2), "e": round(s["end"], 2), "text": s["text"].strip()} for s in r["segments"]]
    (p / "work" / "words.json").write_text(json.dumps({"language": r.get("language"), "text": r["text"].strip(), "segments": segs, "words": words},
                                                      indent=1, ensure_ascii=False), encoding="utf8")
    print(f"{len(words)} words, {len(segs)} sentences, language {r.get('language')} -> work/words.json")


def cmd_words(a):
    p, _ = load(a.project)
    j = json.loads((p / "work" / "words.json").read_text(encoding="utf8"))
    for s in j["segments"]:
        ws = [w for w in j["words"] if s["s"] - 0.05 <= w["s"] < s["e"] + 0.05]
        print(f"[{tc(s['s'])}-{tc(s['e'])}] " + " ".join(f"{w['w']}@{w['s']:.2f}-{w['e']:.2f}" for w in ws))


# ---------- cutout ----------
def cmd_cutout(a):
    p, cfg = load(a.project)
    out = p / "work" / "cut.webm"
    run(sys.executable, SKILL / "scripts" / "rvm_matte.py", cfg["video"], out, "--downsample", str(a.downsample))
    print(f"cutout -> {out}")


def decode_alpha(cut, t, W, H):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-ss", f"{max(0, t):.3f}", "-i", str(cut), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgba", "-"], capture_output=True, check=True).stdout
    if len(raw) < W * H * 4:
        return None
    return np.frombuffer(raw[:W * H * 4], np.uint8).reshape(H, W, 4)


# ---------- plate: the empty room ----------
def cmd_plate(a):
    import cv2, numpy as np
    p, cfg = load(a.project)
    W, H, D = cfg["width"], cfg["height"], cfg["duration"]
    cut = p / "work" / "cut.webm"
    n = max(8, min(40, int(D * 2)))
    stack, masks = [], []
    for i in range(n):
        t = D * (i + 0.5) / n
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", cfg["video"], "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                             capture_output=True, check=True).stdout
        rgba = decode_alpha(cut, t, W, H)
        if len(raw) < W * H * 3 or rgba is None:
            continue
        img = np.frombuffer(raw[:W * H * 3], np.uint8).reshape(H, W, 3)
        free = cv2.erode((rgba[..., 3] < 10).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0   # well clear of the person
        stack.append(img); masks.append(free)
    S = np.stack(stack).astype(np.float32); M = np.stack(masks)
    S[~M] = np.nan
    plate = np.nanmedian(S, axis=0)
    hole = np.isnan(plate[..., 0])
    plate = np.nan_to_num(plate).clip(0, 255).astype(np.uint8)
    if hole.any():   # never seen behind the person: fill from the surroundings and mark it
        plate = cv2.inpaint(plate, hole.astype(np.uint8) * 255, 9, cv2.INPAINT_TELEA)
    cv2.imwrite(str(p / "work" / "plate.png"), plate)
    # the same plate, smaller, with a labelled grid in the video's own pixels (what room.js uses)
    s = min(1.0, 900 / H)
    small = cv2.resize(plate, (round(W * s), round(H * s)), interpolation=cv2.INTER_AREA)
    over = small.copy()
    step = 100 if max(W, H) <= 2000 else 200
    for x in range(0, W, step):
        cv2.line(over, (round(x * s), 0), (round(x * s), small.shape[0]), (0, 0, 255) if x % (step * 5) == 0 else (60, 60, 255), 1)
        if x % (step * 2) == 0:
            cv2.putText(over, str(x), (round(x * s) + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 200), 1)
    for y in range(0, H, step):
        cv2.line(over, (0, round(y * s)), (small.shape[1], round(y * s)), (0, 0, 255) if y % (step * 5) == 0 else (60, 60, 255), 1)
        if y % (step * 2) == 0:
            cv2.putText(over, str(y), (2, round(y * s) - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 200), 1)
    if hole.any():
        hs = cv2.resize(hole.astype(np.uint8), (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST)
        over[hs > 0] = (over[hs > 0] * 0.6 + np.array([255, 0, 255]) * 0.4).astype(np.uint8)
    cv2.imwrite(str(p / "work" / "plate_grid.jpg"), cv2.addWeighted(over, 0.75, small, 0.25, 0))
    # where the person usually is (union of the matte) for the head position and the doodle spots
    occ = (~M).mean(axis=0)
    ys, xs = np.where(occ > 0.5)
    person = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    cfg["person_box"] = person
    save(p, cfg)
    print(f"plate from {len(stack)} frames -> work/plate.png, work/plate_grid.jpg (grid in video pixels, magenta = never seen)")
    print(f"person usually inside x {person[0]}-{person[2]}, y {person[1]}-{person[3]}" if person else "no person found")


# ---------- room check ----------
def render_html(p, cfg):
    """One page that draws any still: the set, the cut-out person (with a marker outline), keywords, glyphs."""
    W, H = cfg["width"], cfg["height"]
    files = [KIT / "cartoon.js", *custom_files(p), p / "room.js"]
    scripts = "".join(f'<script src="{f.as_uri()}"></script>' for f in files)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{_fontcss()}
html,body{{margin:0;background:#000;overflow:hidden}}#stage{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;transform-origin:0 0;overflow:hidden}}
.L{{position:absolute;inset:0}}.L img{{width:{W}px;height:{H}px;display:block}}.kw{{position:absolute;display:flex;align-items:center;justify-content:center}}
</style></head><body><div id="stage"></div>{scripts}<script>
// every bundled font must be loaded before anything is measured (a style can mix several, like the collage)
const fontsIn = async () => {{
  await Promise.all(Object.keys(Cartoon.FONT_FILES).map(f => document.fonts.load(`${{f === "Cabin Sketch" ? "700 " : ""}}40px "${{f}}"`).catch(() => 0)));
  await document.fonts.ready;
}};
window.fontsIn = fontsIn;
window.render = async (o) => {{
  window.__ready = false;
  const s = document.getElementById('stage'), u = Math.min({W},{H})/1080, st = Cartoon.styleById(o.style);
  const sc = o.scale || 1; s.style.transform = `scale(${{sc}})`;
  document.documentElement.style.width = ({W}*sc)+'px'; document.documentElement.style.height = ({H}*sc)+'px';
  const ow = Math.max(3, Math.round(9*u)), ink = st.ink;
  const outline = o.cut ? `drop-shadow(${{ow}}px 0 0 ${{ink}}) drop-shadow(-${{ow}}px 0 0 ${{ink}}) drop-shadow(0 ${{ow}}px 0 ${{ink}}) drop-shadow(0 -${{ow}}px 0 ${{ink}}) drop-shadow(${{Math.round(16*u)}}px ${{Math.round(22*u)}}px ${{Math.round(15*u)}}px rgba(0,0,0,.3))` : '';
  let h = '';
  if (o.take) h += `<div class="L"><img src="${{o.take}}"></div>`;
  if (!o.noset) h += `<div class="L">${{Cartoon.set(Cartoon.ROOM, o.style, {{doodles: o.doodles !== false}})}}</div>`;
  if (o.cut && !o.noset) h += `<div class="L"><img src="${{o.cut}}" style="filter:${{outline}}"></div>`;
  if (o.plateOver) h += `<div class="L" style="opacity:.45"><img src="${{o.plateOver}}"></div>`;
  await fontsIn(o.type);
  for (const k of (o.keywords || [])) {{
    const [x, y, w, hh] = k.box;
    // the size measured in the real font (layout.json), or measured here for a look-picker thumb
    const size = (k.size && k.size[o.type]) || Cartoon.fitSize(o.type, k.lines, w, hh, Math.min(hh / (k.lines.length * 1.12), 260 * u) * (k.scale || 1));
    h += `<div class="kw" data-lines="${{k.lines.join(' / ')}}" style="left:${{x}}px;top:${{y}}px;width:${{w}}px;height:${{hh}}px">${{Cartoon.typeHTML(o.type, k.lines, size)}}</div>`;
    if (k.glyph) h += `<div class="L"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"><defs><filter id="cf-s"><feDropShadow dx="${{6*u}}" dy="${{8*u}}" stdDeviation="${{2*u}}" flood-opacity=".25"/></filter></defs><g class="kg" data-lines="${{k.lines.join(' / ')}}">${{Cartoon.glyph(o.style, k.glyph[3], k.glyph[0], k.glyph[1], k.glyph[2], u)}}</g></svg></div>`;
  }}
  s.innerHTML = h;
  await document.fonts.ready;
  await Promise.all([...document.images].map(i => i.decode().catch(() => 0)));
  window.__ready = true;
}};
// what leaves the safe zone in the frame drawn now: keywords (every letter, stroke included) and their doodles
window.safeReport = () => {{
  const z = Cartoon.safeZone({W}, {H}), s = document.getElementById('stage'), sc = s.getBoundingClientRect().width / {W}, out = [];
  const box = (els, pad) => {{ let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (const e of els) {{ const r = e.getBoundingClientRect(); if (!r.width || !r.height) continue;
      x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom); }}
    return [x0 / sc - pad, y0 / sc - pad, x1 / sc + pad, y1 / sc + pad].map(Math.round); }};
  const test = (what, kind, b, topMin) => {{ const sides = [];
    if (b[0] < z.x0) sides.push(`left ${{b[0]}} < ${{z.x0}}`); if (b[2] > z.x1) sides.push(`right ${{b[2]}} > ${{z.x1}}`);
    if (b[1] < topMin) sides.push(`top ${{b[1]}} < ${{topMin}}`); if (b[3] > z.y1) sides.push(`bottom ${{b[3]}} > ${{z.y1}}`);
    if (sides.length) out.push({{ what, kind, box: b, sides }}); }};
  for (const kw of s.querySelectorAll('.kw')) {{
    const t = kw.querySelector('.cf-type'), size = Math.max(0, ...[t, ...t.querySelectorAll('*')].map(e => parseFloat(getComputedStyle(e).fontSize) || 0));
    test(kw.dataset.lines, 'keyword', box([t, ...t.querySelectorAll('*')], size / 19), z.typeTop - Math.round(size / 19));
  }}
  for (const g of s.querySelectorAll('.kg')) test(g.dataset.lines, 'keyword doodle', box([g], 0), z.y0);
  return {{ zone: z, out }};
}};
</script></body></html>"""
    out = p / "work" / "render.html"
    out.write_text(page, encoding="utf8")
    return out


def _fontcss():
    return "\n".join(f'@font-face{{font-family:"{f}";src:url("{(KIT / "fonts" / file).as_uri()}");{"font-weight:700;" if f == "Cabin Sketch" else ""}font-display:block}}'
                     for f, file in FONTS.items())


FONTS = {"Anton": "Anton-Regular.ttf", "Permanent Marker": "PermanentMarker-Regular.ttf", "Luckiest Guy": "LuckiestGuy-Regular.ttf",
         "Bangers": "Bangers-Regular.ttf", "Titan One": "TitanOne-Regular.ttf", "Cabin Sketch": "CabinSketch-Bold.ttf", "Yellowtail": "Yellowtail-Regular.ttf",
         "Abril Fatface": "AbrilFatface-Regular.ttf", "Rubik Mono One": "RubikMonoOne-Regular.ttf", "Shrikhand": "Shrikhand-Regular.ttf",
         "Special Elite": "SpecialElite-Regular.ttf"}


class Shooter:
    """Playwright page on render.html; shoot(o, path, width) renders one still and saves it as JPEG/PNG."""

    def __init__(self, p, cfg):
        from playwright.sync_api import sync_playwright
        self.cfg, self.page_url = cfg, render_html(p, cfg).as_uri()
        self.pw = sync_playwright().start()
        self.b = self.pw.chromium.launch()
        self.pg = self.b.new_page(viewport={"width": 1080, "height": round(1080 * cfg["height"] / cfg["width"])})
        self.pg.goto(self.page_url)
        self.pg.on("pageerror", lambda e: print("page error:", e))

    def shoot(self, o, path, width=720):
        W, H = self.cfg["width"], self.cfg["height"]
        sc = width / W
        self.pg.set_viewport_size({"width": width, "height": round(H * sc)})
        self.pg.evaluate("o => window.render(o)", dict(o, scale=sc))
        self.pg.wait_for_function("window.__ready === true", timeout=60000)
        kw = {"type": "jpeg", "quality": 88} if str(path).endswith(".jpg") else {}
        if path:
            self.pg.screenshot(path=str(path), **kw)
        return self.pg.evaluate("window.safeReport()")

    def close(self):
        self.b.close(); self.pw.stop()


def cmd_check_room(a):
    """room.js in the chosen style beside the plate, and drawn over it at 45%, so Claude can see what is off."""
    p, cfg = load(a.project)
    if not (p / "room.js").exists():
        sys.exit("room.js is missing: write it first (reference/room-drawing.md)")
    st = a.style or look(cfg)[0]
    shots = p / "work" / "check"; shots.mkdir(exist_ok=True)
    sh = Shooter(p, cfg)
    try:
        plate = (p / "work" / "plate.png").as_uri()
        sh.shoot({"style": st, "noset": False}, shots / "room.png", 540)
        sh.shoot({"style": st, "plateOver": plate}, shots / "over.png", 540)
    finally:
        sh.close()
    ff("-i", p / "work" / "plate.png", "-i", shots / "room.png", "-i", shots / "over.png", "-filter_complex",
       "[0:v]scale=540:-2[a];[1:v]scale=540:-2[b];[2:v]scale=540:-2[c];[a][b][c]hstack=inputs=3", shots / "compare.jpg")
    print(f"-> {shots / 'compare.jpg'} (the real empty room | your drawing | the drawing over the room)")


# ---------- safe zone (the same numbers as Cartoon.safeZone in kit/cartoon.js) ----------
def safe_zone(W, H):
    """Instagram Reels safe zone for vertical video (x 60-960, y 220-1500 of 1080x1920, type from y 230), scaled to the
    frame; 5% margins for other shapes."""
    if H > W:
        return {"x0": round(W * 60 / 1080), "y0": round(H * 220 / 1920), "x1": round(W * 960 / 1080), "y1": round(H * 1500 / 1920),
                "typeTop": round(H * 230 / 1920)}
    return {"x0": round(W * 0.05), "y0": round(H * 0.05), "x1": round(W * 0.95), "y1": round(H * 0.95), "typeTop": round(H * 0.06)}


def ensure_sizes(p, cfg, type_id, sh=None):
    """Measure every keyword in its real font (stroke included) and store the size that fits its box, per type style,
    in work/layout.json. Sizes never come from the letter count."""
    lay_f = p / "work" / "layout.json"
    lay = json.loads(lay_f.read_text(encoding="utf8"))
    todo = [k for k in lay if type_id not in (k.get("size") or {})]
    if todo:
        own = sh is None
        sh = sh or Shooter(p, cfg)
        try:
            got = sh.pg.evaluate("async ([t, ks, u]) => { await window.fontsIn(t);"
                                 " return ks.map(k => Cartoon.fitSize(t, k.lines, k.box[2], k.box[3], Math.min(k.box[3] / (k.lines.length * 1.12), 260 * u) * (k.scale || 1))); }",
                                 [type_id, todo, min(cfg["width"], cfg["height"]) / 1080])
        finally:
            if own:
                sh.close()
        for k, s_ in zip(todo, got):
            k.setdefault("size", {})[type_id] = s_
        lay_f.write_text(json.dumps(lay, indent=1), encoding="utf8")
    return lay


# ---------- layout: where each keyword sits ----------
def cmd_layout(a):
    import numpy as np
    p, cfg = load(a.project)
    W, H = cfg["width"], cfg["height"]
    kws = json.loads((p / "keywords.json").read_text(encoding="utf8"))["keywords"]
    words = json.loads((p / "work" / "words.json").read_text(encoding="utf8"))["words"]
    cut = p / "work" / "cut.webm"
    gap = round(0.03 * min(W, H))
    z = safe_zone(W, H)
    zx0, zy0, zx1, zy1, top = z["x0"], z["y0"], z["x1"], z["y1"], z["typeTop"]
    zw = zx1 - zx0
    out = []
    for i, k in enumerate(kws):
        t0, t1 = timing(k, kws[i + 1] if i + 1 < len(kws) else None, cfg["duration"])
        boxes = []
        for t in (t0, (t0 + t1) / 2, t1 - 0.05):
            rgba = decode_alpha(cut, t, W, H)
            if rgba is None:
                continue
            ys, xs = np.where(rgba[..., 3] > 127)
            if len(xs):
                boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
        if boxes:
            x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
            x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        else:
            x0, y0, x1, y1 = W, H, 0, 0
        # every candidate box lies inside the safe zone, and type never starts above typeTop
        cand = {"top": (zx0, top, zw, min(y0 - gap, zy1) - top), "bottom": (zx0, max(y1 + gap, top), zw, zy1 - max(y1 + gap, top)),
                "left": (zx0, top, min(x0 - gap, zx1) - zx0, zy1 - top), "right": (max(x1 + gap, zx0), top, zx1 - max(x1 + gap, zx0), zy1 - top)}
        want = k.get("at")
        if isinstance(want, list):   # placed by hand: still clipped to the safe zone
            bx0, by0 = max(want[0], zx0), max(want[1], top)
            box, where = (bx0, by0, min(want[0] + want[2], zx1) - bx0, min(want[1] + want[3], zy1) - by0), "custom"
        else:
            ok = {n: b for n, b in cand.items() if b[2] >= 0.3 * W and b[3] >= 0.11 * H}
            where = want if want in cand and want in ok else (max(ok, key=lambda n: min(ok[n][2], ok[n][3] * 2.5) * min(ok[n][3], 0.35 * H)) if ok else "top")
            box = ok.get(where) or (zx0, top, zw, round(0.2 * H))   # nothing free: over the head, like a title
            if box[3] > 0.42 * H:   # a tall free column or band: keep the type near the top of it
                box = (box[0], box[1], box[2], round(0.36 * H))
        box = [int(v) for v in box]
        r = round(0.055 * min(W, H))
        # the keyword's doodle sits in a corner of its box, wholly inside it (so inside the safe zone)
        # (inset 1.4 r: arrows, rays and sticker borders reach past the glyph's radius)
        gx = box[0] + box[2] - 1.4 * r if i % 2 == 0 else box[0] + 1.4 * r
        out.append({"i": i, "lines": k["lines"], "scale": float(k.get("scale", 1)), "t": t0, "end": t1, "box": box, "where": where,
                    "glyph": [round(gx), round(box[1] + 1.4 * r), r, i]})
    (p / "work" / "layout.json").write_text(json.dumps(out, indent=1), encoding="utf8")
    for o in out:
        print(f"{o['t']:6.2f}-{o['end']:6.2f}  {' / '.join(o['lines']):34s} {o['where']:7s} box {o['box']}")


def timing(k, nxt, dur):
    t0 = float(k["t"])
    t1 = float(k.get("end", t0 + 1.2))
    t1 = max(t1 + 0.35, t0 + 0.9)
    if nxt:
        t1 = min(t1, float(nxt["t"]) - 0.04)
    return round(t0, 3), round(min(t1, dur), 3)


# ---------- outline layer ----------
def cmd_outline(a):
    p, cfg = load(a.project)
    ink = json.loads(node_eval(f"console.log(JSON.stringify(Cartoon.styleById({json.dumps(look(cfg)[0])}).ink))", *custom_files(p)))
    run(sys.executable, SKILL / "scripts" / "outline_layer.py", p / "work" / "cut.webm", p / "work" / "person.webm", "--ink", ink)
    cfg["outline_ink"] = ink
    save(p, cfg)


# ---------- storyboard ----------
STOP = set("a an the of to in on at for and or but is it it's its this that these those i you we he she they my your our me us "
           "just so very really be was are am do does did with from by as up out how here's".split())


def beats_from(segs, min_len=2.5):
    beats, cur = [], None
    for s in segs:
        if cur and (cur["e"] - cur["s"] < min_len):
            cur["e"], cur["text"] = s["e"], cur["text"] + " " + s["text"]
        else:
            if cur:
                beats.append(cur)
            cur = dict(s)
    if cur:
        beats.append(cur)
    return beats


def cmd_storyboard(a):
    p, cfg = load(a.project)
    W, H, D = cfg["width"], cfg["height"], cfg["duration"]
    sb_dir = p / "storyboard"; fr = sb_dir / "frames"; fr.mkdir(parents=True, exist_ok=True)
    stills = p / "work" / "stills"; stills.mkdir(exist_ok=True)
    words = json.loads((p / "work" / "words.json").read_text(encoding="utf8"))
    meta = json.loads(node_eval("console.log(JSON.stringify({d:Cartoon.STYLES.concat(Cartoon.CUSTOM).map(s=>({id:s.id,name:s.name,blurb:s.blurb})),"
                                "t:Cartoon.TYPES.concat(Cartoon.CUSTOM_TYPES).map(t=>({id:t.id,name:t.name,blurb:t.blurb}))}))", *custom_files(p)))
    dname = {d["id"]: d["name"] for d in meta["d"]}; tname = {t["id"]: t["name"] for t in meta["t"]}
    d_id, t_id = look(cfg)
    lay = ensure_sizes(p, cfg, t_id)
    old = json.loads((sb_dir / "storyboard.json").read_text(encoding="utf8")) if (sb_dir / "storyboard.json").exists() else None
    version = (old["version"] + 1) if (old and a.bump) else (old["version"] if old else 1)
    tag = f"v{version}"
    video, cut = cfg["video"], p / "work" / "cut.webm"

    def frame_pair(t, name):
        take, cutp = stills / f"{name}-take.png", stills / f"{name}-cut.png"
        if not take.exists():
            ff("-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", take)
        if not cutp.exists():
            ff("-c:v", "libvpx-vp9", "-ss", f"{t:.3f}", "-i", cut, "-frames:v", "1", "-pix_fmt", "rgba", cutp)
        return take, cutp

    beats = []
    shots = []   # (options, path)
    for bi, b in enumerate(beats_from(words["segments"])):
        bid = f"B{bi + 1:02d}"
        kin = [k for k in lay if b["s"] - 0.05 <= k["t"] < b["e"] + 0.05]
        moments, what = [], []
        for mi, k in enumerate(kin[:3]):
            t = min(k["t"] + 0.3, k["end"] - 0.05)
            name = f"{bid}-{mi + 1}"
            take, cutp = frame_pair(t, f"t{t:.2f}")
            on = [o for o in lay if o["t"] <= t < o["end"]]
            spoken = next((w["w"] for w in words["words"] if abs(w["s"] - k["t"]) < 0.12), k["lines"][0].lower())
            moments.append({"t": round(t, 2), "caption": f"On “{spoken.strip('.,!?')}”: {' '.join(k['lines'])} pops in, {k['where'] if k['where'] != 'custom' else 'placed by hand'}",
                            "plan": f"frames/{name}-plan-{tag}.jpg", "take": f"frames/{name}-orig.jpg"})
            shots.append(({"style": d_id, "type": t_id, "take": take.as_uri(), "cut": cutp.as_uri(),
                           "keywords": [{"lines": o["lines"], "box": o["box"], "glyph": o["glyph"], "scale": o.get("scale", 1), "size": o.get("size")} for o in on]}, fr / f"{name}-plan-{tag}.jpg", take, fr / f"{name}-orig.jpg", bid))
        for k in kin:
            what.append(f"{k['t']:.2f}-{k['end']:.2f} s: “{' / '.join(k['lines'])}” pops in ({k['where']}), holds, pops out; a {dname.get(d_id, d_id)} doodle springs in beside it")
        if not kin:
            t = (b["s"] + b["e"]) / 2
            name = f"{bid}-1"
            take, cutp = frame_pair(t, f"t{t:.2f}")
            moments.append({"t": round(t, 2), "caption": "No keyword here: you talk in front of your drawn room, the doodles boil",
                            "plan": f"frames/{name}-plan-{tag}.jpg", "take": f"frames/{name}-orig.jpg"})
            shots.append(({"style": d_id, "type": t_id, "take": take.as_uri(), "cut": cutp.as_uri(), "keywords": []}, fr / f"{name}-plan-{tag}.jpg", take, fr / f"{name}-orig.jpg", bid))
            what.append("No keyword in this beat: only the room and you")
        if len(kin) > 3:
            what.append(f"{len(kin) - 3} more keyword(s) in this beat are listed above but not drawn as frames")
        what.insert(0, f"Your room, redrawn as a {dname.get(d_id, d_id)} set, from the first frame; you stay real, cut out with a marker outline")
        beats.append({"id": bid, "start": round(b["s"] if bi else 0, 2), "end": round(b["e"], 2), "estimated": False, "line": b["text"],
                      "shot": {"kind": "th", "name": "Talking head", "label": "Your take, cartoonified", "source": Path(video).name},
                      "moments": moments, "what": what + ["Every drawn line boils (a new wobble 8 times a second)"],
                      "keys": sorted({w.lower().strip("!?.,'") for k in kin for w in k.get("words", " ".join(k["lines"])).split()} - STOP),
                      "sound": ["None added: Cartoonify makes no sound effects. Your voice stays as recorded."], "music": "None",
                      "ref": None, "ref_none": "No reference: the look is the one picked in “Pick your look” above", "alerts": []})
    if beats:
        beats[-1]["end"] = round(D, 2)

    # look picker thumbs: the 10 doodle styles on your own frame, the 10 type styles on the current doodle style
    t_look = lay[0]["t"] + 0.3 if lay else D / 2
    take, cutp = frame_pair(t_look, f"t{t_look:.2f}")
    sample = [{"lines": lay[0]["lines"], "box": lay[0]["box"], "glyph": lay[0]["glyph"], "size": lay[0].get("size")}] if lay else []
    for d in meta["d"]:
        shots.append(({"style": d["id"], "type": t_id, "take": take.as_uri(), "cut": cutp.as_uri(), "keywords": []}, fr / f"look-{d['id']}-{tag}.jpg", None, None, None))
    for t in meta["t"]:
        shots.append(({"style": d_id, "type": t["id"], "take": take.as_uri(), "cut": cutp.as_uri(), "keywords": sample}, fr / f"look-{t['id']}-{tag}.jpg", None, None, None))

    unsafe = {}   # beat id -> what leaves the safe zone
    sh = Shooter(p, cfg)
    try:
        for o, path, take, orig, bid in shots:
            got = sh.shoot(o, path, 720 if not path.name.startswith("look-") else 360)
            if bid:
                for v in got["out"]:
                    unsafe.setdefault(bid, []).append(f"“{v['what']}” ({v['kind']}): {', '.join(v['sides'])}")
            if take is not None and not orig.exists():
                ff("-i", take, "-vf", "scale=720:-2", "-q:v", "3", orig)
    finally:
        sh.close()
    zone = safe_zone(W, H)
    for b in beats:
        if b["id"] in unsafe:
            b["alerts"].append(f"Leaves the safe zone (x {zone['x0']}-{zone['x1']}, y {zone['y0']}-{zone['y1']})")
            b["what"].extend(f"Safe zone: {u_}" for u_ in unsafe[b["id"]])

    rec = cfg.get("recommended") or {}
    changes = list(a.change or [])
    if old and a.bump:
        ol = (old.get("look") or {}).get("current") or {}
        if (ol.get("doodle"), ol.get("type")) != (d_id, t_id):
            changes.insert(0, f"New look: {dname.get(d_id, d_id)} + {tname.get(t_id, t_id)} (was {dname.get(ol.get('doodle'), ol.get('doodle'))} + {tname.get(ol.get('type'), ol.get('type'))})")
    sb = {"project": Path(video).stem, "title": words["segments"][0]["text"] if words["segments"] else "Cartoonify",
          "meta": f"{len(beats)} beats · {len(lay)} keywords · look: {dname.get(d_id, d_id)} + {tname.get(t_id, t_id)} · no sound added · "
                  + (f"safe zone: {sum(len(v) for v in unsafe.values())} problem(s), see Checks" if unsafe else "safe zone checked: every keyword inside"),
          "kinds": {"th": "you, cartoonified"}, "version": version, "length": round(D, 2), "changes": changes, "needs": [], "music": [],
          "look": {"intro": f"Each option is your own room, redrawn, at {tc(t_look)}. Text styles are shown on the doodle style the beats use now.",
                   "doodles": [dict(d, thumb=f"frames/look-{d['id']}-{tag}.jpg") for d in meta["d"]],
                   "types": [dict(t, thumb=f"frames/look-{t['id']}-{tag}.jpg") for t in meta["t"]],
                   "recommended": {"doodle": rec.get("doodle", d_id), "type": rec.get("type", t_id), "why": rec.get("why", "")},
                   "current": {"doodle": d_id, "type": t_id, "custom": (cfg.get("look") or {}).get("custom", "")}},
          "beats": beats}
    if old and a.bump:   # mark what changed since the last version (the page puts those beats first)
        prev = {b["id"]: b for b in old["beats"]}
        look_changed = bool(changes) and changes[0].startswith("New look")
        for b in beats:
            ob = prev.get(b["id"])
            if look_changed or not ob or [m["caption"] for m in ob["moments"]] != [m["caption"] for m in b["moments"]] or ob["what"] != b["what"] or \
                    any(b["id"] in c or f"beat {int(b['id'][1:]):02d}" in c.lower() for c in a.change or []):
                sb.setdefault("changed_ids", []).append(b["id"])
    (sb_dir / "storyboard.json").write_text(json.dumps(sb, indent=1, ensure_ascii=False), encoding="utf8")
    run(sys.executable, SB_TOOLS / "build.py", sb_dir)
    print(f"storyboard v{version}: {len(beats)} beats -> {sb_dir / 'index.html'}")


# ---------- build the HyperFrames edit ----------
def bake_set(svg, W, H, out):
    """The room (doodles left out) as four PNGs, one per wobble state of its line filter (seeds 3 to 6)."""
    from playwright.sync_api import sync_playwright
    head = f"<!doctype html><html><head><meta charset='utf-8'><style>{_fontcss()} html,body{{margin:0;background:#000;overflow:hidden}}</style></head><body>"
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for i in range(4):
            # only the wobble's own turbulence changes seed; the chalk grain (seed 8) stays put
            v = re.sub(r'(<filter id="cf-w"[^>]*><feTurbulence[^>]*?seed=")3(")', rf"\g<1>{3 + i}\g<2>", svg, count=1)
            pg.set_content(head + v + "</body></html>")
            pg.evaluate("document.fonts.ready")
            pg.screenshot(path=str(out / f"set-{i}.png"))
        b.close()



def cmd_build(a):
    p, cfg = load(a.project)
    W, H, D = cfg["width"], cfg["height"], round(cfg["duration"], 3)
    d_id, t_id = look(cfg)
    e = p / "edit"; (e / "compositions").mkdir(parents=True, exist_ok=True); (e / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    for f, file in FONTS.items():
        shutil.copy(KIT / "fonts" / file, e / "assets" / "fonts" / file)
    src = p / "work" / "person.webm"
    if not src.exists():
        sys.exit(f"missing {src}: run cutout and outline first")
    shutil.copy(src, e / "assets" / "person.webm")
    if cfg.get("audio"):
        ff("-i", cfg["video"], "-vn", "-c:a", "copy" if cfg["audio"] == "aac" else "aac", *([] if cfg["audio"] == "aac" else ["-b:a", "256k"]), e / "assets" / "voice.m4a")
    lay = ensure_sizes(p, cfg, t_id)
    data = json.loads(node_eval(f"""
const u = Math.min({W},{H})/1080, L = {json.dumps(lay)};
const set = Cartoon.set(Cartoon.ROOM, {json.dumps(d_id)}, {{ doodles: false }}), doodles = Cartoon.set(Cartoon.ROOM, {json.dumps(d_id)}, {{ only: "doodles" }});
const kws = L.map(k => {{ const size = k.size[{json.dumps(t_id)}];   // measured in the real font by ensure_sizes
  return {{ html: Cartoon.typeHTML({json.dumps(t_id)}, k.lines, size), glyph: Cartoon.glyph({json.dumps(d_id)}, k.glyph[3], k.glyph[0], k.glyph[1], k.glyph[2], u).replace(/url\\(#cf-s\\)/g,'url(#ty-s)') }}; }});
console.log(JSON.stringify({{ set, doodles, kws, spots: (Cartoon.ROOM.spots||[]).length }}));""", *custom_files(p), p / "room.js"))
    bake_set(data["set"], W, H, e / "assets")
    u = min(W, H) / 1080
    boil_steps = math.ceil(D * 8) + 1
    # the set: drawn from frame 1; its doodles spring in over the first second, then bounce on the keywords
    near = []
    spots = json.loads(node_eval("console.log(JSON.stringify(Cartoon.ROOM.spots||[]))", p / "room.js")) if data["spots"] else []
    for k in lay:
        gx, gy = k["glyph"][0], k["glyph"][1]
        if spots:
            j = min(range(len(spots)), key=lambda s: (spots[s][0] - gx) ** 2 + (spots[s][1] - gy) ** 2)
            near.append((k["t"], j))
    set_html = f"""<template>
  <style>
    #cf-root {{ position: absolute; inset: 0; }}
    #cf-root > img, #cf-root > svg {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    .cf-b, .cf-doodle {{ visibility: hidden; }}
  </style>
  <div id="cf-root" data-composition-id="set" data-width="{W}" data-height="{H}">
    <!-- the room in its four wobble states, drawn once (a live line filter over the whole frame doubles the render time) -->
{chr(10).join(f'    <img id="cf-b{i}" class="cf-b" src="assets/set-{i}.png" alt=""' + (' style="visibility: visible"' if i == 0 else '') + '>' for i in range(4))}
    <!-- the doodles stay live: they pop, and each boils through its own small filter -->
    {data['doodles']}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    // every drawn line boils: a new wobble 8 times a second, from the first frame
    // state 0 is the page's own (a set at exactly 0 s would not draw frame 0), so the swaps start at the second state
    for (let i = 1; i < {boil_steps}; i++) {{
      tl.set(".cf-b", {{ visibility: "hidden" }}, i * 0.125);
      tl.set(`#cf-b${{i % 4}}`, {{ visibility: "visible" }}, i * 0.125);
      tl.set("#cf-w feTurbulence", {{ attr: {{ seed: 3 + (i % 4) }} }}, i * 0.125);
    }}
    // the doodles spring in one by one over the first second (the room itself is there from frame 1)
    // the origin is set with scale 0 (smoothOrigin off), so a pop never slides a doodle away from its place
    gsap.utils.toArray("#cf-doodles .cf-doodle").forEach((g, i) => {{
      tl.fromTo(g, {{ scale: 0, autoAlpha: 0, svgOrigin: `${{g.dataset.x}} ${{g.dataset.y}}` }}, {{ scale: 1, autoAlpha: 1, duration: 0.3, ease: "back.out(3)" }}, 0.15 + i * 0.09);
    }});
    // on each keyword the nearest doodle bounces
    {chr(10).join(f'    tl.to("#cf-d{j}", {{ scale: 1.3, duration: 0.12, ease: "power2.out", yoyo: true, repeat: 1 }}, {max(t, 0.15 + j * 0.09 + 0.35):.3f});' for t, j in near)}
    window.__timelines["set"] = tl;
  </script>
</template>
"""
    kw_divs = "\n".join(f'    <div class="ty-kw" id="ty-k{i}" style="left:{k["box"][0]}px;top:{k["box"][1]}px;width:{k["box"][2]}px;height:{k["box"][3]}px">{d["html"]}</div>'
                        for i, (k, d) in enumerate(zip(lay, data["kws"])))
    glyphs = "".join(f'<g class="ty-g" id="ty-g{i}"><g filter="url(#ty-gw)">{d["glyph"]}</g></g>' for i, d in enumerate(data["kws"]))
    anim = "\n".join(
        f'    pop("#ty-k{i}", {max(0.0, k["t"] - 0.04):.3f}, {k["end"]:.3f}); glyph("#ty-g{i}", {k["glyph"][0]}, {k["glyph"][1]}, {max(0.0, k["t"] + 0.06):.3f}, {k["end"]:.3f});'
        for i, k in enumerate(lay))
    font_css = "\n    ".join(f'@font-face {{ font-family: "{f}"; src: url("assets/fonts/{file}"); {"font-weight: 700; " if f == "Cabin Sketch" else ""}}}' for f, file in FONTS.items())
    type_html = f"""<template>
  <style>
    {font_css}
    #ty-root {{ position: absolute; inset: 0; }}
    #ty-root > svg {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    .ty-kw {{ position: absolute; display: flex; align-items: center; justify-content: center; opacity: 0; visibility: hidden; filter: url(#ty-w); }}
    .ty-g {{ opacity: 0; visibility: hidden; }}
  </style>
  <div id="ty-root" data-composition-id="type" data-width="{W}" data-height="{H}">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
      <defs>
        <filter id="ty-w" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency="{round(0.02 / u, 4)}" numOctaves="2" seed="3" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="{round(4 * u, 1)}" xChannelSelector="R" yChannelSelector="G"/></filter>
        <filter id="ty-gw" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency="{round(0.02 / u, 4)}" numOctaves="2" seed="3" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="{round(8 * u, 1)}" xChannelSelector="R" yChannelSelector="G"/></filter>
        <filter id="ty-s" x="-10%" y="-10%" width="120%" height="120%"><feDropShadow dx="{round(6 * u, 1)}" dy="{round(8 * u, 1)}" stdDeviation="{round(2 * u, 1)}" flood-opacity=".25"/></filter>
      </defs>
      {glyphs}
    </svg>
{kw_divs}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    // the type and its doodles boil with the room (8 wobbles a second)
    for (let i = 0; i < {boil_steps}; i++) tl.set("#ty-w feTurbulence, #ty-gw feTurbulence", {{ attr: {{ seed: 3 + (i % 4) }} }}, i * 0.125);
    // a keyword pops in on its word, holds, and pops out
    const pop = (sel, at, end) => {{
      tl.fromTo(sel, {{ scale: 0.2, autoAlpha: 0, rotation: -4 }}, {{ scale: 1, autoAlpha: 1, rotation: 0, duration: 0.28, ease: "back.out(2.4)" }}, at);
      tl.to(sel, {{ scale: 0.6, autoAlpha: 0, duration: 0.14, ease: "back.in(2)" }}, Math.max(at + 0.32, end - 0.14));
    }};
    const glyph = (sel, x, y, at, end) => {{
      tl.set(sel, {{ svgOrigin: `${{x}} ${{y}}` }}, 0);
      tl.fromTo(sel, {{ scale: 0, autoAlpha: 0, rotation: -25 }}, {{ scale: 1, autoAlpha: 1, rotation: 0, duration: 0.3, ease: "back.out(3)" }}, at);
      tl.to(sel, {{ scale: 0, autoAlpha: 0, duration: 0.12, ease: "power1.in" }}, Math.max(at + 0.32, end - 0.12));
    }};
{anim}
    window.__timelines["type"] = tl;
  </script>
</template>
"""
    (e / "compositions" / "set.html").write_text(set_html, encoding="utf8")
    (e / "compositions" / "type.html").write_text(type_html, encoding="utf8")
    voice = (f'    <audio id="voice" class="clip" data-label="Your voice" src="assets/voice.m4a" data-start="0" data-media-start="0" data-duration="{D}" data-track-index="5" data-volume="1"></audio>\n'
             if cfg.get("audio") else "")
    index = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{Path(cfg['video']).stem} · Cartoonify</title>
  <style>
    html, body {{ margin: 0; background: #000; }}
    #main {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; }}
    .full {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
    #set {{ position: absolute; inset: 0; z-index: 1; }}
    #person-wrap {{ position: absolute; inset: 0; z-index: 2; }}
    #type {{ position: absolute; inset: 0; z-index: 3; }}
  </style>
</head>
<body>
  <div id="main" data-composition-id="main" data-start="0" data-duration="{D}" data-width="{W}" data-height="{H}" data-fps="{cfg['fps_str']}">
    <!-- the room, redrawn as a cartoon ({d_id}), from the first frame -->
    <div id="set" data-label="Drawn room" data-composition-id="set" data-composition-src="compositions/set.html" data-start="0" data-duration="{D}"
         data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
    <!-- the person, cut out with RVM, with the marker outline and a soft shadow baked in; always in front of the room -->
    <div id="person-wrap">
      <video id="person" class="clip full" data-label="You, cut out" src="assets/person.webm" data-start="0" data-media-start="0" data-duration="{D}"
             data-track-index="2" muted playsinline></video>
    </div>
    <!-- the keywords as giant type ({t_id}) and their doodles -->
    <div id="type" data-label="Keywords" data-composition-id="type" data-composition-src="compositions/type.html" data-start="0" data-duration="{D}"
         data-track-index="3" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
    <!-- the original voice, nothing added -->
{voice}  </div>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    window.__timelines["main"] = gsap.timeline({{ paused: true }});
  </script>
</body>
</html>
"""
    (e / "index.html").write_text(index, encoding="utf8")
    print(f"edit -> {e} ({W}x{H}, {cfg['fps_str']} fps, {D} s, look {d_id} + {t_id}, {len(lay)} keywords)")
    print(f"check:  {NPX} hyperframes check  (in {e})\nreview: {NPX} hyperframes play  (in {e}), the HyperFrames player")


# ---------- safe-zone check (the lint step before a render) ----------
def safecheck(p, cfg):
    """Draw every keyword moment exactly as the edit lays it out and list what leaves the safe zone: keywords (every
    letter, stroke included) and their doodles fail; wall doodles outside it only warn. Returns (failures, warnings)."""
    d_id, t_id = look(cfg)
    z = safe_zone(cfg["width"], cfg["height"])
    sh = Shooter(p, cfg)
    fails = []
    try:
        lay = ensure_sizes(p, cfg, t_id, sh)
        for k in lay:
            t = (k["t"] + k["end"]) / 2
            on = [o for o in lay if o["t"] <= t < o["end"]]
            r = sh.shoot({"style": d_id, "type": t_id, "noset": True, "keywords": [{"lines": o["lines"], "box": o["box"], "glyph": o["glyph"],
                          "scale": o.get("scale", 1), "size": o.get("size")} for o in on]}, None, 540)
            fails += [f"{t:6.2f}s  “{v['what']}” {v['kind']}: {', '.join(v['sides'])}" for v in r["out"]]
    finally:
        sh.close()
    spots = json.loads(node_eval("console.log(JSON.stringify(Cartoon.ROOM.spots||[]))", p / "room.js")) if (p / "room.js").exists() else []
    warns = [f"wall doodle {i} at ({x}, {y}) r {r_} reaches outside the safe zone" for i, (x, y, r_) in enumerate(spots)
             if x - r_ < z["x0"] or x + r_ > z["x1"] or y - r_ < z["y0"] or y + r_ > z["y1"]]
    return sorted(set(fails)), warns


def cmd_safecheck(a):
    p, cfg = load(a.project)
    z = safe_zone(cfg["width"], cfg["height"])
    fails, warns = safecheck(p, cfg)
    print(f"safe zone x {z['x0']}-{z['x1']}, y {z['y0']}-{z['y1']} (type from y {z['typeTop']})")
    for w in warns:
        print("warn ", w)
    for f_ in fails:
        print("FAIL ", f_)
    print("OK: every keyword and its doodle is inside" if not fails else
          f"{len(fails)} problem(s): give the keyword a smaller scale or another \"at\", then layout and build")
    sys.exit(1 if fails else 0)


# ---------- render ----------
def cmd_render(a):
    p, cfg = load(a.project)
    fails, warns = safecheck(p, cfg)
    for w in warns:
        print("safe zone warn:", w)
    if fails and not a.force:
        sys.exit("safe zone: not rendering, these leave it:\n  " + "\n  ".join(fails) + "\n(fix them, or render anyway with --force)")
    e = p / "edit"; (e / "renders").mkdir(exist_ok=True)
    mbps = max(1, math.ceil(cfg["bitrate"] / 1e6)) if cfg.get("bitrate") else 20
    out = e / "renders" / f"{Path(cfg['video']).stem}-cartoonify.mp4"
    cmd = [NPX, "hyperframes", "render", ".", "--fps", cfg["fps_str"], "--video-bitrate", f"{mbps}M", "-o", str(out)]
    print("render:", " ".join(cmd[1:]), f"  ({cfg['width']}x{cfg['height']}, same as the upload)")
    subprocess.run(cmd, cwd=e, check=True)
    got = probe(out)
    ok = got["width"] == cfg["width"] and got["height"] == cfg["height"] and abs(got["fps"] - cfg["fps"]) < 0.01
    print(json.dumps({"output": str(out), "upload": {k: cfg[k] for k in ("width", "height", "fps", "bitrate")},
                      "render": {k: got[k] for k in ("width", "height", "fps", "bitrate")}, "matches_upload": ok}, indent=1))


# ---------- look: apply the pick saved on the storyboard page ----------
def cmd_look(a):
    p, cfg = load(a.project)
    lk = dict(cfg.get("look") or {})
    if a.doodle or a.type:
        lk.update({k: v for k, v in (("doodle", a.doodle), ("type", a.type)) if v})
    else:
        rv = p / "storyboard" / "review.json"
        picked = (json.loads(rv.read_text(encoding="utf8")).get("look") if rv.exists() else None) or {}
        lk.update({k: picked[k] for k in ("doodle", "type", "custom") if picked.get(k) is not None})
    changed = (lk.get("doodle"), lk.get("type")) != look(cfg)
    cfg["look"] = lk
    save(p, cfg)
    print(f"look: {lk.get('doodle')} + {lk.get('type')}" + (f", custom request: {lk['custom']!r}" if lk.get("custom") else "")
          + (" (changed: run outline again, then storyboard --bump)" if changed else " (unchanged)"))


# ---------- status ----------
def cmd_status(a):
    p, cfg = load(a.project)
    steps = [("init", p / "cartoonify.json"), ("transcribe", p / "work" / "words.json"), ("cutout", p / "work" / "cut.webm"),
             ("plate", p / "work" / "plate.png"), ("room.js (Claude draws it)", p / "room.js"), ("keywords.json (Claude picks them)", p / "keywords.json"),
             ("layout", p / "work" / "layout.json"), ("storyboard", p / "storyboard" / "index.html"), ("outline", p / "work" / "person.webm"),
             ("build", p / "edit" / "index.html")]
    for name, f in steps:
        print(f"{'done' if f.exists() else '....'}  {name}")
    print("look:", look(cfg))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("video"); s.add_argument("--project")
    s = sub.add_parser("transcribe"); s.add_argument("project"); s.add_argument("--model", default="small"); s.add_argument("--language", default=None)
    for n in ("words", "plate", "layout", "outline", "build", "safecheck", "status"):
        sub.add_parser(n).add_argument("project")
    s = sub.add_parser("render"); s.add_argument("project"); s.add_argument("--force", action="store_true", help="render even if something leaves the safe zone")
    s = sub.add_parser("cutout"); s.add_argument("project"); s.add_argument("--downsample", type=float, default=0.75)
    s = sub.add_parser("look"); s.add_argument("project"); s.add_argument("--doodle"); s.add_argument("--type")
    s = sub.add_parser("check-room"); s.add_argument("project"); s.add_argument("--style")
    s = sub.add_parser("storyboard"); s.add_argument("project"); s.add_argument("--bump", action="store_true"); s.add_argument("--change", action="append")
    a = ap.parse_args()
    globals()["cmd_" + a.cmd.replace("-", "_")](a)


if __name__ == "__main__":
    main()
