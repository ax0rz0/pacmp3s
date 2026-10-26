"""contact sheet of Workshop preview thumbnails with title / subscribers: python heads_sheet.py DIR OUT.png id id ..."""
import json
import os
import sys
import time

from PIL import Image, ImageDraw, ImageFont

d, out = sys.argv[1], sys.argv[2]
ids = sys.argv[3:]
rows = {r['publishedfileid']: r for r in json.load(open(os.path.join(d, 'details.json'), encoding='utf-8')) if r.get('result') == 1}
if not ids:
    ids = [k for k in rows if os.path.exists(os.path.join(d, 'prev_%s.jpg' % k))]
cols = 6 if len(ids) > 12 else 4
tw, th = 300, 300
lab = 56
W = cols * tw
H = ((len(ids) + cols - 1) // cols) * (th + lab)
img = Image.new('RGB', (W, H), (24, 26, 32))
dr = ImageDraw.Draw(img)
try:
    f1 = ImageFont.truetype('arial.ttf', 15)
    f2 = ImageFont.truetype('arial.ttf', 12)
except Exception:
    f1 = f2 = ImageFont.load_default()
for i, k in enumerate(ids):
    r = rows.get(k)
    x, y = (i % cols) * tw, (i // cols) * (th + lab)
    p = os.path.join(d, 'prev_%s.jpg' % k)
    if os.path.exists(p):
        try:
            im = Image.open(p).convert('RGB')
            im.thumbnail((tw, th))
            img.paste(im, (x + (tw - im.width) // 2, y + (th - im.height) // 2))
        except Exception:
            pass
    title = (r or {}).get('title', k)
    dr.text((x + 6, y + th + 4), '%d  %s' % (i + 1, title[:38]), fill=(235, 235, 240), font=f1)
    sub = '%s subs  %.0f MB  id %s' % ((r or {}).get('lifetime_subscriptions', '?'), int((r or {}).get('file_size', 0)) / 1e6, k)
    dr.text((x + 6, y + th + 24), sub, fill=(150, 160, 175), font=f2)
img.save(out)
print(out, img.size, len(ids))
