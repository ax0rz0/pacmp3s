"""Are the files the outfits use live on GitHub with the right size?  python check_live.py [--wait MINUTES] [--only SUBSTR]
Reads pacmp3s_live_urls.json from the temp folder (written by verify_outfits.py: url -> size of the repo file). HEAD with Accept-Encoding identity, redirects followed.
Exit 0 when every URL answers 200 with the repo file's size."""
import json, os, sys, tempfile, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
LIVE_URLS = os.path.join(tempfile.gettempdir(), 'pacmp3s_live_urls.json')


def head(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': UA, 'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=30) as r:
                cl = r.headers.get('Content-Length')
                return r.status, int(cl) if cl else None
        except urllib.error.HTTPError as e:
            return e.code, None
        except Exception as e:
            last = e
            time.sleep(1.5)
    return None, str(last)


def check(urls, only=None):
    items = [(u, s) for u, s in urls.items() if not only or only in u]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda us: head(us[0]), items))
    bad = []
    for (u, size), (code, cl) in zip(items, res):
        if code != 200 or cl != size:
            bad.append((u, size, code, cl))
    return len(items), bad


def main():
    urls = json.load(open(LIVE_URLS))
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    wait = float(sys.argv[sys.argv.index('--wait') + 1]) if '--wait' in sys.argv else 0
    t0 = time.time()
    n, bad = check(urls, only)                      # one full pass, then only the stragglers are polled (every 30 s)
    while True:
        stamp = time.strftime('%H:%M:%S')
        if not bad:
            n2, bad = check(urls, only)             # final full pass to confirm
            if not bad:
                print('%s  all %d urls live with the right size' % (stamp, n2))
                return 0
        print('%s  %d of %d urls not ready:' % (stamp, len(bad), n))
        for u, size, code, cl in bad[:12]:
            print('   %-100s want %s got HTTP %s size %s' % (u.split('main/')[-1], size, code, cl))
        sys.stdout.flush()
        if time.time() - t0 >= wait * 60:
            return 1
        time.sleep(30)
        _, bad = check({u: size for u, size, _, _ in bad}, None)


if __name__ == '__main__':
    sys.exit(main())
