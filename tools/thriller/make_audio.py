"""Cut the dance's music loop out of a source track: LOOP_BARS bars (2 s each at 120 BPM) starting at a downbeat, shifted 0.25 s earlier (pac eases the first pose in over
0.25 s, so the animation runs 0.25 s behind the event and its first beat lands 0.25 s into the file), with a short equal-power crossfade baked into the seam: the first
SEAM seconds of the file are mixed with the audio that continues after the loop end, so the end of the file flows into its start without a click.

  python make_audio.py SRC OUT.mp3 --downbeat 270.0708 [--bars 8] [--bpm 120] [--lead 0.25] [--lufs -12.5 --tp -1.0]
"""
import argparse, os, sys
import numpy as np
sys.path.insert(0, r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\emote')
import prep_audio as pa

SR = pa.SR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--downbeat', type=float, required=True, help='time (s) of the downbeat that must land on the first pose of the dance loop')
    ap.add_argument('--bars', type=int, default=8)
    ap.add_argument('--bpm', type=float, default=120.0)
    ap.add_argument('--lead', type=float, default=0.25)
    ap.add_argument('--seam', type=float, default=0.025)
    ap.add_argument('--lufs', type=float, default=-12.5)
    ap.add_argument('--tp', type=float, default=-1.0)
    ap.add_argument('--bitrate', default='192k')
    a = ap.parse_args()
    x = pa.decode(a.src)
    loop_s = a.bars * 4 * 60.0 / a.bpm
    n = int(round(loop_s * SR))
    s0 = int(round((a.downbeat - a.lead) * SR))
    d = int(round(a.seam * SR))
    seg = x[s0:s0 + n].copy()
    cont = x[s0 + n:s0 + n + d]
    assert len(seg) == n and len(cont) == d, 'source too short for this window'
    u = np.arange(d) / float(d)
    seg[:d] = seg[:d] * np.sin(u * np.pi / 2)[:, None] + cont * np.cos(u * np.pi / 2)[:, None]
    i0, tp0 = pa.measure(seg)
    gain = min(a.lufs - i0, a.tp - tp0)
    print('loop %.4f s (%d samples) from %.4f s | before: %.1f LUFS, true peak %.1f dBFS | gain %+.2f dB' % (loop_s, n, a.downbeat - a.lead, i0, tp0, gain))
    seg = seg * 10 ** (gain / 20)
    pa.encode(seg, a.out, a.bitrate)
    y = pa.decode(a.out)
    i1, tp1 = pa.measure(y)
    print('output: %d samples = %.4f s | %.1f LUFS, true peak %.1f dBFS, clipped %d | %d bytes' % (len(y), len(y) / SR, i1, tp1, int((np.abs(y) >= 0.9999).sum()), os.path.getsize(a.out)))
    pa.seam_report(y, 'loop seam')


if __name__ == '__main__':
    main()
