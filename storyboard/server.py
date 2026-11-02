"""Storyboard review server (prototype): serves one storyboard folder and saves the user's clicks to review.json.

    python server.py <storyboard folder> [--port 8300]

GET  /api/review   the review state.
POST /api/review   {"beat": "L03", "value": "approved" | "change" | null} and/or {"beat": "L03", "note": "..."},
                   or {"general": "..."}: only the fields sent change, so two open tabs never overwrite each other.
                   A beat that offers versions (its moments carry "option": "A", "B"...; see build.py) is approved with
                   the letter picked: {"beat": "L07", "value": "approved", "option": "B"}. The letter is saved in
                   review.json next to the value, and "change" or null drops it. Refused with 400: "option" sent
                   without "value" ("send option with value approved"); approved on a beat with versions without one
                   of its letters ("pick a version: A, B or C"); a letter with any other value, or on a beat that
                   offers no versions ("no version to pick here"). A beat with one version is approved as before.
POST /api/submit   {"kind": "review" | "go"}: the Done button. It stamps "submitted" into review.json; wait_done.py,
                   running in the background of the Claude session, sees it and wakes the session. "go" is refused
                   (409) unless every beat is approved and every beat with versions holds one of its CURRENT letters
                   (a letter that storyboard.json no longer offers counts as missing). The 409 body is
                   {"error": "go needs every beat approved"}, plus "missing_version": [beat ids] when some beats are
                   approved without a valid letter.
POST /api/look     {"doodle": "D7", "type": "T2", "custom": "free text"}: the "Pick your look" Save button (only when
                   storyboard.json has a "look" key). Saved as "look": {doodle, type, custom, at} in review.json.
                   Refused with 400: no "look" in the storyboard, a doodle or type id the look does not list, a custom
                   that is not a string or is longer than 4000 characters. "go" is refused (409, {"error": "the new
                   look is not drawn yet", "look_pending": true}) while the saved pick differs from look.current.
GET  /api/version  {"version": N} from storyboard.json, re-read when it changes, so an open page can say that a new
                   version is ready.
Every write keeps a timestamped backup in review-backups/ (the last 50). Guards: it answers only requests
addressed to this machine (Host and Origin
checks), takes JSON writes only, and serves only the file types in STATIC from the folder.
"""
import argparse
import json
import os
import shutil
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from build import look_pending, or_list, versions   # build.py sits next to this file

STATIC = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
          ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
          ".svg": "image/svg+xml"}
MAX_BODY = 64 * 1024
MAX_NOTE = 4000
VALUES = ("approved", "change", None)
KINDS = ("review", "go")


def offered(sb):
    """{beat id: its version letters} for the beats that offer versions; a beat with one version is not in it."""
    return {b["id"]: v for b in sb["beats"] if (v := versions(b))}


def go_refusal(state, sb):
    """None when "go" is allowed. Otherwise the 409 body: every beat must be approved, and every beat with versions must
    hold one of its current letters. "missing_version" lists the beats approved without a valid letter."""
    beats = state.get("beats", {})
    unapproved, missing = False, []
    for bid in sb["ids"]:
        item = beats.get(bid) or {}
        if item.get("value") != "approved":
            unapproved = True
        elif bid in sb["options"] and item.get("option") not in sb["options"][bid]:
            missing.append(bid)
    if not (unapproved or missing):
        if sb.get("look") and look_pending(state.get("look"), sb["look"]["current"]):
            return {"error": "the new look is not drawn yet", "look_pending": True}
        return None
    refusal = {"error": "go needs every beat approved"}
    if missing:
        refusal["missing_version"] = missing
    return refusal


def make_handler(root, port):
    sb_path = root / "storyboard.json"
    sb_cache = {"mtime": None, "ids": [], "version": 1, "options": {}, "look": None}
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    origins = {f"http://{h}" for h in hosts}
    review = root / "review.json"
    backups = root / "review-backups"
    lock = threading.Lock()

    def storyboard():
        mtime = sb_path.stat().st_mtime
        if mtime != sb_cache["mtime"]:
            sb = json.loads(sb_path.read_text(encoding="utf-8"))
            sb_cache.update(mtime=mtime, ids=[b["id"] for b in sb["beats"]], version=int(sb.get("version", 1)),
                            options=offered(sb), look=sb.get("look") or None)
        return sb_cache

    def load():
        if review.exists():
            try:
                return json.loads(review.read_text(encoding="utf-8"))
            except ValueError:
                pass
        return {"version": storyboard()["version"], "beats": {}, "general": {"note": ""}}

    def save(state):
        if review.exists():
            backups.mkdir(exist_ok=True)
            shutil.copy2(review, backups / f"review-{datetime.now():%Y%m%d-%H%M%S-%f}.json")
            for old in sorted(backups.glob("review-*.json"))[:-50]:
                old.unlink()
        tmp = review.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, review)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def local(self):
            return self.headers.get("Host", "") in hosts

        def do_GET(self):
            if not self.local():
                return self.send(403, {"error": "host"})
            path = unquote(urlparse(self.path).path)
            if path == "/api/review":
                with lock:
                    return self.send(200, load())
            if path == "/api/version":
                return self.send(200, {"version": storyboard()["version"]})
            if path.endswith("/"):
                path += "index.html"
            f = (root / path.lstrip("/")).resolve()
            inside = root == f or root in f.parents
            if (not inside or not f.is_file() or f.suffix.lower() not in STATIC
                    or "review-backups" in f.parts or f.name.endswith(".tmp")):
                return self.send(404, {"error": "not found"})
            self.send(200, f.read_bytes(), STATIC[f.suffix.lower()])

        def read_json(self):
            origin = self.headers.get("Origin")
            if origin and origin not in origins:
                return None, (403, {"error": "origin"})
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return None, (415, {"error": "json only"})
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return None, (413, {"error": "size"})
            try:
                body = json.loads(self.rfile.read(n))
            except ValueError:
                return None, (400, {"error": "bad json"})
            if not isinstance(body, dict):
                return None, (400, {"error": "object only"})
            return body, None

        def do_POST(self):
            if not self.local():
                return self.send(403, {"error": "host"})
            path = urlparse(self.path).path
            if path not in ("/api/review", "/api/submit", "/api/look"):
                return self.send(404, {"error": "not found"})
            body, err = self.read_json()
            if err:
                return self.send(*err)
            now = datetime.now().isoformat(timespec="seconds")
            with lock:
                sb = storyboard()
                state = load()
                if path == "/api/submit":
                    kind = body.get("kind")
                    if kind not in KINDS:
                        return self.send(400, {"error": "kind"})
                    refusal = go_refusal(state, sb) if kind == "go" else None
                    if refusal:
                        return self.send(409, refusal)
                    state["submitted"] = {"at": now, "version": sb["version"], "kind": kind}
                elif path == "/api/look":
                    look = sb["look"]
                    if not look:
                        return self.send(400, {"error": "this storyboard has no look to pick"})
                    doodles = [i["id"] for i in look["doodles"]]
                    types = [i["id"] for i in look["types"]]
                    custom = body.get("custom", "")
                    if body.get("doodle") not in doodles:
                        return self.send(400, {"error": f"doodle: one of {', '.join(doodles)}"})
                    if body.get("type") not in types:
                        return self.send(400, {"error": f"type: one of {', '.join(types)}"})
                    if not isinstance(custom, str) or len(custom) > MAX_NOTE:
                        return self.send(400, {"error": f"custom: text up to {MAX_NOTE} characters"})
                    state["look"] = {"doodle": body["doodle"], "type": body["type"], "custom": custom, "at": now}
                elif "beat" in body:
                    bid = body["beat"]
                    if bid not in sb["ids"]:
                        return self.send(400, {"error": "unknown beat"})
                    letters = sb["options"].get(bid)           # None: this beat offers one version
                    if "option" in body and "value" not in body:
                        return self.send(400, {"error": "send option with value approved"})
                    if "value" in body:
                        if body["value"] not in VALUES:
                            return self.send(400, {"error": "value"})
                        if body["value"] == "approved" and letters:
                            if body.get("option") not in letters:
                                return self.send(400, {"error": f"pick a version: {or_list(letters)}"})
                        elif body.get("option") is not None:
                            return self.send(400, {"error": "no version to pick here"})
                    item = state.setdefault("beats", {}).setdefault(bid, {})
                    if "value" in body:
                        item["value"] = body["value"]
                        if body["value"] == "approved" and letters:
                            item["option"] = body["option"]
                        else:
                            item.pop("option", None)
                    if "note" in body:
                        item["note"] = str(body["note"])[:MAX_NOTE]
                    item["at"] = now
                elif "general" in body:
                    state.setdefault("general", {})["note"] = str(body["general"])[:MAX_NOTE]
                    state["general"]["at"] = now
                else:
                    return self.send(400, {"error": "send beat or general"})
                state["version"] = sb["version"]
                state["saved_at"] = now
                save(state)
            self.send(200, state)

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--port", type=int, default=8300)
    a = ap.parse_args()
    root = Path(a.folder).resolve()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(root, a.port))
    print(f"storyboard: http://127.0.0.1:{a.port}/  (clicks saved to {root / 'review.json'})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
