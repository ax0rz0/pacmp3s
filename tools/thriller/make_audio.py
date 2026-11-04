"""Cut the dance's music loop out of a source track (only the needed window is decoded, so a 10 minute file costs no memory).

  python make_audio.py SRC OUT.mp3 --downbeat 353.54 --loop 32.565868 [--lead 0.25] [--seam 0.025] [--lufs -12.5 --tp -1.0] [--bitrate 160k]

  --downbeat  time (s) in SRC of the downbeat that must land on the first pose of the dance loop
  --loop      exact loop length in seconds (a whole number of dance loops: 64 beats = two 32-beat loops; measure it from the track, e.g. the autocorrelation peak of a repeating loop)
  --lead      the downbeat sits this far into the file: pac eases the first pose in over 0.25 s, so the animation runs 0.25 s behind the event (and the sound)
  --seam      equal-power crossfade baked into the loop seam: the first SEAM seconds of the file are mixed with the audio that continues after the loop end, so end -> start has no click
Output: 44.1 kHz stereo CBR mp3, no ID3 tags, LAME/Info header (gapless length); the file is exactly round(loop * 44100) samples long.
"""
import argparse, os, subprocess, sys
import numpy as np
sys.path.insert(0, r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\emote')
import prep_audio as pa

SR = pa.SR


def decode_window(src, t0, dur):
    args = ['ffmpeg', '-hide_banner', '-nostats', '-v', 'error', '-ss', '%.6f' % t0, '-t', '%.6f' % dur, '-i', src, '-ar', str(SR), '-ac', '2', '-f', 'f32le', '-']
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors='replace')[-1500:])
    return np.frombuffer(p.stdout, dtype='<f4').reshape(-1, 2).astype(np.float64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--downbeat', type=float, required=True)
    ap.add_argument('--loop', type=float, required=True)
    ap.add_argument('--lead', type=float, default=0.25)
    ap.add_argument('--seam', type=float, default=0.025)
    ap.add_argument('--lufs', type=float, default=-12.5)
    ap.add_argument('--tp', type=float, default=-1.0)
    ap.add_argument('--bitrate', default='160k')
    a = ap.parse_args()
    n = int(round(a.loop * SR))
    d = int(round(a.seam * SR))
    start = a.downbeat - a.lead
    pre = 0.1
    x = decode_window(a.src, start - pre, a.loop + a.seam + pre + 0.2)
    s0 = int(round(pre * SR))
    seg = x[s0:s0 + n].copy()
    cont = x[s0 + n:s0 + n + d]
    assert len(seg) == n and len(cont) == d, 'source too short for this window (%d, %d)' % (len(seg), len(cont))
    u = np.arange(d) / float(d)
    seg[:d] = seg[:d] * np.sin(u * np.pi / 2)[:, None] + cont * np.cos(u * np.pi / 2)[:, None]
    i0, tp0 = pa.measure(seg)
    gain = min(a.lufs - i0, a.tp - tp0)
    print('loop %.6f s (%d samples) cut from %.4f s | before: %.1f LUFS, true peak %.1f dBFS | gain %+.2f dB' % (a.loop, n, start, i0, tp0, gain))
    seg = seg * 10 ** (gain / 20)
    pa.encode(seg, a.out, a.bitrate)
    y = pa.decode(a.out)
    i1, tp1 = pa.measure(y)
    print('output: %d samples = %.6f s | %.1f LUFS, true peak %.1f dBFS, clipped %d | %d bytes' % (len(y), len(y) / SR, i1, tp1, int((np.abs(y) >= 0.9999).sum()), os.path.getsize(a.out)))
    pa.seam_report(y, 'loop seam')


if __name__ == '__main__':
    main()
