"""The cut-out person with a marker outline and a soft contact shadow, as one VP9-alpha video for the edit: the RVM
cutout laid over its own outline. The outline boils with the room's lines (a new wobble 8 times a second at any frame
rate). One alpha video instead of two halves what the renderer has to unpack.

  python outline_layer.py CUT.webm OUT.webm [--ink #2F2219] [--thick 9] [--shadow 0.30] [--layer-only]

--layer-only writes the outline and shadow alone (to sit under the cutout as a separate layer).

Sizes are for a 1080-wide short side and scale with the video."""
import argparse, json, subprocess
import cv2
import numpy as np


def probe(path):
    s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                                   "-of", "json", path], capture_output=True, text=True, check=True).stdout)["streams"][0]
    return s["width"], s["height"], s["r_frame_rate"]


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--ink", default="#2F2219")
    ap.add_argument("--thick", type=float, default=9, help="marker width in px at a 1080 short side, outside the body")
    ap.add_argument("--shadow", type=float, default=0.30, help="contact shadow opacity (0 = none)")
    ap.add_argument("--layer-only", action="store_true", help="the outline and shadow alone, without the person")
    a = ap.parse_args()
    W, H, fps = probe(a.src)
    u = min(W, H) / 1080
    num, den = (int(x) for x in fps.split("/"))
    every = max(1, round(num / den / 8))                      # frames per boil step: 8 new wobbles a second
    thick, wob = max(2, round(a.thick * u)), 3.0 * u
    off, blur = (round(16 * u), round(22 * u)), 15 * u

    def noise_maps(seed):
        rng = np.random.default_rng(seed)
        small = rng.standard_normal((2, max(2, H // 40), max(2, W // 40))).astype(np.float32)
        big = [cv2.resize(s, (W, H), interpolation=cv2.INTER_CUBIC) for s in small]
        gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        return gx + big[0] * wob, gy + big[1] * wob

    maps = [noise_maps(s) for s in range(4)]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * thick + 1, 2 * thick + 1))
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", a.src, "-fps_mode", "passthrough", "-f", "rawvideo",
                            "-pix_fmt", "rgba", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", fps, "-i", "-",
                            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "18" if a.layer_only else "14", "-b:v", "0", "-row-mt", "1", "-deadline", "good",
                            "-cpu-used", "4", "-auto-alt-ref", "0", "-an", a.dst], stdin=subprocess.PIPE)
    rgb = np.empty((H, W, 3), np.uint8); rgb[:] = hex_rgb(a.ink)
    n = 0
    while True:
        buf = dec.stdout.read(W * H * 4)
        if len(buf) < W * H * 4:
            break
        px = np.frombuffer(buf, np.uint8).reshape(H, W, 4)
        al = px[..., 3]
        body = (al > 127).astype(np.uint8) * 255
        soft = (al > 12).astype(np.uint8) * 255                       # the full extent, motion blur included
        mx, my = maps[(n // every) % 4]
        line = cv2.remap(cv2.dilate(soft, kernel), mx, my, cv2.INTER_LINEAR)
        line = cv2.GaussianBlur(line, (0, 0), 1.2 * u)
        sh = np.zeros_like(body, dtype=np.float32)
        if a.shadow > 0:   # a soft shadow: blurred at a quarter of the size (the same look, a fraction of the time)
            dx, dy = off
            sh8 = np.zeros_like(body); sh8[dy:, dx:] = body[:H - dy, :W - dx]
            small = cv2.resize(sh8, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
            sh = cv2.resize(cv2.GaussianBlur(small, (0, 0), blur / 4), (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32) * a.shadow
        # the line runs on under the body (the cutout covers it), so the cutout's soft edge sits on ink, never on the wall;
        # only the shadow is kept off the body and its blur
        outside = 1 - cv2.GaussianBlur(soft, (0, 0), 1.0).astype(np.float32) / 255
        alpha = np.maximum(line.astype(np.float32), sh * outside).clip(0, 255)
        if a.layer_only:
            enc.stdin.write(np.dstack([rgb, alpha.astype(np.uint8)]).tobytes())
        else:   # the person over the outline (straight alpha "over")
            ca, la = al.astype(np.float32)[..., None] / 255, alpha[..., None] / 255
            out_a = ca + la * (1 - ca)
            col = (px[..., :3].astype(np.float32) * ca + rgb.astype(np.float32) * la * (1 - ca)) / np.maximum(out_a, 1e-6)
            enc.stdin.write(np.dstack([col.clip(0, 255), out_a * 255]).astype(np.uint8).tobytes())
        n += 1
    enc.stdin.close(); enc.wait(); dec.wait()
    print(f"outline_layer: {n} frames -> {a.dst}")


if __name__ == "__main__":
    main()
