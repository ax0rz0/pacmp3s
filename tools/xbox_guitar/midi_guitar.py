"""what the MIDI says about the guitar part of Brain Damage: pluck onsets, and per bar the fretboard region the left hand has to be in"""
import collections
import mido
import numpy as np

PATH = r'C:\Users\poopy\Downloads\Pink Floyd - Brain Damage .mid'
MIDI_BPM = 130.11
SPB = 60.0 / MIDI_BPM                       # one MIDI beat in seconds (0.4611 s); the song itself is at half this tempo
OPEN = [40, 45, 50, 55, 59, 64]             # E A D G B e
NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def guitar_notes():
    mid = mido.MidiFile(PATH)
    tr = mid.tracks[4]
    ticks = 0
    on = {}
    notes = []
    for m in tr:
        ticks += m.time
        t = ticks / mid.ticks_per_beat * SPB
        if m.type == 'note_on' and m.velocity > 0:
            on[m.note] = t
        elif m.type in ('note_off', 'note_on'):
            if m.note in on:
                notes.append((on.pop(m.note), t, m.note))
    notes.sort()
    return notes


def fret_of(note):
    """lowest fret on any string that can play the note (0 = open)"""
    best = None
    for s, o in enumerate(OPEN):
        f = note - o
        if 0 <= f <= 12 and (best is None or f < best[1]):
            best = (s, f)
    return best


def bars(notes, beats=4):
    L = beats * SPB
    out = collections.defaultdict(list)
    for t0, t1, n in notes:
        out[int(t0 // L)].append(n)
    res = []
    for b in range(max(out) + 1):
        ns = out.get(b, [])
        frets = [fret_of(n)[1] for n in ns if fret_of(n) and fret_of(n)[1] > 0]
        centre = float(np.median(frets)) if frets else 2.0
        res.append((b * L, (b + 1) * L, centre, sorted(set(ns))))
    return res


def segments(notes, tol=1.6):
    """merge consecutive bars whose hand position differs by less than tol frets"""
    bs = bars(notes)
    seg = []
    cur = [bs[0]]
    for b in bs[1:]:
        if abs(b[2] - np.mean([c[2] for c in cur])) < tol:
            cur.append(b)
        else:
            seg.append(cur); cur = [b]
    seg.append(cur)
    return [(s[0][0], s[-1][1], float(np.mean([c[2] for c in s])), sorted(set(n for c in s for n in c[3]))) for s in seg]


if __name__ == '__main__':
    notes = guitar_notes()
    print('notes', len(notes), 'span %.1f .. %.1f s' % (notes[0][0], notes[-1][1]))
    seg = segments(notes)
    print('hand-position segments:', len(seg))
    for t0, t1, c, ns in seg[:30]:
        print('  %6.1f - %6.1f s  fret %.1f   notes %s' % (t0, t1, c, ' '.join(NAMES[n % 12] + str(n // 12 - 1) for n in ns[:8])))
