"""The review loop end to end, on a temporary copy (never on a real review.json).

    python -m pytest tests/test_flow.py -q      (or: python tests/test_flow.py)

Clicks and notes are saved one item at a time; "go" is refused until every beat is approved; Done stamps "submitted";
wait_done.py sees a new Done and prints the review; a foreign Host is refused.

Versions (a beat that offers Option A / B / C, 2026-10-22): build.check refuses a half-named beat, the page has one
Approve per version, the server saves the pick and refuses "go" without a valid one, the pick survives a new storyboard
version, and the waiter prints it. A storyboard without versions behaves exactly as before.
"""
import contextlib
import json
import re
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "storyboard"
sys.path.insert(0, str(HERE))
import build  # noqa: E402
import server  # noqa: E402
import wait_done  # noqa: E402

SB = {"project": "T1", "title": "t", "version": 1, "length": 6.0,
      "beats": [{"id": "L01", "start": 0, "end": 2}, {"id": "L02", "start": 2, "end": 4}, {"id": "L03", "start": 4, "end": 6}]}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def call(port, path, body=None, host=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "Host": host or f"127.0.0.1:{port}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_flow():
    root = Path(tempfile.mkdtemp(prefix="sb-test-"))
    try:
        (root / "storyboard.json").write_text(json.dumps(SB), encoding="utf-8")
        port = free_port()
        srv = ThreadingHTTPServer(("127.0.0.1", port), server.make_handler(root, port))
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        assert call(port, "/api/review", {"beat": "L01", "value": "approved"})[0] == 200
        assert call(port, "/api/review", {"beat": "L02", "value": "change"})[0] == 200
        assert call(port, "/api/review", {"beat": "L02", "note": "softer flare"})[0] == 200
        assert call(port, "/api/review", {"general": "pace is good"})[0] == 200
        state = json.loads((root / "review.json").read_text(encoding="utf-8"))
        assert state["beats"]["L01"]["value"] == "approved"
        assert state["beats"]["L02"] == {**state["beats"]["L02"], "value": "change", "note": "softer flare"}
        assert list((root / "review-backups").glob("review-*.json")), "a backup before each write"

        assert call(port, "/api/review", {"beat": "L99", "value": "approved"})[0] == 400
        assert call(port, "/api/submit", {"kind": "go"})[0] == 409, "go needs every beat approved"
        assert call(port, "/api/version")[1] == {"version": 1}
        assert call(port, "/api/review", host="evil.example:80")[0] == 403

        # the waiter wakes on a NEW Done only
        out = {}
        waiter = threading.Thread(target=lambda: out.setdefault("text", run_waiter(root)), daemon=True)
        waiter.start()
        time.sleep(1.5)
        assert waiter.is_alive(), "no Done yet: still waiting"
        status, state = call(port, "/api/submit", {"kind": "review"})
        assert status == 200 and state["submitted"]["kind"] == "review" and state["submitted"]["version"] == 1
        waiter.join(timeout=5)
        assert not waiter.is_alive(), "Done wakes the waiter"
        text = out["text"]
        assert "REVIEW" in text and "approved: 01" in text and "02 (L02): softer flare" in text
        assert "not reviewed: 03" in text and "general notes: pace is good" in text

        # a new storyboard version is seen without restarting the server
        sb2 = {**SB, "version": 2}
        time.sleep(0.05)
        (root / "storyboard.json").write_text(json.dumps(sb2), encoding="utf-8")
        assert call(port, "/api/version")[1] == {"version": 2}
        srv.shutdown()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_waiter(root):
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        wait_done.main(str(root))
    return buf.getvalue()


# ---- versions: a beat that offers Option A / B / C gets one Approve per version (2026-10-22) -----------------------

NO_KEY = object()     # a moment without an "option" key


def full_beat(bid, start, end, letters=None, per=1):
    """A complete beat (every field build.page reads).
    letters: the versions it offers, `per` moments each, at the same instants. None: a one-version beat with `per` moments."""
    def moment(k, option=None):
        m = {"t": start + 0.5 + k, "caption": f"look {option or k + 1}",
             "plan": f"frames/{bid}-plan-{option or ''}{k + 1}.jpg", "take": f"frames/{bid}-orig-{k + 1}.jpg"}
        if option:
            m["option"] = option
        return m
    moments = [moment(k, L) for L in letters for k in range(per)] if letters else [moment(k) for k in range(per)]
    return {"id": bid, "start": start, "end": end, "line": "Comment EDIT, and I'll send you the guide.", "keys": ["EDIT"],
            "shot": {"kind": "th", "name": "Sofa", "label": "Sofa, wide shot"}, "moments": moments,
            "what": ["a bullet"], "sound": [], "music": "keeps going", "ref": None, "ref_none": "No reference", "alerts": []}


def versioned(bid, options, start=0, end=2):
    """A complete beat whose moments carry these "option" values (NO_KEY: that moment has no "option" key)."""
    b = full_beat(bid, start, end, per=len(options))
    for m, o in zip(b["moments"], options):
        if o is not NO_KEY:
            m["option"] = o
    return b


def storyboard(beats, version=1):
    return {"project": "T2", "title": "t", "version": version, "length": float(beats[-1]["end"]), "beats": beats}


def write_sb(root, sb, later=False):
    """Write storyboard.json; later=True waits first, so the server sees a new modified time."""
    if later:
        time.sleep(0.1)
    (root / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@contextlib.contextmanager
def served(sb):
    """A server on a free port over a temporary storyboard folder (never a real review.json)."""
    root = Path(tempfile.mkdtemp(prefix="sb-test-"))
    srv = None
    try:
        write_sb(root, sb)
        port = free_port()
        srv = ThreadingHTTPServer(("127.0.0.1", port), server.make_handler(root, port))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        yield root, port
    finally:
        if srv:
            srv.shutdown()
            srv.server_close()
        shutil.rmtree(root, ignore_errors=True)


def test_versions_check():
    def problems(options):
        return build.check(storyboard([versioned("L07", options)]))

    # the helper: the distinct letters in order of first appearance, and [] when there are fewer than two
    assert build.versions(versioned("L07", ["A", "B", "C"])) == ["A", "B", "C"]
    assert build.versions(versioned("L07", ["B", "B", "A"])) == ["B", "A"]
    assert build.versions(versioned("L07", [NO_KEY, NO_KEY])) == []
    assert build.versions(versioned("L07", ["A", "A"])) == []
    assert build.versions({"id": "L01", "start": 0, "end": 2}) == [], "an old beat without moments"

    # accepted
    assert problems(["A", "B", "C"]) == [], "three versions, one moment each"
    assert problems(["A", "A", "B"]) == [], "A has two moments, B has one"
    assert problems([NO_KEY, NO_KEY]) == [], "no option key at all: a one-version beat, as before"

    # refused, one message per mistake
    every = 'L07: every moment of a beat with versions names its version ("option": "A")'
    assert problems(["A", NO_KEY, "B"]) == [every]
    assert problems(["A", NO_KEY, "A"]) == [every], "the half-named beat is the only thing said about it"
    for bad in ("b", "AB", "", 1, None):
        assert problems(["A", bad]) == ['L07: "option" is one capital letter (A, B, C...)'], bad
    assert problems(["A", "A"]) == ['L07: only one version (A): drop "option" or add the other versions']
    assert problems(["C"]) == ['L07: only one version (C): drop "option" or add the other versions']
    assert problems(["A", "B", "A"]) == ["L07: the moments of version A sit together"]
    assert problems(["A", "B", "C", "B"]) == ["L07: the moments of version B sit together"]
    assert problems(["A", "B", "A", "B"]) == ["L07: the moments of version A sit together",
                                              "L07: the moments of version B sit together"]


def test_versions_page():
    sb = storyboard([full_beat("L01", 0, 2), full_beat("L02", 2, 4, letters="ABC"), full_beat("L03", 4, 6, per=2),
                     versioned("L04", ["A", "A", "B"], 6, 8)])
    assert build.check(sb) == []
    page = build.page(sb)
    cards = {m.group(1): m.group(0) for m in re.finditer(r'<article class="beat" id="b-(\w+)".*?</article>', page, re.S)}
    assert list(cards) == ["L01", "L02", "L03", "L04"]

    # a beat with three versions: one Approve per version, then Change
    abc = cards["L02"]
    assert re.search(r'<article [^>]*data-options="ABC"', abc)
    for L in "ABC":
        assert (f'<button type="button" class="act ok" data-opt="{L}" aria-pressed="false">{build.ICON_OK}'
                f'<span>Approve {L}</span></button>') in abc
    assert abc.index("Approve A") < abc.index("Approve B") < abc.index("Approve C") < abc.index("<span>Change</span>")
    assert '<div class="actions has-opts">' in abc
    assert "<kbd>A</kbd>" not in abc and "<kbd>C</kbd>" in abc, "no key hint on a version button; Change keeps C"
    assert '<span class="vers">3 versions · pick one</span>' in abc
    assert ('<p class="flag flag-pick"><i>?</i>Approved, but no version picked yet: click Approve A, B or C.</p>') in abc
    # the frames: the letter on each, "or" between the versions, the version in the caption
    assert '<div class="seq seq-3 seq-opts">' in abc
    for k, L in enumerate("ABC"):
        assert f'<figure class="mo" data-i="{k}" data-opt="{L}">' in abc
        assert f'<span class="mo-step mo-opt">{L}</span>' in abc
        assert f'<figcaption><span class="mo-tc">Version {L} · 0:02.5</span>look {L}</figcaption>' in abc
    assert abc.count('<span class="mo-or" aria-hidden="true">or</span>') == 2
    assert "mo-arrow" not in abc and '<span class="mo-step">' not in abc
    # the Approved stamp lands on the version picked: each version carries its own, so it never sits on another one
    for L in "ABC":
        assert f'</figcaption><span class="stamp stamp-ok">Approved {L}</span></figure>' in abc
    assert abc.count('class="stamp stamp-ok"') == 3, "no card-wide Approved stamp on a beat with versions"
    assert '<span class="stamp stamp-chg">Change</span></div>' in abc

    # versions A (two moments) and B (one): the arrow stays inside a version, "or" goes between versions
    ab = cards["L04"]
    assert re.search(r'<article [^>]*data-options="AB"', ab)
    assert ab.count('<span class="mo-arrow" aria-hidden="true">→</span>') == 1
    assert ab.count('<span class="mo-or" aria-hidden="true">or</span>') == 1
    assert ab.index("mo-arrow") < ab.index("mo-or")
    assert ab.count('<span class="mo-step mo-opt">A</span>') == 2 and ab.count('<span class="mo-step mo-opt">B</span>') == 1
    assert ab.count('Approved A</span>') == 1, "one stamp per version, on its first frame"
    assert "Approve A" in ab and "Approve B" in ab and "Approve C" not in ab
    assert '<span class="vers">2 versions · pick one</span>' in ab
    assert "click Approve A or B." in ab, "the card names its own letters"

    # a one-version beat in the same storyboard is exactly as before: the single Approve with its key hint
    one = cards["L01"]
    assert ('<div class="actions">\n'
            f'      <button type="button" class="act ok" aria-pressed="false">{build.ICON_OK}<span>Approve</span><kbd>A</kbd></button>\n'
            f'      <button type="button" class="act chg" aria-pressed="false">{build.ICON_CHG}<span>Change</span><kbd>C</kbd></button>\n'
            '      <span class="saved-tick" aria-live="polite"></span>\n'
            '    </div>') in one
    assert '<figure class="mo" data-i="0"><div class="mo-frame">' in one
    assert '<figcaption><span class="mo-tc">0:00.5</span>look 1</figcaption>' in one
    for new in ("data-opt", "mo-opt", "mo-or", "seq-opts", "vers", "flag-pick", "has-opts", "Version"):
        assert new not in one, new
    assert '<div class="seq seq-1">' in one and 'class="mo-step"' not in one
    two = cards["L03"]        # two moments, one version: numbered, joined by an arrow
    assert '<span class="mo-step">1</span>' in two and '<span class="mo-step">2</span>' in two
    assert two.count('<span class="mo-arrow" aria-hidden="true">→</span>') == 1
    assert "mo-or" not in two and "data-opt" not in two and "seq-opts" not in two

    # the intro tells about versions only when a beat has them
    sentence = "When a beat offers versions, approve the one you want: <b>Approve A</b>, <b>B</b> or <b>C</b>."
    assert sentence in page and page.index(sentence) < page.index("Nothing gets edited")
    plain = build.page(storyboard([full_beat("L01", 0, 2), full_beat("L02", 2, 4, per=2)]))
    assert "offers versions" not in plain and "Approve A" not in plain and "data-options" not in plain


def test_option_approve():
    sb = storyboard([full_beat("L01", 0, 2), full_beat("L02", 2, 4, letters="ABC"), full_beat("L03", 4, 6, letters="AB")])
    with served(sb) as (root, port):
        def post(body):
            return call(port, "/api/review", body)

        # refused, and a refused request writes nothing
        assert post({"beat": "L02", "value": "approved"}) == (400, {"error": "pick a version: A, B or C"})
        assert post({"beat": "L02", "value": "approved", "option": None}) == (400, {"error": "pick a version: A, B or C"})
        assert post({"beat": "L02", "value": "approved", "option": "Z"}) == (400, {"error": "pick a version: A, B or C"})
        assert post({"beat": "L03", "value": "approved"}) == (400, {"error": "pick a version: A or B"})
        assert post({"beat": "L03", "value": "approved", "option": "C"}) == (400, {"error": "pick a version: A or B"}), \
            "C is another beat's letter"
        assert post({"beat": "L01", "value": "approved", "option": "A"}) == (400, {"error": "no version to pick here"})
        assert post({"beat": "L02", "value": "change", "option": "A"}) == (400, {"error": "no version to pick here"})
        assert post({"beat": "L02", "value": None, "option": "A"}) == (400, {"error": "no version to pick here"})
        assert post({"beat": "L02", "option": "A"}) == (400, {"error": "send option with value approved"})
        assert not (root / "review.json").exists()

        # approved B is saved with its letter; another letter replaces it; a note leaves it alone
        status, state = post({"beat": "L02", "value": "approved", "option": "B"})
        assert status == 200 and state["beats"]["L02"]["value"] == "approved" and state["beats"]["L02"]["option"] == "B"
        assert read_json(root / "review.json")["beats"]["L02"]["option"] == "B"
        assert post({"beat": "L02", "value": "approved", "option": "C"})[0] == 200
        assert read_json(root / "review.json")["beats"]["L02"]["option"] == "C"
        assert post({"beat": "L02", "note": "softer"})[0] == 200
        saved = read_json(root / "review.json")["beats"]["L02"]
        assert saved["option"] == "C" and saved["note"] == "softer"

        # change, or undoing the approval, drops the letter
        assert post({"beat": "L02", "value": "change"})[0] == 200
        assert "option" not in read_json(root / "review.json")["beats"]["L02"]
        assert post({"beat": "L02", "value": "approved", "option": "A"})[0] == 200
        assert post({"beat": "L02", "value": None})[0] == 200
        saved = read_json(root / "review.json")["beats"]["L02"]
        assert saved["value"] is None and "option" not in saved and saved["note"] == "softer"

        # a beat with one version keeps its plain Approve, with no letter in the file
        assert post({"beat": "L01", "value": "approved"})[0] == 200
        assert post({"beat": "L01", "value": "approved", "option": None})[0] == 200
        assert "option" not in read_json(root / "review.json")["beats"]["L01"]

        # "go" needs a valid letter on every beat with versions. An old review.json says approved with no letter.
        ok = {"value": "approved", "at": "2026-10-24T09:00:00"}

        def by_hand(beats):
            (root / "review.json").write_text(json.dumps({"version": 1, "beats": beats, "general": {"note": ""}}),
                                              encoding="utf-8")

        refused = {"error": "go needs every beat approved"}
        by_hand({"L01": ok, "L02": ok, "L03": {**ok, "option": "A"}})
        assert call(port, "/api/submit", {"kind": "go"}) == (409, {**refused, "missing_version": ["L02"]})
        by_hand({"L01": ok, "L02": {**ok, "option": "Z"}, "L03": {**ok, "option": "C"}})
        assert call(port, "/api/submit", {"kind": "go"}) == (409, {**refused, "missing_version": ["L02", "L03"]}), \
            "a letter the beat does not offer counts as missing"
        by_hand({"L01": {"value": "change", "at": ok["at"]}, "L02": ok, "L03": {**ok, "option": "B"}})
        assert call(port, "/api/submit", {"kind": "go"}) == (409, {**refused, "missing_version": ["L02"]})
        by_hand({"L01": {"value": "change", "at": ok["at"]}, "L02": {**ok, "option": "B"}, "L03": {**ok, "option": "B"}})
        assert call(port, "/api/submit", {"kind": "go"}) == (409, refused), "only unapproved beats: as before"
        assert "submitted" not in read_json(root / "review.json")

        assert post({"beat": "L01", "value": "approved"})[0] == 200
        assert post({"beat": "L02", "value": "approved", "option": "B"})[0] == 200
        status, state = call(port, "/api/submit", {"kind": "go"})
        assert status == 200 and state["submitted"]["kind"] == "go"


def test_option_carry_over():
    def sb_of(version, letters_l02):
        return storyboard([full_beat("L01", 0, 2), full_beat("L02", 2, 4, letters=letters_l02), full_beat("L03", 4, 6)],
                          version=version)

    with served(sb_of(1, "ABC")) as (root, port):
        for bid, extra in (("L01", {}), ("L02", {"option": "B"}), ("L03", {})):
            assert call(port, "/api/review", {"beat": bid, "value": "approved", **extra})[0] == 200

        # v2 offers the same versions: the pick is still there, "go" is accepted, the waiter prints it
        write_sb(root, sb_of(2, "ABC"), later=True)
        assert call(port, "/api/version")[1] == {"version": 2}
        assert call(port, "/api/review")[1]["beats"]["L02"]["option"] == "B"
        out = {}
        waiter = threading.Thread(target=lambda: out.setdefault("text", run_waiter(root)), daemon=True)
        waiter.start()
        time.sleep(1.5)
        status, state = call(port, "/api/submit", {"kind": "go"})
        assert status == 200 and state["submitted"]["kind"] == "go" and state["submitted"]["version"] == 2
        waiter.join(timeout=5)
        assert not waiter.is_alive(), "Done wakes the waiter"
        text = out["text"]
        assert "GO: every beat approved, start the edit" in text
        assert "approved: 01, 02 B, 03" in text
        assert "versions picked:\n  02 (L02): approved B\n" in text
        assert "no version picked" not in text

        # v3 offers A and C only: B no longer exists, so the beat has no valid pick
        write_sb(root, sb_of(3, "AC"), later=True)
        assert call(port, "/api/review")[1]["beats"]["L02"]["option"] == "B", "the file is not rewritten behind his back"
        status, body = call(port, "/api/submit", {"kind": "go"})
        assert (status, body) == (409, {"error": "go needs every beat approved", "missing_version": ["L02"]})
        text = wait_done.summary(read_json(root / "review.json"), read_json(root / "storyboard.json"))
        assert "approved: 01, 03\n" in text, text
        assert "no version picked:\n  02 (L02): approved without a version (A or C): ask which one\n" in text
        assert "versions picked" not in text and "02 B" not in text and "not reviewed: none" in text


def test_summary_unchanged_without_versions():
    sb = {"project": "T5", "beats": [{"id": "L01", "moments": [{"t": 1}]}, {"id": "L02"}, {"id": "L03"}]}
    state = {"submitted": {"at": "2026-10-24T10:00:00", "version": 1, "kind": "review"},
             "beats": {"L01": {"value": "approved", "option": "B"}, "L02": {"value": "change", "note": "softer flare"}},
             "general": {"note": "pace is good"}}
    # exactly what the waiter printed before versions existed (a stale option on a one-version beat is ignored)
    assert wait_done.summary(state, sb) == "\n".join([
        "STORYBOARD DONE · T5 v1 · sent 2026-10-24T10:00:00",
        "REVIEW: make the next version",
        "approved: 01",
        "to change:",
        "  02 (L02): softer flare",
        "not reviewed: 03",
        "general notes: pace is good"])
    everything = {"submitted": {"at": "2026-10-24T10:00:00", "version": 1, "kind": "go"},
                  "beats": {b["id"]: {"value": "approved"} for b in sb["beats"]}}
    text = wait_done.summary(everything, sb)
    assert text == "\n".join([
        "STORYBOARD DONE · T5 v1 · sent 2026-10-24T10:00:00",
        "GO: every beat approved, start the edit",
        "approved: 01, 02, 03",
        "to change: none",
        "not reviewed: none",
        "general notes: none"])
    assert "versions picked" not in text and "no version picked" not in text

    # the same lines show up when a beat does offer versions (so the check above is not empty)
    sb2 = {"project": "T5", "beats": [{"id": "L01"}, {"id": "L02", "moments": [{"option": "A"}, {"option": "B"}]},
                                      {"id": "L03", "moments": [{"option": "A"}, {"option": "B"}, {"option": "C"}]}]}
    state2 = {"submitted": {"at": "2026-10-24T10:00:00", "version": 1, "kind": "review"},
              "beats": {"L01": {"value": "approved"}, "L02": {"value": "approved", "option": "B"},
                        "L03": {"value": "approved"}}}
    assert wait_done.summary(state2, sb2) == "\n".join([
        "STORYBOARD DONE · T5 v1 · sent 2026-10-24T10:00:00",
        "REVIEW: make the next version",
        "approved: 01, 02 B",
        "versions picked:",
        "  02 (L02): approved B",
        "no version picked:",
        "  03 (L03): approved without a version (A, B or C): ask which one",
        "to change: none",
        "not reviewed: none",
        "general notes: none"])


# ---- "Pick your look": the optional look section (doodle + text style) ------------------------------------------------

FIX = Path(__file__).resolve().parent / "fixtures"


def look_sb():
    return json.loads((FIX / "look-demo" / "storyboard.json").read_text(encoding="utf-8"))


def test_look_absent_page_identical():
    sb = json.loads((FIX / "nolook-storyboard.json").read_text(encoding="utf-8"))
    golden = (FIX / "golden-nolook.html").read_text(encoding="utf-8", newline="")
    assert build.page(sb) == golden, "a storyboard without look renders byte-identical to before"


def test_look_page_and_check():
    sb = look_sb()
    folder = FIX / "look-demo"
    assert build.check(sb, folder) == []
    page = build.page(sb)
    assert page.count('class="look-card"') == 20 and "Pick your look" in page and 'id="wrap-look"' in page
    assert page.index('id="look"') < page.index('id="beats"') and page.index("Timeline") < page.index('id="look"')
    assert "Recommended: <b>Blueprint lab</b> + <b>Bubble 3D</b>" in page and "Use this" in page
    # refused: missing thumb file, repeated id, ids not in the lists
    bad = look_sb(); bad["look"]["doodles"][0]["thumb"] = "frames/nope.jpg"
    assert any("D1 thumb file is missing" in p for p in build.check(bad, folder))
    bad = look_sb(); bad["look"]["types"][1]["id"] = "T1"
    assert any("repeated type id T1" in p for p in build.check(bad, folder))
    bad = look_sb(); bad["look"]["recommended"]["doodle"] = "D99"
    assert any("recommended doodle 'D99'" in p for p in build.check(bad, folder))
    bad = look_sb(); bad["look"]["current"]["type"] = "T99"
    assert any("current type 'T99'" in p for p in build.check(bad, folder))


def test_look_server():
    sb = look_sb()
    with served(sb) as (root, port):
        ok = {"doodle": "D7", "type": "T2", "custom": "pastel"}
        assert call(port, "/api/look", ok)[0] == 200
        saved = read_json(root / "review.json")["look"]
        assert saved["doodle"] == "D7" and saved["type"] == "T2" and saved["custom"] == "pastel" and saved["at"]
        assert call(port, "/api/look", {**ok, "doodle": "D99"})[0] == 400
        assert call(port, "/api/look", {**ok, "type": "D7"})[0] == 400
        assert call(port, "/api/look", {**ok, "custom": "x" * 4001})[0] == 400
        assert call(port, "/api/look", {**ok, "custom": 5})[0] == 400
        assert call(port, "/api/look", ok, host="evil.example:80")[0] == 403
        assert call(port, "/api/look", {**ok, "custom": "pastel 2"})[0] == 200
        assert list((root / "review-backups").glob("review-*.json")), "a backup before the second write"
        # approve everything: go is refused while the look differs from current, a review is fine
        for b in sb["beats"]:
            assert call(port, "/api/review", {"beat": b["id"], "value": "approved"})[0] == 200
        code, body = call(port, "/api/submit", {"kind": "go"})
        assert code == 409 and body == {"error": "the new look is not drawn yet", "look_pending": True}
        assert call(port, "/api/submit", {"kind": "review"})[0] == 200
        # back to the current look, no custom: go is allowed
        assert call(port, "/api/look", {"doodle": "D2", "type": "T3", "custom": ""})[0] == 200
        assert call(port, "/api/submit", {"kind": "go"})[0] == 200
        # custom text alone is pending too
        assert call(port, "/api/look", {"doodle": "D2", "type": "T3", "custom": "more pastel"})[0] == 200
        assert call(port, "/api/submit", {"kind": "go"})[0] == 409
    nolook = json.loads((FIX / "nolook-storyboard.json").read_text(encoding="utf-8"))
    with served(nolook) as (root, port):
        assert call(port, "/api/look", {"doodle": "D1", "type": "T1", "custom": ""})[0] == 400, "no look in storyboard"


def test_look_waiter():
    sb = look_sb()
    sub = {"submitted": {"at": "2026-11-02T10:00:00", "version": 1, "kind": "review"}, "beats": {}}
    base = wait_done.summary(sub, {k: v for k, v in sb.items() if k != "look"})
    assert "look" not in base, "without look the output is what it always was"
    kept = wait_done.summary(sub, sb)
    assert kept == base + "\nlook: kept D2 Cozy loft + T3 Bubble 3D"
    picked = {**sub, "look": {"doodle": "D7", "type": "T2", "custom": "pastel", "at": "x"}}
    text = wait_done.summary(picked, sb)
    assert text.endswith("\nlook: picked D7 Greenhouse + T2 Marker hand-lettering (current: D2 Cozy loft + T3 Bubble 3D) "
                         '-> redraw in the next version\ncustom look request: "pastel"')
    same = {**sub, "look": {"doodle": "D2", "type": "T3", "custom": "", "at": "x"}}
    assert wait_done.summary(same, sb) == kept


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK: {name}")
