"""quick previews straight from a choreography module's Timeline through the solver: pose sheets (any view) and a looping GIF (CPU only, small)"""
import importlib
import io
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

import thr_core as tc
import thr_fig as tf

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
os.makedirs(OUT, exist_ok=True)
CH = {'player': ('ethics', 'player'), 'zombie': ('zombie', 'zombie')}
FORM = (('zombie', (-14, 52), '#4a7c3a'), ('player', (0, 0), '#2b6cb0'), ('zombie', (-14, -52), '#4a7c3a'))


class Prev:
    def __init__(self, mod):
        self.td = mod
        self.tl = mod.Timeline()
        self.rigs = {k: tc.rig_for(r) for k, (r, s) in CH.items()}
        self.sol = {k: tc.Solver(self.rigs[k], mod.style_for(s)) for k, (r, s) in CH.items()}

    def figs(self, beat, form=FORM):
        P = self.tl.pose(beat)
        cache = {}
        out = []
        for kind, off, col in form:
            if kind not in cache:
                M, trl, AR, AP = self.sol[kind].solve(P)
                cache[kind] = (AR, AP)
            AR, AP = cache[kind]
            out.append((self.rigs[kind], AR, AP, col, off, 0))
        return out

    def sheet(self, tag, beats, view='q', ncols=4, title='', size=(3.1, 3.2), xr=(-85, 85), yr=(-3, 78), dpi=80, form=FORM):
        items = [('beat %g' % b, self.figs(b, form)) for b in beats]
        tf.grid(os.path.join(OUT, tag + '.png'), items, view=view, ncols=ncols, size=size, dpi=dpi, title=title, xr=xr, yr=yr)
        return os.path.join(OUT, tag + '.png')

    def gif(self, tag, view='q', fps=12, step_beats=None, size=(4.2, 2.9), dpi=80, xr=(-92, 92), yr=(-3, 76), loops=1):
        n = int(self.td.LOOP_BEATS * self.td.BEAT * fps) * loops
        fig, ax = plt.subplots(figsize=size)
        frames = []
        for i in range(n):
            beat = i / fps / self.td.BEAT
            ax.clear()
            for rig, AR, AP, col, off, yaw in self.figs(beat):
                tf.draw(ax, rig, AR, AP, view, col, off, yaw=yaw, lw=3.0)
            ax.set_aspect('equal')
            ax.set_xlim(*xr)
            ax.set_ylim(*yr)
            ax.plot(xr, [0, 0], '-', color='0.6', lw=1)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title('beat %.1f   (%d / %d)' % (beat % self.td.LOOP_BEATS, int(beat % self.td.LOOP_BEATS) + 1, self.td.LOOP_BEATS), fontsize=8, pad=2)
            fig.tight_layout(pad=0.4)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi)
            buf.seek(0)
            frames.append(Image.open(buf).convert('P', palette=Image.ADAPTIVE, colors=48))
        plt.close(fig)
        path = os.path.join(OUT, tag + '.gif')
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(round(1000 / fps)), loop=0, optimize=True, disposal=2)
        return path


if __name__ == '__main__':
    modname = sys.argv[1] if len(sys.argv) > 1 else 'thr_dance2'
    mod = importlib.import_module(modname)
    pv = Prev(mod)
    t0 = time.time()
    tag = sys.argv[2] if len(sys.argv) > 2 else 'v2'
    for i, (a, b) in enumerate(((0, 8), (8, 16), (16, 24), (24, 32))):
        pv.sheet('%s_q_%d' % (tag, i + 1), [x for x in range(a, b)], view='q', title='%s beats %d-%d (3/4 view: zombie | player | zombie)' % (tag, a, b - 1))
    print('sheets %.1fs' % (time.time() - t0))
