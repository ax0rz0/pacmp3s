"""python wait_assets_live_adv.py [STAGE_DIR] [minutes]: poll raw GitHub until every OBJ under STAGE_DIR/obj/adv is live with the right size (default stage dir: stage_adv)"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_live as cl

RAW = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/'
stage = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_adv')
minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 10
d = os.path.join(stage, 'obj', 'adv')
urls = {RAW + 'obj/adv/' + fn: os.path.getsize(os.path.join(d, fn)) for fn in os.listdir(d) if fn.endswith('.obj')}
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
