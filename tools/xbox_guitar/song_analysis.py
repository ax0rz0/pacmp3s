"""analysis of the supplied recording (braindamage.mp3): level / silence, tempo and beat grid, chroma-based chord roots per beat.  CPU only (numpy + scipy)."""
import json
import math
import os
import subprocess
import sys

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.expanduser('~'), 'Downloads', 'braindamage.mp3')
SR = 22050
HOP = 512
NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def decode(path=SRC, sr=SR, start=None, dur=None):
    cmd = ['ffmpeg', '-v', 'error']
    if start is not None:
        cmd += ['-ss', '%.3f' % start]
    cmd += ['-i', path]
    if dur is not None:
        cmd += ['-t', '%.3f' % dur]
    cmd += ['-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def levels(x, sr=SR):
    win = sr // 2
    n = len(x) // win
    rms = np.sqrt(np.mean(x[:n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    loud = np.where(db > -50)[0]
    return db, (loud[0] * 0.5 if len(loud) else 0.0), ((loud[-1] + 1) * 0.5 if len(loud) else 0.0)


def onset_envelope(x, sr=SR, hop=HOP):
    f, t, Z = signal.stft(x, fs=sr, nperseg=2048, noverlap=2048 - hop, boundary=None, padded=False)
    M = np.abs(Z)
    sel = (f > 40) & (f < 6000)
    L = np.log1p(30.0 * M[sel])
    d = np.maximum(0.0, np.diff(L, axis=1))
    env = np.concatenate([[0.0], d.sum(axis=0)])
    env = env - np.convolve(env, np.ones(43) / 43, mode='same')           # local mean removal (1 s)
    env = np.maximum(env, 0.0)
    return env / (env.max() + 1e-9), t


def tempo_candidates(env, hop=HOP, sr=SR, lo=0.3, hi=4.2):
    e = env - env.mean()
    n = len(e)
    ac = np.correlate(e, e, mode='full')[n - 1:]
    ac = ac / (ac[0] + 1e-9)
    fr = hop / sr
    lags = np.arange(len(ac)) * fr
    sel = (lags >= lo) & (lags <= hi)
    idx = np.where(sel)[0]
    pk = [i for i in idx[1:-1] if ac[i] > ac[i - 1] and ac[i] >= ac[i + 1] and ac[i] > 0.05]
    pk.sort(key=lambda i: -ac[i])
    return [(float(lags[i]), float(ac[i])) for i in pk[:14]], ac, lags


def beat_track(env, period_s, hop=HOP, sr=SR, tight=60.0):
    """Ellis style dynamic programming beat tracker around a tempo period (seconds)"""
    fr = hop / sr
    p = period_s / fr
    w = np.exp(-0.5 * (np.arange(-int(p / 2), int(p / 2) + 1) / (p / 32.0)) ** 2)
    score = np.convolve(env, w, mode='same')
    n = len(score)
    cum = score.copy()
    back = -np.ones(n, dtype=int)
    for t in range(n):
        lo = int(round(t - 2 * p))
        hi = int(round(t - p / 2))
        if hi < 0:
            continue
        lo = max(lo, 0)
        if hi < lo:
            continue
        prev = np.arange(lo, hi + 1)
        pen = -tight * (np.log((t - prev) / p)) ** 2
        v = cum[prev] + pen
        j = int(np.argmax(v))
        if v[j] > 0:
            cum[t] = score[t] + v[j]
            back[t] = prev[j]
    # best end among the last period
    tail = np.arange(max(n - int(p), 0), n)
    t = int(tail[np.argmax(cum[tail])])
    beats = [t]
    while back[t] >= 0:
        t = back[t]
        beats.append(t)
    beats = np.array(beats[::-1], dtype=float) * fr
    return beats


def chroma_frames(x, sr=SR, nfft=8192, hop=2048):
    f, t, Z = signal.stft(x, fs=sr, nperseg=nfft, noverlap=nfft - hop, boundary=None, padded=False)
    M = np.abs(Z)
    sel = (f >= 60) & (f <= 1800)
    fs = f[sel]
    Msel = M[sel]
    midi = 69 + 12 * np.log2(fs / 440.0)
    # tuning: circular mean of the fractional pitch of the strongest peaks
    wts = Msel.sum(axis=1)
    frac = (midi - np.round(midi))
    ang = 2 * np.pi * frac
    tun = np.angle(np.sum(wts * np.exp(1j * ang))) / (2 * np.pi)
    pc = np.mod(np.round(midi - tun).astype(int), 12)
    C = np.zeros((len(t), 12))
    comp = np.log1p(20.0 * Msel)
    low = fs < 260
    B = np.zeros((len(t), 12))
    for k in range(12):
        m = pc == k
        C[:, k] = comp[m].sum(axis=0)
        B[:, k] = comp[m & low].sum(axis=0)
    return t, C, B, tun


def main():
    x = decode()
    print('decoded %.1f s at %d Hz' % (len(x) / SR, SR))
    db, t0, t1 = levels(x)
    print('first sound above -50 dBFS (rms 0.5 s windows) at %.1f s, last at %.1f s of %.1f' % (t0, t1, len(x) / SR))
    print('level per 10 s (dBFS rms):', ' '.join('%.0f' % db[i:i + 20].mean() for i in range(0, len(db), 20)))
    env, tt = onset_envelope(x)
    cands, ac, lags = tempo_candidates(env)
    print('autocorrelation peaks (lag s, strength, BPM if one beat):')
    for lag, s in cands:
        print('   %.3f s  %.2f   -> %.1f BPM' % (lag, s, 60.0 / lag))
    np.save(os.path.join(HERE, 'out', 'song_env.npy'), env)


if __name__ == '__main__':
    main()
