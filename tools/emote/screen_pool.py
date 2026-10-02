import sys, json, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import make_fn_pack as fp
import make_fn_pack2 as p2
from retarget import Valve
from mdl_anim import load_model

fam = sys.argv[1] if len(sys.argv) > 1 else 'classd'
out = sys.argv[2] if len(sys.argv) > 2 else 'pool_out'
only = sys.argv[3].split(',') if len(sys.argv) > 3 else None
valve = Valve(load_model(fp.FAMILIES[fam]))
os.makedirs(os.path.join(out, fam), exist_ok=True)
rows = []
for key, title, seq in p2.POOL:
    if only and key not in only:
        continue
    t0 = time.time()
    try:
        model = p2.find_model(seq)
        js, st = fp.build((key, title, model, seq), valve, finger_min=60.0)
    except Exception as e:
        print('%-12s FAILED %s' % (key, e)); sys.stdout.flush(); continue
    path = os.path.join(out, fam, 'fn_%s.json' % key)
    with open(path, 'w', newline='\n') as f:
        json.dump(js, f, separators=(',', ':'))
    kb = os.path.getsize(path) / 1024
    # lowest pelvis height relative to rest (lying down / floor work shows up here)
    print('%-12s %-16s %2dfps %4.1fs %4d fr %2d bones %5.0f KB | root %-8s span %5.1f | closure %5.1f%s | err mean %.2f p99 %.2f max %.1f | %.0fs' % (
        key, seq, st['fps'], st['secs'], st['frames'], st['bones'], kb, st['axes'], st['span'], st['closure'], '+B' if st['blended'] else '  ',
        st['mean_err'], st['p99'], st['max_err'], time.time() - t0))
    sys.stdout.flush()
