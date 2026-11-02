"""Build a storyboard page from storyboard.json (prototype of the /storyboard skill).

    python build.py <storyboard folder>

Writes <folder>/index.html and copies static/page.css and static/review.js next to it. Refuses, with the list of
problems, when a beat has no frame, no "what", no "sound" or "music" key, or when two beats share an id.
The page is in English.

Versions (2026-10-22): a moment may carry "option": "A" (one capital letter, A to Z). A beat offers versions when its
moments name two or more distinct letters; the versions are those letters in order of first appearance, and its card
shows one Approve per version (Approve A, Approve B...), a letter on each frame and "or" between the versions. A beat
with no "option" keys is a one-version beat and renders exactly as before. versions(b) is the one helper that says
which letters a beat offers: server.py and wait_done.py import it too. Also refused: some moments naming a version and
some not, an "option" that is not one capital letter, a single letter, and the moments of one version not sitting
together.

Pick your look (optional): an optional "look" key in storyboard.json adds a "Pick your look" section between the
timeline and the beat cards (doodle styles, text styles, a recommendation, a free-text box, Save look). Without the key
the page is byte-identical to what it always was. look_pending() says whether a saved pick differs from "current".

Look (2026-10-17): a director's storyboard sheet. Paper by default, a darkroom variant for dark mode (and a toggle);
the planned frame is the hero; Approve leaves a stamp, Change opens a sticky note; keyboard: A, C, J/K.
"""
import html
import json
import re
import shutil
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ICON_OK = ('<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5l3.6 3.6 7.4-8.2" fill="none" '
           'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')
ICON_CHG = ('<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M13.6 3.6l2.8 2.8-8.9 8.9-3.6.8.8-3.6z" '
            'fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/></svg>')


def esc(s):
    return html.escape(str(s), quote=True)


def tc(t):
    m, s = divmod(float(t), 60)
    return f"{int(m)}:{s:04.1f}"


def dur(t):
    return f"{float(t):.1f} s"


def marked(line, keys):
    out = esc(line)
    for k in keys:
        out = re.sub(rf"(?<!\w)({re.escape(esc(k))})(?!\w)", r"<mark>\1</mark>", out, flags=re.I)
    return out


def is_letter(o):
    return isinstance(o, str) and re.fullmatch(r"[A-Z]", o) is not None


def versions(b):
    """The versions a beat offers: the distinct capital letters of its moments' "option", in order of first appearance.
    [] when there are fewer than two: a beat with no "option" keys is a one-version beat, exactly as before."""
    letters = []
    for m in b.get("moments") or []:
        o = m.get("option") if isinstance(m, dict) else None
        if is_letter(o) and o not in letters:
            letters.append(o)
    return letters if len(letters) > 1 else []


def or_list(letters):
    """["A", "B", "C"] -> "A, B or C"; ["A", "B"] -> "A or B"."""
    return " or ".join([", ".join(letters[:-1]), letters[-1]] if len(letters) > 1 else letters)


def version_problems(b):
    """What is wrong with a beat's "option" keys, one layer at a time: first how the moments are named, then what the
    letters mean. [] for a beat with no "option" key at all."""
    bid = b.get("id", "?")
    moments = b.get("moments") or []
    named = [m for m in moments if "option" in m]
    if not named:
        return []
    problems = []
    if len(named) < len(moments):
        problems.append(f'{bid}: every moment of a beat with versions names its version ("option": "A")')
    if not all(is_letter(m["option"]) for m in named):
        problems.append(f'{bid}: "option" is one capital letter (A, B, C...)')
    if problems:
        return problems
    letters = list(dict.fromkeys(m["option"] for m in moments))
    if len(letters) == 1:
        return [f'{bid}: only one version ({letters[0]}): drop "option" or add the other versions']
    for letter in letters:
        at = [i for i, m in enumerate(moments) if m["option"] == letter]
        if at[-1] - at[0] + 1 != len(at):
            problems.append(f"{bid}: the moments of version {letter} sit together")
    return problems


def look_problems(sb, folder=None):
    """What is wrong with the optional "look" key. [] when there is none. folder: where the thumbs are looked for."""
    look = sb.get("look")
    if look is None:
        return []
    if not isinstance(look, dict):
        return ["look: must be an object"]
    problems, ids = [], {}
    for key, kind in (("doodles", "doodle"), ("types", "type")):
        items = look.get(key)
        if not isinstance(items, list) or len(items) < 2:
            problems.append(f"look: needs at least two {key}")
            ids[key] = []
            continue
        seen = set()
        for it in items:
            if not isinstance(it, dict) or not it.get("id") or not it.get("name"):
                problems.append(f"look: every {kind} needs an id and a name")
                continue
            if it["id"] in seen:
                problems.append(f"look: repeated {kind} id {it['id']}")
            seen.add(it["id"])
            if not it.get("thumb"):
                problems.append(f"look: {it['id']} has no thumb")
            elif folder is not None and not (Path(folder) / it["thumb"]).is_file():
                problems.append(f"look: {it['id']} thumb file is missing ({it['thumb']})")
        ids[key] = sorted(seen)
    for key in ("recommended", "current"):
        sel = look.get(key)
        if sel is None and key == "recommended":
            continue
        if not isinstance(sel, dict):
            problems.append(f"look: needs '{key}'")
            continue
        if sel.get("doodle") not in ids["doodles"]:
            problems.append(f"look: {key} doodle {sel.get('doodle')!r} is not in doodles")
        if sel.get("type") not in ids["types"]:
            problems.append(f"look: {key} type {sel.get('type')!r} is not in types")
    return problems


def look_pending(saved, current):
    """True when a saved look pick needs a redraw: another doodle or type than the beats show now, or a custom request
    (non-empty) that differs from the one the beats were drawn with. saved None: nothing picked, nothing pending."""
    if not saved:
        return False
    custom = str(saved.get("custom") or "").strip()
    return (saved.get("doodle") != current.get("doodle") or saved.get("type") != current.get("type")
            or (custom != "" and custom != str(current.get("custom") or "").strip()))


def look_name(look, kind, lid):
    """'D5 Cozy loft' for a doodle or type id (the bare id when the list no longer holds it)."""
    for it in look.get("doodles" if kind == "doodle" else "types", []):
        if it.get("id") == lid:
            return f"{lid} {it.get('name', '')}".strip()
    return str(lid)


def check(sb, folder=None):
    problems, seen = [], set()
    for b in sb["beats"]:
        bid = b.get("id", "?")
        if bid in seen:
            problems.append(f"{bid}: repeated id")
        seen.add(bid)
        if not b.get("moments"):
            problems.append(f"{bid}: no moment (each needs a planned frame, the original take and a caption)")
        for m in b.get("moments", []):
            if not (m.get("plan") and m.get("take") and m.get("caption")):
                problems.append(f"{bid}: a moment without its planned frame, original take or caption")
        problems += version_problems(b)
        if not b.get("what"):
            problems.append(f"{bid}: no 'what' (what happens on screen)")
        for key in ("sound", "music"):
            if key not in b:
                problems.append(f"{bid}: no '{key}'")
    return problems + look_problems(sb, folder)


def sequence(b):
    """The beat as a small storyboard: numbered moments in order, each captioned with what happens on its word.
    Each frame holds the planned edit and the original take of the same instant; the view switch shows one or the other.
    A beat that offers versions shows the version's letter on each frame instead of the step number, and "or" between
    two versions where a beat has the arrow between two moments. Its Approved stamp sits on each version's first frame
    ("Approved B"), so the stamp lands on the version picked and never on another one."""
    ms = b["moments"]
    n = len(ms)
    opts = versions(b)
    parts = []
    for i, m in enumerate(ms, 1):
        stamp = ""
        if opts:
            letter = esc(m["option"])
            step = f'<span class="mo-step mo-opt">{letter}</span>'
            attr = f' data-opt="{letter}"'
            when = f"Version {letter} · {tc(m['t'])}"
            if i == 1 or ms[i - 2]["option"] != m["option"]:
                stamp = f'<span class="stamp stamp-ok">Approved {letter}</span>'
        else:
            step = f'<span class="mo-step">{i}</span>' if n > 1 else ""
            attr = ""
            when = tc(m["t"])
        parts.append(
            f'<figure class="mo" data-i="{i - 1}"{attr}><div class="mo-frame">'
            f'<img class="mo-plan" src="{esc(m["plan"])}" alt="Planned edit at {tc(m["t"])}">'
            f'<img class="mo-take" src="{esc(m["take"])}" alt="Original take at {tc(m["t"])}" loading="lazy">'
            f'{step}<span class="mo-tag">Original take</span></div>'
            f'<figcaption><span class="mo-tc">{when}</span>{esc(m["caption"])}</figcaption>{stamp}</figure>')
        if i < n:
            if opts and ms[i]["option"] != m["option"]:
                parts.append('<span class="mo-or" aria-hidden="true">or</span>')
            else:
                parts.append('<span class="mo-arrow" aria-hidden="true">→</span>')
    ok_stamp = "" if opts else '<span class="stamp stamp-ok">Approved</span>'
    return (f'<div class="seq seq-{min(n, 3)}{" seq-opts" if opts else ""}">{"".join(parts)}'
            f'{ok_stamp}<span class="stamp stamp-chg">Change</span></div>'
            f'<div class="view" role="group" aria-label="Show"><button type="button" data-v="plan" class="is-on">'
            f'Planned edit</button><button type="button" data-v="take">Original take</button></div>')


def numbers(sb):
    """Beat ids stay internal (L04B...); the page shows each beat's place: 01, 02..."""
    return {b["id"]: f"{i:02d}" for i, b in enumerate(sb["beats"], 1)}


def filmstrip(sb):
    total = float(sb["length"])
    segs = "".join(
        f'<a class="seg" href="#b-{esc(b["id"])}" data-beat="{esc(b["id"])}" '
        f'style="flex:{float(b["end"]) - float(b["start"]):.2f} 1 0" title="{i:02d} · {tc(b["start"])}">'
        f'<span>{i:02d}</span></a>'
        for i, b in enumerate(sb["beats"], 1))
    ticks = "".join(f'<i class="mtick" style="left:{float(m["t"]) / total * 100:.2f}%" title="{tc(m["t"])} {esc(m["what"])}"></i>'
                    for m in sb.get("music", []))
    return f'<nav class="film" aria-label="Beats">{segs}{ticks}</nav>'


def timeline(sb):
    total = float(sb["length"])
    blocks = "".join(
        f'<a class="tl-blk k-{esc(b["shot"]["kind"])}" href="#b-{esc(b["id"])}" data-beat="{esc(b["id"])}" '
        f'style="flex:{float(b["end"]) - float(b["start"]):.2f} 1 0">'
        f'<b>{i:02d}</b><em>{esc(b["shot"]["name"])}</em></a>'
        for i, b in enumerate(sb["beats"], 1))
    marks = "".join(f'<span class="tl-mark" style="left:{float(m["t"]) / total * 100:.2f}%"><i></i>'
                    f'<em>{tc(m["t"])} · {esc(m["what"])}</em></span>' for m in sb.get("music", []))
    legend = "".join(f'<span><i class="sw k-{esc(k)}"></i>{esc(v)}</span>' for k, v in sb.get("kinds", {}).items())
    return (f'<section class="timeline" aria-label="Timeline"><div class="label-row"><h2>Timeline</h2>'
            f'<div class="legend">{legend}<span><i class="sw sw-music"></i>music</span></div></div>'
            f'<div class="tl-track">{blocks}</div><div class="tl-marks">{marks}</div></section>')


def checks_panel(sb):
    groups = OrderedDict()
    for i, b in enumerate(sb["beats"], 1):
        for a in b.get("alerts", []):
            groups.setdefault(a, []).append((i, b["id"]))
    if not groups:
        return '<div class="panel"><h2>Checks</h2><p class="quiet">Every beat passes your rules.</p></div>'
    items = "".join(
        f'<li><span>{esc(a)}</span><span class="jumps">'
        + "".join(f'<a href="#b-{esc(bid)}">{i:02d}</a>' for i, bid in beats) + "</span></li>"
        for a, beats in groups.items())
    n = sum(len(v) for v in groups.values())
    return f'<div class="panel panel-checks"><h2>Checks <span class="badge">{n}</span></h2><ul>{items}</ul></div>'


ICON_ZOOM = ('<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M12 3h5v5M8 17H3v-5M17 3l-5.5 5.5M3 17l5.5-5.5" fill="none" '
             'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def look_cards(items, kind, rec_id):
    out = []
    for it in items:
        star = '<i class="look-star" title="Recommended">&#9733;</i>' if it["id"] == rec_id else ""
        out.append(
            f'<div class="look-card" data-kind="{kind}" data-id="{esc(it["id"])}">'
            f'<button type="button" class="look-pick" aria-pressed="false">'
            f'<span class="look-thumb"><img src="{esc(it["thumb"])}" alt="{esc(it["name"])}" loading="lazy">'
            f'{star}<span class="look-ring">Picked</span></span>'
            f'<span class="look-name">{esc(it["name"])}<code>{esc(it["id"])}</code></span>'
            f'<span class="look-blurb">{esc(it.get("blurb", ""))}</span></button>'
            f'<button type="button" class="look-zoom" data-src="{esc(it["thumb"])}" data-label="{esc(it["name"])}" '
            f'aria-label="View {esc(it["name"])} full size">{ICON_ZOOM}</button></div>')
    return "".join(out)


def look_label(look, kind, lid):
    """The style's name without its id: 'Cozy loft'."""
    return look_name(look, kind, lid).split(" ", 1)[-1]


def look_section(sb):
    """The optional "Pick your look" section ('' without a "look" key, so the page stays byte-identical)."""
    look = sb.get("look")
    if not look:
        return ""
    cur = look["current"]
    rec = look.get("recommended")
    intro = f'<p class="look-intro">{esc(look["intro"])}</p>' if look.get("intro") else ""
    rec_box = ""
    if rec:
        rec_box = (f'<div class="look-rec"><div><p class="look-rec-h"><i>&#9733;</i> Recommended: '
                   f'<b>{esc(look_label(look, "doodle", rec["doodle"]))}</b> + '
                   f'<b>{esc(look_label(look, "type", rec["type"]))}</b></p>'
                   f'<p class="look-rec-why">{esc(rec.get("why", ""))}</p></div>'
                   f'<button type="button" class="look-use" id="look-use">Use this</button></div>')
    names = (f'<b>{esc(look_label(look, "doodle", cur["doodle"]))}</b> doodles with '
             f'<b>{esc(look_label(look, "type", cur["type"]))}</b> text')
    rec_d = rec["doodle"] if rec else ""
    rec_t = rec["type"] if rec else ""
    return f"""<section class="look" id="look" aria-label="Pick your look" data-cur-doodle="{esc(cur['doodle'])}" data-cur-type="{esc(cur['type'])}" data-cur-custom="{esc(cur.get('custom', ''))}" data-rec-doodle="{esc(rec_d)}" data-rec-type="{esc(rec_t)}">
    <h2 class="look-title">Pick your look</h2>
    {intro}
    {rec_box}
    <h3 class="look-h">Doodle style</h3>
    <div class="look-grid" id="look-doodles">{look_cards(look["doodles"], "doodle", rec_d)}</div>
    <h3 class="look-h">Text style</h3>
    <div class="look-grid" id="look-types">{look_cards(look["types"], "type", rec_t)}</div>
    <label class="gen-label" for="look-custom">Want something else? Describe your own look (optional)</label>
    <textarea id="look-custom" rows="3" placeholder="For example: thicker outlines, pastel colors, lettering like a children's book."></textarea>
    <div class="look-save-row"><button type="button" class="look-save" id="look-save">Save look</button><span class="look-tick" id="look-tick" aria-live="polite"></span></div>
    <p class="look-explain">The beats below show {names}. A new pick is drawn in the next version after you click Done.</p>
    <p class="look-new" id="look-new" hidden></p>
  </section>
  """


def beat_card(i, b, sb):
    what = "".join(f"<li>{esc(w)}</li>" for w in b["what"])
    sound = (" · ".join(esc(s) for s in b["sound"]) if b["sound"] else '<span class="quiet">no sound effects</span>')
    if b.get("ref"):
        ref = (f'<button type="button" class="ref-thumb" data-src="{esc(b["ref"]["src"])}" '
               f'data-label="Reference">'
               f'<img src="{esc(b["ref"]["src"])}" alt="reference" loading="lazy"></button>'
               f'<span>{esc(b["ref"]["why"])}</span>')
    else:
        ref = f'<span class="quiet">{esc(b.get("ref_none") or "No reference")}</span>'
    alerts = "".join(f'<p class="flag"><i>!</i>{esc(a)}</p>' for a in b.get("alerts", []))
    needs = "".join(f'<p class="flag flag-need"><i>…</i>Missing: {esc(n["what"])} (placeholder: '
                    f'{esc(n["placeholder"])})</p>' for n in sb.get("needs", []) if n.get("beat") == b["id"])
    est = ' <span class="est">estimated</span>' if b.get("estimated") else ""
    changed = '<span class="changed">changed in this version</span>' if b["id"] in sb.get("changed_ids", []) else ""
    opts = versions(b)
    if opts:       # a beat that offers versions: one Approve per version, then Change
        data_options = f' data-options="{"".join(opts)}"'
        vers = f'<span class="vers">{len(opts)} versions · pick one</span>'
        pick = (f'<p class="flag flag-pick"><i>?</i>Approved, but no version picked yet: click Approve '
                f'{or_list(opts)}.</p>')
        actions_class = "actions has-opts"
        approve = "\n      ".join(
            f'<button type="button" class="act ok" data-opt="{L}" aria-pressed="false">{ICON_OK}<span>Approve {L}</span></button>'
            for L in opts)
    else:
        data_options = vers = pick = ""
        actions_class = "actions"
        approve = f'<button type="button" class="act ok" aria-pressed="false">{ICON_OK}<span>Approve</span><kbd>A</kbd></button>'
    return f"""
<article class="beat" id="b-{esc(b['id'])}" data-beat="{esc(b['id'])}" data-n="{i:02d}"{data_options}>
  <div class="beat-num" aria-hidden="true">{i:02d}</div>
  <div class="beat-media">{sequence(b)}</div>
  <div class="beat-body">
   <div class="beat-text">
    <div class="beat-head">
      <span class="tc">{tc(b['start'])} to {tc(b['end'])}</span><span class="sep">/</span><span class="tc">{dur(float(b['end']) - float(b['start']))}</span>{est}
      <span class="setup"><i class="sw k-{esc(b['shot']['kind'])}"></i>{esc(b['shot']['label'])}</span>{vers}{changed}
    </div>
    <blockquote class="line">{marked(b['line'], b.get('keys', []))}</blockquote>
    <ul class="what">{what}</ul>
    <dl class="meta">
      <div><dt>Sound</dt><dd>{sound}</dd></div>
      <div><dt>Music</dt><dd>{esc(b['music'])}</dd></div>
      <div><dt>Reference</dt><dd class="ref">{ref}</dd></div>
    </dl>
    {alerts}{needs}{pick}
    <div class="note"><textarea rows="3" placeholder="What should change? For example: make the flare softer."></textarea></div>
   </div>
    <div class="{actions_class}">
      {approve}
      <button type="button" class="act chg" aria-pressed="false">{ICON_CHG}<span>Change</span><kbd>C</kbd></button>
      <span class="saved-tick" aria-live="polite"></span>
    </div>
  </div>
</article>"""


def page(sb):
    n = len(sb["beats"])
    v = int(sb["version"])
    num = numbers(sb)
    changes = ("".join(f"<li>{esc(c)}</li>" for c in sb["changes"]) if sb.get("changes")
               else '<li class="quiet">First version.</li>')
    needs = ("".join(f'<li><b>{esc(x["what"])}</b> <a href="#b-{esc(x["beat"])}">beat {num.get(x["beat"], esc(x["beat"]))}</a><br>'
                     f'<span class="quiet">Placeholder: {esc(x["placeholder"])}</span></li>' for x in sb["needs"])
             if sb.get("needs") else '<li class="quiet">Nothing. All the material is in.</li>')
    stand_in = (f'<aside class="proto"><b>Prototype</b><span>{esc(sb["stand_in"])}</span></aside>'
                if sb.get("stand_in") else "")
    cards = "".join(beat_card(i, b, sb) for i, b in enumerate(sb["beats"], 1))
    how_versions = ("When a beat offers versions, approve the one you want: <b>Approve A</b>, <b>B</b> or <b>C</b>.\n      "
                    if any(versions(b) for b in sb["beats"]) else "")
    wrap_look = '<p class="look-new" id="wrap-look" hidden></p>\n    ' if sb.get("look") else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Storyboard · {esc(sb['project'])} v{v}</title>
<script>try{{var t=localStorage.getItem('sb-theme');if(t)document.documentElement.dataset.theme=t;}}catch(e){{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<link rel="stylesheet" href="page.css">
</head>
<body data-version="{v}" data-total="{n}">
<header class="top">
  <div class="brand"><span class="wordmark">Storyboard</span><span class="proj">{esc(sb['project'])}</span><span class="ver">v{v}</span></div>
  {filmstrip(sb)}
  <div class="tools">
    <span class="status" id="status" aria-live="polite"></span>
    <a class="progress" href="#wrap" title="Go to Done"><b id="n-ok">0</b><span>/{n} approved</span></a>
    <div class="filter" role="group" aria-label="Show">
      <button type="button" data-f="all" class="is-on">All</button><button type="button" data-f="todo">To review</button><button type="button" data-f="chg">Changes</button>
    </div>
    <button type="button" class="theme" id="theme" aria-label="Switch light or dark"><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="6.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 3.5a6.5 6.5 0 0 1 0 13z" fill="currentColor"/></svg></button>
  </div>
</header>
<main>
  <section class="intro">
    <p class="kicker">{esc(sb['project'])} · v{v} · {dur(sb['length'])} · {n} beats</p>
    <h1>{esc(sb['title'])}</h1>
    <p class="meta">{esc(sb.get('meta', ''))}</p>
    <p class="how">Approve or change each beat, then click <b>Done</b> at the end: your review goes straight to Claude.
      <span class="keys"><kbd>A</kbd> approve <kbd>C</kbd> change <kbd>O</kbd> original take <kbd>J</kbd><kbd>K</kbd> next and previous</span><br>
      {how_versions}Nothing gets edited before the whole storyboard is approved, and nothing gets rendered before your <b>render</b>.</p>
    {stand_in}
  </section>
  <section class="overview">
    <div class="panel"><h2>What changed in v{v}</h2><ul>{changes}</ul></div>
    <div class="panel"><h2>Still missing</h2><ul>{needs}</ul></div>
    {checks_panel(sb)}
  </section>
  {timeline(sb)}
  {look_section(sb)}<section class="beats" id="beats">{cards}</section>
  <section class="wrap" id="wrap">
    <h2 class="wrap-title">Wrap-up</h2>
    <p class="wrap-sum" id="wrap-sum"></p>
    <ul class="wrap-list" id="wrap-list"></ul>
    {wrap_look}<label class="gen-label" for="general">General notes</label>
    <textarea id="general" rows="3" placeholder="Pace, music, tone: anything about the whole video. Notes on this page itself are welcome too."></textarea>
    <div class="done-row">
      <button type="button" class="done" id="done">Done · send my review</button>
      <p class="done-note" id="done-note"></p>
    </div>
  </section>
</main>
<div class="newver" id="newver" hidden><span>A new version is ready</span><button type="button" id="newver-go">Open it</button></div>
<div class="lightbox" id="lightbox" hidden><button type="button" class="lb-prev" aria-label="Previous">‹</button><figure><img alt=""><figcaption></figcaption></figure><button type="button" class="lb-next" aria-label="Next">›</button></div>
<script src="review.js"></script>
</body>
</html>
"""


def main(folder):
    out = Path(folder).resolve()
    sb = json.loads((out / "storyboard.json").read_text(encoding="utf-8"))
    problems = check(sb, out)
    if problems:
        print("storyboard.json did not pass:\n  " + "\n  ".join(problems))
        sys.exit(1)
    (out / "index.html").write_text(page(sb), encoding="utf-8")
    src = HERE / "static" if (HERE / "static").is_dir() else HERE      # the vendored copy keeps them beside build.py
    for f in ("page.css", "review.js"):
        shutil.copy2(src / f, out / f)
    print(f"OK: {out / 'index.html'} ({len(sb['beats'])} beats, v{sb['version']})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python build.py <storyboard folder>")
    main(sys.argv[1])
