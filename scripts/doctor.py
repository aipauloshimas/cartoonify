"""doctor.py - check (and, after confirmation, install) everything the Cartoonify skill needs.

  python scripts/doctor.py                       check only, print the table + install plan (exit 1 if anything is missing)
  python scripts/doctor.py --json                machine-readable result
  python scripts/doctor.py --install [--yes]     show the plan, ask "Install these N items? [y/N]" (needs a TTY;
                                                 without a TTY it refuses unless --yes is passed)
  python scripts/doctor.py --install --only ffmpeg,model   limit the plan (names: ffmpeg, node, hyperframes,
                                                 python-packages, chromium, model)
  python scripts/doctor.py --pretend-missing ffmpeg,model --dry-run   test aid: mark items missing, print the
                                                 commands instead of running them

Checks: ffmpeg+ffprobe, Node >= 18 + npx, HyperFrames CLI, Python >= 3.9 + pip, python packages (numpy, cv2,
onnxruntime, whisper, playwright), Playwright Chromium, RVM model file. macOS and Windows; Linux best effort.
Stdlib only. Never installs without --install and a yes.
"""
import argparse, json, os, platform, re, shutil, subprocess, sys, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"
MODEL = os.path.expanduser("~/.cache/rvm/rvm_mobilenetv3_fp32.onnx")
MODEL_URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx"
PKGS = {"numpy": "numpy", "cv2": "opencv-python", "onnxruntime": "onnxruntime",
        "whisper": "openai-whisper", "playwright": "playwright"}
ORDER = ["ffmpeg", "node", "hyperframes", "python", "python-packages", "chromium", "model"]
EXTRA_DIRS = ([os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"), r"C:\Program Files\nodejs"]
              if WIN else ["/opt/homebrew/bin", "/usr/local/bin"])


def which(name):
    p = shutil.which(name)
    if p:
        return p
    for d in EXTRA_DIRS:
        for ext in ([".exe", ".cmd", ""] if WIN else [""]):
            f = os.path.join(d, name + ext)
            if os.path.isfile(f):
                return f
    return None


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return -1, str(e)


def item(name, ok, version="", fix=""):
    return {"name": name, "ok": ok, "version": version, "fix": fix}


def pm_fix(win_cmd, mac_cmd):
    return win_cmd if WIN else mac_cmd


def check_ffmpeg():
    ff, fp = which("ffmpeg"), which("ffprobe")
    fix = pm_fix("winget install --id Gyan.FFmpeg -e", "brew install ffmpeg")
    if not (ff and fp):
        return item("ffmpeg", False, "missing: " + ", ".join(n for n, p in (("ffmpeg", ff), ("ffprobe", fp)) if not p), fix)
    _, out = run([ff, "-version"])
    return item("ffmpeg", True, (out.splitlines() or [""])[0].replace("ffmpeg version ", "")[:40] + " (+ffprobe)", fix)


def check_node():
    node, npx = which("node"), which("npx")
    fix = pm_fix("winget install --id OpenJS.NodeJS.LTS -e", "brew install node")
    if not (node and npx):
        return item("node", False, "node or npx not found", fix)
    _, out = run([node, "--version"])
    m = re.match(r"v(\d+)", out)
    if not m or int(m.group(1)) < 18:
        return item("node", False, "old: " + out + " (need >= 18)", fix)
    return item("node", True, out + " + npx", fix)


def check_hyperframes():
    npx = which("npx")
    if not npx:
        return item("hyperframes", False, "needs npx (install node first)", "npm i -g hyperframes (optional; npx fetches it)")
    code, out = run([npx, "--yes", "hyperframes", "--version"], timeout=180)
    ver = (out.splitlines() or [""])[-1][:40]
    return item("hyperframes", code == 0 and bool(ver), ver if code == 0 else "failed: " + out[-80:],
                "npm i -g hyperframes (optional; npx fetches it)")


def check_python():
    ok = sys.version_info >= (3, 9)
    code, out = run([sys.executable, "-m", "pip", "--version"], timeout=120)
    pip = code == 0
    v = platform.python_version() + (", pip " + out.split()[1] if pip and len(out.split()) > 1 else ", pip MISSING")
    return item("python", ok and pip, v, "install Python 3.9+ from https://python.org; then: python -m ensurepip")


def check_packages():
    missing, found = [], []
    for mod, pip in PKGS.items():
        code, _ = run([sys.executable, "-c", "import " + mod], timeout=90)
        (found if code == 0 else missing).append(mod if code == 0 else pip)
    fix = "%s -m pip install --user %s" % (sys.executable, " ".join(missing))
    return item("python-packages", not missing, ("ok: " + ", ".join(found)) if not missing else "missing: " + ", ".join(missing), fix)


PW_TEST = ("from playwright.sync_api import sync_playwright\n"
           "with sync_playwright() as p:\n    b = p.chromium.launch(headless=True); print(b.version); b.close()\n")


def check_chromium():
    fix = "%s -m playwright install chromium" % sys.executable
    code, out = run([sys.executable, "-c", PW_TEST], timeout=150)
    if code != 0:
        return item("chromium", False, "cannot launch: " + (out.splitlines() or ["timeout"])[-1][:70], fix)
    return item("chromium", True, "chromium " + out.splitlines()[-1], fix)


def check_model():
    fix = "download %s -> %s" % (MODEL_URL, MODEL)
    if not os.path.isfile(MODEL):
        return item("model", False, "not found: " + MODEL, fix)
    mb = os.path.getsize(MODEL) / 1e6
    return item("model", 10 <= mb <= 20, "%.1f MB at %s" % (mb, MODEL) + ("" if 10 <= mb <= 20 else " (wrong size)"), fix)


CHECKS = [check_ffmpeg, check_node, check_hyperframes, check_python, check_packages, check_chromium, check_model]


def run_checks(pretend):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(len(CHECKS)) as ex:  # checks are independent and slow (npx, torch import): run together
        results = list(ex.map(lambda f: f(), CHECKS))
    items = []
    for it in results:
        if it["name"] in pretend and it["ok"]:
            it = dict(it, ok=False, version="(pretended missing) " + it["version"])
        items.append(it)
    return items


def table(items):
    print("%-16s %-8s %s" % ("ITEM", "STATUS", "FOUND"))
    for it in items:
        print("%-16s %-8s %s" % (it["name"], "OK" if it["ok"] else "MISSING", it["version"]))


# ---- install plan: list of (item name, description, argv list or callable) ----
def build_plan(missing_names, only=None):
    plan = []
    for n in ORDER:
        if n not in missing_names or (only and n not in only):
            continue
        py = sys.executable
        if n == "ffmpeg":
            cmd = ["winget", "install", "--id", "Gyan.FFmpeg", "-e"] if WIN else ["brew", "install", "ffmpeg"]
            plan.append((n, "ffmpeg + ffprobe (about 100-200 MB)", cmd))
        elif n == "node":
            cmd = ["winget", "install", "--id", "OpenJS.NodeJS.LTS", "-e"] if WIN else ["brew", "install", "node"]
            plan.append((n, "Node.js LTS + npx (about 30-80 MB)", cmd))
        elif n == "hyperframes":
            plan.append((n, "HyperFrames CLI, fetched by npx on first use (about 100 MB with Chromium)",
                         ["npx", "--yes", "hyperframes", "--version"]))
        elif n == "python-packages":
            plan.append((n, "python packages numpy, opencv-python, onnxruntime, openai-whisper, playwright (about 1 GB incl. torch)",
                         [py, "-m", "pip", "install", "--user"] + list(PKGS.values())))
        elif n == "chromium":
            plan.append((n, "Playwright Chromium (about 150 MB)", [py, "-m", "playwright", "install", "chromium"]))
        elif n == "model":
            plan.append((n, "RVM model, about 15 MB, from " + MODEL_URL, ("download", MODEL_URL, MODEL)))
        elif n == "python":
            print("NOTE: Python itself must be installed by hand: https://python.org")
    return plan


def fmt(cmd):
    return "download %s -> %s" % (cmd[1], cmd[2]) if isinstance(cmd, tuple) else " ".join(cmd)


def download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    urllib.request.urlretrieve(url, part)
    os.replace(part, dest)


def execute(plan, dry):
    for name, desc, cmd in plan:
        print("\n> %s: %s" % (name, fmt(cmd)))
        if dry:
            continue
        if isinstance(cmd, tuple):
            download(cmd[1], cmd[2])
            continue
        exe = which(cmd[0]) if cmd[0] not in (sys.executable,) else cmd[0]
        if not exe:
            print("  cannot run: '%s' not found." % cmd[0])
            continue
        r = subprocess.run([exe] + cmd[1:])
        print("  exit code %d" % r.returncode)


def main():
    ap = argparse.ArgumentParser(description="Cartoonify doctor")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pretend-missing", default="")
    a = ap.parse_args()
    pretend = {x.strip() for x in a.pretend_missing.split(",") if x.strip()}
    only = {x.strip() for x in a.only.split(",") if x.strip()} or None
    osname = "Windows %s" % platform.release() if WIN else ("macOS %s" % platform.mac_ver()[0] if MAC else platform.system())

    items = run_checks(pretend)
    if a.json:
        print(json.dumps({"ok": all(i["ok"] for i in items), "os": osname, "items": items}, indent=2))
        return 0 if all(i["ok"] for i in items) else 1

    print("Cartoonify doctor (%s, Python %s)\n" % (osname, platform.python_version()))
    table(items)
    missing = [i["name"] for i in items if not i["ok"]]
    if not missing:
        print("\nAll good.")
        return 0

    pm = "winget" if WIN else "brew"
    if ({"ffmpeg", "node"} & set(missing)) and not shutil.which(pm) and not (WIN and which("winget")):
        print("\n%s not found. Get it first: %s" % (pm, "App Installer from the Microsoft Store" if WIN else "https://brew.sh"))
    plan = build_plan(set(missing), only)
    print("\nInstall plan (%d item%s):" % (len(plan), "" if len(plan) == 1 else "s"))
    for name, desc, cmd in plan:
        print("  - %s: %s\n      %s" % (name, desc, fmt(cmd)))
    if not a.install:
        print("\nCheck only. To install: python scripts/doctor.py --install")
        return 1
    if not plan:
        return 1
    if not a.yes:
        # no keyboard (Claude Code's shell): the user answers in the chat instead. On Windows the null device claims to
        # be a terminal, so an empty read counts as no keyboard too
        try:
            answer = input("\nInstall these %d items? [y/N] " % len(plan)) if sys.stdin.isatty() else None
        except EOFError:
            answer = None
        if answer is None:
            print("\nNo keyboard here. Ask the user first, then run doctor.py --install --yes")
            return 1
        if answer.strip().lower() not in ("y", "yes"):
            print("Cancelled.")
            return 1
    execute(plan, a.dry_run)
    if a.dry_run:
        print("\nDry run: nothing was executed.")
        return 1
    if WIN:
        print("\nAfter winget installs, a new terminal may be needed for PATH.")
    print("\nRe-checking:\n")
    items = run_checks(set())
    table(items)
    return 0 if all(i["ok"] for i in items) else 1


if __name__ == "__main__":
    sys.exit(main())
