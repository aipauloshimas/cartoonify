"""The safe zone is defined twice (kit/cartoon.js for the page, scripts/cartoonify.py for the layout): they must agree."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import cartoonify  # noqa: E402


def js_zone(w, h):
    js = (f"global.window=undefined;require('vm').runInThisContext(require('fs').readFileSync({json.dumps(str(ROOT / 'kit' / 'cartoon.js'))},'utf8'));"
          f"console.log(JSON.stringify(Cartoon.safeZone({w},{h})))")
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)


def test_reels_zone_at_1080x1920():
    assert cartoonify.safe_zone(1080, 1920) == {"x0": 60, "y0": 220, "x1": 960, "y1": 1500, "typeTop": 230}


def test_python_and_js_agree():
    for w, h in ((1080, 1920), (2160, 3840), (720, 1280), (1920, 1080), (1080, 1080)):
        assert cartoonify.safe_zone(w, h) == js_zone(w, h), (w, h)
