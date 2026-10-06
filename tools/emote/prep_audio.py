"""Prep an emote's music for a pac3 `sound` part that loops next to a looping custom_animation.

  python prep_audio.py SRC.mp3 OUT.mp3 [--length 24.2667] [--stretch] [--rotate 0.25] [--lead 0.451] [--lufs -11.4 --tp -1.0 [--limit] | --gain -3]

  --length   exact length of the output loop in seconds (it should be a whole number of animation loops; the part loops the file)
  --stretch  reach --length by a pitch-preserving tempo change of the whole track (keeps the beat grid locked to the animation);
             without it the track is padded with silence / trimmed at the end
  --wrap-tail  when the source is longer than --length, mix the surplus (a reverb / fade tail) onto the start of the loop instead of discarding it,
               which is what you would hear if the file were retriggered every --length seconds with the tail ringing into the next hit
  --rotate   move the last N seconds to the front. pac eases the first pose in over 0.25 s, so the animation runs 0.25 s behind the
             moment the event fires; rotating a seamless loop by 0.25 s puts the music's downbeat on the animation's first pose
  --lufs/--tp  integrated loudness target and true-peak ceiling (a gain is derived from them)   --gain  fixed gain in dB
  --limit    with --lufs: do not cap the gain by the true peak, run a transparent peak limiter at --tp instead (for quiet masters)
  --lead     prepend N seconds of silence (an intro that must start later than the event: pac's 0.25 s ease-in plus ActMod's own delay);
             with --lead the --length is optional and defaults to lead + source length
Output: 44.1 kHz stereo CBR mp3, no ID3 tags, with the LAME/Info header (gapless length).
"""
import argparse, re, subprocess, sys
import numpy as np

SR = 44100


def run_ffmpeg(args, data=None):
    p = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-v', 'info'] + args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors='replace')[-2000:])
    return p.stdout, p.stderr.decode(errors='replace')


def decode(path, af=None):
    args = ['-i', path] + (['-af', af] if af else []) + ['-ar', str(SR), '-ac', '2', '-f', 'f32le', '-']
    out, _ = run_ffmpeg(args)
    return np.frombuffer(out, dtype='<f4').reshape(-1, 2).astype(np.float64)


def measure(x):
    """integrated loudness (LUFS) and true peak (dBTP) of float stereo samples via ffmpeg's ebur128."""
    _, err = run_ffmpeg(['-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-af', 'ebur128=peak=true', '-f', 'null', '-'], x.astype('<f4').tobytes())
    tail = err[err.rfind('Summary:'):]
    i = float(re.search(r'I:\s+(-?[\d.]+) LUFS', tail).group(1))
    tp = float(re.search(r'Peak:\s+(-?[\d.]+) dBFS', tail).group(1))
    return i, tp


def encode(x, out, bitrate='192k'):
    run_ffmpeg(['-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-c:a', 'libmp3lame', '-b:a', bitrate, '-ar', str(SR), '-ac', '2',
                '-map_metadata', '-1', '-write_id3v2', '0', out], x.astype('<f4').tobytes())


def seam_report(x, name):
    """ratio of the largest sample jump across the loop seam (end -> start) to the 99.9th percentile of the jumps inside the file."""
    mono = x.mean(axis=1)
    cat = np.concatenate([mono[-64:], mono[:64]])
    j = np.abs(np.diff(cat))[62:66].max()
    p = np.percentile(np.abs(np.diff(mono)), 99.9)
    print('%s: seam jump %.4f vs 99.9th percentile %.4f (%.2fx)' % (name, j, p, j / p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--length', type=float, default=None)
    ap.add_argument('--lead', type=float, default=0.0)
    ap.add_argument('--limit', action='store_true')
    ap.add_argument('--stretch', action='store_true')
    ap.add_argument('--wrap-tail', action='store_true')
    ap.add_argument('--rotate', type=float, default=0.0)
    ap.add_argument('--gain', type=float, default=None)
    ap.add_argument('--lufs', type=float, default=None)
    ap.add_argument('--tp', type=float, default=-1.0)
    ap.add_argument('--bitrate', default='192k')
    a = ap.parse_args()
    x = decode(a.src)
    n_out = int(round(a.length * SR)) if a.length else len(x) + int(round(a.lead * SR))
    print('source: %d samples = %.4f s' % (len(x), len(x) / SR))
    if a.stretch:
        ratio = len(x) / float(n_out)
        print('tempo ratio %.6f (%+.3f %%, %.1f cents if it were resampled)' % (ratio, (ratio - 1) * 100, 1200 * np.log2(ratio)))
        x = decode(a.src, 'atempo=%.9f' % ratio)
        print('after atempo: %d samples (target %d)' % (len(x), n_out))
    if a.wrap_tail and len(x) > n_out:
        tail = x[n_out:]
        x = x[:n_out].copy()
        k = min(len(tail), n_out)
        x[:k] += tail[:k]
        print('tail of %.3f s mixed onto the start of the loop' % (len(tail) / SR))
    if a.lead:
        x = np.concatenate([np.zeros((int(round(a.lead * SR)), 2)), x])
    if len(x) < n_out:
        x = np.concatenate([x, np.zeros((n_out - len(x), 2))])
    x = x[:n_out]
    if a.rotate:
        x = np.roll(x, int(round(a.rotate * SR)), axis=0)
    i, tp = measure(x)
    print('before gain: %.1f LUFS, true peak %.1f dBFS' % (i, tp))
    if a.lufs is not None:
        gain = (a.lufs - i) if a.limit else min(a.lufs - i, a.tp - tp)
    else:
        gain = a.gain if a.gain is not None else 0.0
    x = x * 10 ** (gain / 20)
    print('gain %+.2f dB' % gain)
    if a.limit:
        ceiling = 10 ** (a.tp / 20)
        out, _ = run_ffmpeg(['-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-af', 'alimiter=limit=%.4f:attack=3:release=60:level=disabled' % ceiling, '-f', 'f32le', '-'], x.astype('<f4').tobytes())
        y2 = np.frombuffer(out, dtype='<f4').reshape(-1, 2).astype(np.float64)
        print('limiter at %.1f dBFS: peak before %.3f after %.3f, %d samples changed by more than 1 dB' % (a.tp, np.abs(x).max(), np.abs(y2).max(), int((np.abs(np.abs(y2) - np.abs(x)) > 0.1 * np.abs(x)).sum())))
        x = y2[:len(x)]
    encode(x, a.out, a.bitrate)
    y = decode(a.out)
    i2, tp2 = measure(y)
    clipped = int((np.abs(y) >= 0.9999).sum())
    print('output: %d samples = %.4f s | %.1f LUFS, true peak %.1f dBFS, clipped samples %d' % (len(y), len(y) / SR, i2, tp2, clipped))
    seam_report(y, 'output file loop')


if __name__ == '__main__':
    main()
