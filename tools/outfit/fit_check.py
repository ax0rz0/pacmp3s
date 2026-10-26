import sys
sys.path.insert(0, '.')
import numpy as np
import adv_scene as asn
import make_adv_net as man
import run_donor_preview as rdp
from ethics_acc import Surface
d, tr, P, N = rdp.load()
names = ('Head', 'Lipstick', 'Mouth', 'Cyberware', 'EyeMakeup', 'Pimples')
sel = np.isin(tr['slot'], [d.tex.index(n) for n in names])
S_d = Surface(P[sel])
sc = asn.Scene()
import preview_net_custom as pc
import re
src = open('preview_net_custom.py', encoding='utf-8').read()
kw_line = re.search(r"kw = (dict\(.*\))", src).group(1)
kw = eval(kw_line, dict(dict=dict, S_d=S_d))
meshes, ctx, tie = man.world_meshes(sc, kw, with_hair=False)
S_m = Surface(meshes['black'].V[meshes['black'].F])
bad = 0
tot = 0
worst = 0.0
for z in np.arange(60.8, 65.2, 0.25):
    for y in np.arange(-3.2, 3.21, 0.4):
        a = S_d.cast((40.0, y, z), (-1, 0, 0))
        b = S_m.cast((40.0, y, z), (-1, 0, 0))
        if a is None or b is None:
            continue
        tot += 1
        gap = b[1][0] - a[1][0]
        if gap < 0.05:
            bad += 1
            worst = min(worst, gap)
print('mask-vs-skin samples %d, behind the skin: %d, worst gap %.2f' % (tot, bad, worst))
