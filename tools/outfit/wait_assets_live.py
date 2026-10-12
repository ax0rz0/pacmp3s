"""python wait_assets_live.py STAGE_DIR [minutes]: poll raw GitHub until every file under STAGE_DIR/obj/bna and STAGE_DIR/tex/bna (or the given subdirs) is live with the right size"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_live as cl

RAW = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/'
stage = sys.argv[1]
minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 10
prefixes = [p for p in sys.argv[3:]] or ['dclass_']
urls = {}
for sub in ('obj/bna', 'tex/bna'):
    d = os.path.join(stage, *sub.split('/'))
    if not os.path.isdir(d):
        continue
    for fn in os.listdir(d):
        if any(fn.startswith(p) for p in prefixes):
            urls[RAW + sub + '/' + fn] = os.path.getsize(os.path.join(d, fn))
print('watching %d files' % len(urls))
t0 = time.time()
while True:
    n, bad = cl.check(urls)
    if not bad:
        print('%s all %d files live with the right size' % (time.strftime('%H:%M:%S'), n))
        sys.exit(0)
    print('%s %d of %d not ready: %s' % (time.strftime('%H:%M:%S'), len(bad), n, [(b[0].split('main/')[-1], b[2]) for b in bad[:3]]))
    sys.stdout.flush()
    if time.time() - t0 > minutes * 60:
        sys.exit(1)
    time.sleep(20)
