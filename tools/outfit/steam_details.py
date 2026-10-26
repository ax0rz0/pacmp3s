"""Public Steam Workshop file details (no key needed) + small preview thumbnails for a list of ids.
    python steam_details.py OUTDIR id id id ...      -> OUTDIR/details.json, OUTDIR/prev_<id>.jpg (400 px letterbox thumbnails)"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
out = sys.argv[1]
ids = sys.argv[2:]
os.makedirs(out, exist_ok=True)
form = {'itemcount': str(len(ids))}
for i, k in enumerate(ids):
    form['publishedfileids[%d]' % i] = k
req = urllib.request.Request('https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/', data=urllib.parse.urlencode(form).encode(), method='POST')
with urllib.request.urlopen(req, timeout=60) as r:
    data = json.load(r)
rows = data['response']['publishedfiledetails']
json.dump(rows, open(os.path.join(out, 'details.json'), 'w', encoding='utf-8'), indent=1)
for r in rows:
    pid = r.get('publishedfileid')
    if r.get('result') != 1:
        print(pid, 'result', r.get('result'))
        continue
    print('%-11s %-60s %7.1f MB  subs %8s  fav %6s  upd %s' % (pid, r.get('title', '?')[:60], int(r.get('file_size', 0)) / 1e6, r.get('lifetime_subscriptions', '?'), r.get('favorited', '?'),
                                                              time.strftime('%Y-%m-%d', time.gmtime(r.get('time_updated', 0)))))
    url = r.get('preview_url')
    if url:
        try:
            with urllib.request.urlopen(url + '?imw=400&imh=400&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=true', timeout=40) as pr:
                open(os.path.join(out, 'prev_%s.jpg' % pid), 'wb').write(pr.read())
        except Exception as e:
            print('   preview failed', e)
