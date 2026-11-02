"""Wait until the user clicks Done on the storyboard page, then print the review and exit.

    python wait_done.py <storyboard folder>

The Claude session runs this with Bash run_in_background right after it opens a storyboard version: when the user clicks
Done, server.py stamps "submitted" into review.json, this script sees it, prints the review and exits, and the exit
wakes the session. The user does not have to write anything in the chat. It only reads files.

A beat that offers versions (Option A / B / C, 2026-10-22) shows the letter picked in the approved list ("07 A") and in a
"versions picked" block. A beat approved without one of its CURRENT letters is not in the approved list: it goes to a
"no version picked" block, so the session asks which version the user wants. Without versions the text is what it always was.
"""
import json
import sys
import time
from pathlib import Path

from build import look_name, look_pending, or_list, versions   # build.py sits next to this file


def load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def look_lines(saved, look):
    """The "Pick your look" block: what the user picked (or kept) and their own request, if any."""
    cur = look.get("current") or {}
    now = f"{look_name(look, 'doodle', cur.get('doodle'))} + {look_name(look, 'type', cur.get('type'))}"
    if not look_pending(saved, cur):
        return [f"look: kept {now}"]
    picked = f"{look_name(look, 'doodle', saved.get('doodle'))} + {look_name(look, 'type', saved.get('type'))}"
    lines = [f"look: picked {picked} (current: {now}) -> redraw in the next version"]
    custom = str(saved.get("custom") or "").strip()
    if custom and custom != str(cur.get("custom") or "").strip():
        lines.append(f'custom look request: "{custom}"')
    return lines


def summary(state, sb):
    sub = state.get("submitted") or {}
    beats = state.get("beats") or {}
    rows = [(f"{i:02d}", b["id"], beats.get(b["id"]) or {}) for i, b in enumerate(sb.get("beats", []), 1)]
    letters = {b["id"]: versions(b) for b in sb.get("beats", [])}
    ok, picked, no_pick = [], [], []
    for n, bid, r in rows:
        if r.get("value") != "approved":
            continue
        if not letters[bid]:
            ok.append(n)
        elif r.get("option") in letters[bid]:
            ok.append(f"{n} {r['option']}")
            picked.append(f"  {n} ({bid}): approved {r['option']}")
        else:
            no_pick.append(f"  {n} ({bid}): approved without a version ({or_list(letters[bid])}): ask which one")
    chg = [(n, bid, (r.get("note") or "").strip()) for n, bid, r in rows if r.get("value") == "change"]
    todo = [n for n, _, r in rows if not r.get("value")]
    kind = "GO: every beat approved, start the edit" if sub.get("kind") == "go" else "REVIEW: make the next version"
    out = [f"STORYBOARD DONE · {sb.get('project', '?')} v{sub.get('version', '?')} · sent {sub.get('at', '?')}",
           kind,
           "approved: " + (", ".join(ok) or "none")]
    if picked:
        out += ["versions picked:"] + picked
    if no_pick:
        out += ["no version picked:"] + no_pick
    out.append("to change:" + ("" if chg else " none"))
    out += [f"  {n} ({bid}): {note or '(no note)'}" for n, bid, note in chg]
    out.append("not reviewed: " + (", ".join(todo) or "none"))
    out.append("general notes: " + ((state.get("general") or {}).get("note", "").strip() or "none"))
    if sb.get("look"):
        out += look_lines(state.get("look"), sb["look"])
    return "\n".join(out)


def main(folder):
    root = Path(folder).resolve()
    review, sb_path = root / "review.json", root / "storyboard.json"
    seen = (load(review).get("submitted") or {}).get("at")
    while True:
        at = (load(review).get("submitted") or {}).get("at")
        if at and at != seen:
            break
        time.sleep(1)
    print(summary(load(review), load(sb_path)), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python wait_done.py <storyboard folder>")
    main(sys.argv[1])
