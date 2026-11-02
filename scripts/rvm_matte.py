"""rvm_matte.py - cut the PERSON (people, hands, arms) out of a video with Robust Video Matting (RVM).

Why RVM: it keeps fast, motion-blurred hands and hair whole, where single-image background removers chew edges and leave
halos.

  python ~/.claude/tools/rvm/rvm_matte.py IN.mp4 OUT.webm [--matte-only] [--downsample R] [--warmup N]
                                                          [--floor LO HI] [--crf Q]

Output (default): VP9 webm with alpha (yuva420p), same size, fps and frame count as IN, ready to lay over the plate.
  - colour: the original pixel in the core (alpha ~1), RVM's `fgr` on the soft edges (clean colour, no background
    fringe round blurred fingers);
  - alpha below LO is cut, ramping back to the raw alpha by HI (default 0.03 0.10), so no faint veil of the
    background lands over whatever sits under the cutout.
--matte-only: a grayscale video of the alpha instead (white = person), e.g. for a luma matte.
--downsample: RVM's internal ratio; default min(1, 576 / long side) = 0.3 for 1080x1920 (right for a visible person).
  For a POV shot where only arms/hands are in frame (no body), use --downsample 0.5: at 0.3 RVM kept the fist but lost
  the forearm, wrist, watch and sleeve; at 0.5 the whole arm came out clean.
The recurrent state is warmed on the first N frames (default 12) before the real pass.
Model: ~/.cache/rvm/rvm_mobilenetv3_fp32.onnx (github.com/PeterL1n/RobustVideoMatting, release v1.0.0, ~15 MB),
run with onnxruntime on CPU (about 0.6 s per 1080x1920 frame).
"""
import argparse, json, os, subprocess, sys
import numpy as np

MODEL = os.path.expanduser('~/.cache/rvm/rvm_mobilenetv3_fp32.onnx')
MODEL_URL = 'https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx'


def probe(path, count=False):
    args = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
            'stream=width,height,r_frame_rate' + (',nb_read_frames' if count else ''), '-of', 'json', path]
    if count:
        args[1:1] = ['-count_frames']
    s = json.loads(subprocess.run(args, capture_output=True, text=True, check=True).stdout)['streams'][0]
    return s


def frames(path, w, h):
    # passthrough: exactly the decoded frames (ffmpeg's default may duplicate/drop frames to force a constant rate,
    # e.g. on a stream-copied trim with an edit list), so the matte stays frame-for-frame with the source
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = w * h * 3
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                break
            yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
    finally:
        p.stdout.close()
        p.kill()
        p.wait()


def main():
    ap = argparse.ArgumentParser(description='Cut the person out of a video with Robust Video Matting.')
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--matte-only', action='store_true', help='write a grayscale alpha video instead of RGBA')
    ap.add_argument('--downsample', type=float, default=None)
    ap.add_argument('--warmup', type=int, default=12)
    ap.add_argument('--floor', type=float, nargs=2, default=(0.03, 0.10), metavar=('LO', 'HI'))
    ap.add_argument('--crf', type=int, default=12)
    a = ap.parse_args()

    if not os.path.exists(MODEL):
        sys.exit('rvm_matte: model missing at %s\n  It is a ~15 MB download from %s\n  Run doctor.py --install to download it.'
                 % (MODEL, MODEL_URL))
    import onnxruntime as ort

    s = probe(a.src)
    W, H, fps = int(s['width']), int(s['height']), s['r_frame_rate']
    dr = np.array([a.downsample or min(1.0, 576.0 / max(W, H))], np.float32)
    lo, hi = a.floor
    so = ort.SessionOptions(); so.intra_op_num_threads = os.cpu_count() or 4
    sess = ort.InferenceSession(MODEL, so, providers=['CPUExecutionProvider'])
    rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4

    def step(img, rec):
        x = (img.astype(np.float32) / 255).transpose(2, 0, 1)[None]
        fgr, pha, *rec = sess.run(None, {'src': x, 'r1i': rec[0], 'r2i': rec[1], 'r3i': rec[2], 'r4i': rec[3],
                                         'downsample_ratio': dr})
        return fgr[0].transpose(1, 2, 0), pha[0, 0], rec

    for k, img in enumerate(frames(a.src, W, H)):        # warm the recurrent state on the first frames
        _, _, rec = step(img, rec)
        if k + 1 >= a.warmup:
            break

    if a.matte_only:
        enc_in = ['-f', 'rawvideo', '-pix_fmt', 'gray', '-s', '%dx%d' % (W, H), '-r', fps, '-i', '-']
        ext = os.path.splitext(a.dst)[1].lower()
        enc_out = (['-c:v', 'libx264', '-crf', str(a.crf), '-pix_fmt', 'yuv420p'] if ext in ('.mp4', '.mov')
                   else ['-c:v', 'libvpx-vp9', '-crf', str(a.crf), '-b:v', '0', '-pix_fmt', 'yuv420p', '-row-mt', '1'])
    else:
        enc_in = ['-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '%dx%d' % (W, H), '-r', fps, '-i', '-']
        enc_out = ['-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-crf', str(a.crf), '-b:v', '0', '-row-mt', '1',
                   '-deadline', 'good', '-cpu-used', '2', '-auto-alt-ref', '0']
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y'] + enc_in + enc_out + ['-an', a.dst], stdin=subprocess.PIPE)
    n = 0
    for img in frames(a.src, W, H):
        fgr, pha, rec = step(img, rec)
        al = np.clip(pha, 0, 1)
        al = np.where(al < lo, 0, np.where(al < hi, (al - lo) / (hi - lo) * al, al))
        a8 = (al * 255 + 0.5).astype(np.uint8)
        if a.matte_only:
            enc.stdin.write(a8.tobytes())
        else:
            w = np.clip((al - 0.9) / 0.08, 0, 1)[..., None]      # core: original pixel; edge: RVM's clean colour
            rgb = img.astype(np.float32) * w + np.clip(fgr * 255, 0, 255) * (1 - w)
            enc.stdin.write(np.dstack([rgb.astype(np.uint8), a8]).tobytes())
        n += 1
        if n % 48 == 0:
            print('rvm_matte: %d frames' % n, file=sys.stderr, flush=True)
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit('rvm_matte: ffmpeg encode failed')

    src_n = int(probe(a.src, count=True)['nb_read_frames'])
    dec = ['-c:v', 'libvpx-vp9'] if a.dst.lower().endswith('.webm') else []
    out = json.loads(subprocess.run(['ffprobe', '-v', 'error'] + dec + ['-count_frames', '-select_streams', 'v:0',
                                     '-show_entries', 'stream=width,height,nb_read_frames', '-of', 'json', a.dst],
                                    capture_output=True, text=True, check=True).stdout)['streams'][0]
    ok = int(out['nb_read_frames']) == src_n == n and int(out['width']) == W and int(out['height']) == H
    print('rvm_matte: %s %dx%d @%s, %d frames (source %d) -> %s' % ('OK' if ok else 'MISMATCH', W, H, fps, n, src_n, a.dst))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
