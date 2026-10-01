import os
from PIL import Image, ImageDraw
D = os.path.dirname(os.path.abspath(__file__))
# transparent PNG: red arrow pointing up-left on transparent bg
im = Image.new('RGBA', (300, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.polygon([(40, 40), (200, 60), (60, 200)], fill=(220, 30, 30, 255)); d.rectangle([180, 200, 280, 280], fill=(30, 30, 220, 128))
im.save(os.path.join(D, 'transparent.png'))
# grayscale JPG: gradient + dark block top-left
g = Image.new('L', (256, 256)); g.putdata([(x + y) // 2 for y in range(256) for x in range(256)])
ImageDraw.Draw(g).rectangle([20, 20, 100, 60], fill=0); g.save(os.path.join(D, 'gray.jpg'), quality=90)
# palette GIF with transparency
p = Image.new('P', (200, 200), 0); p.putpalette([255, 0, 255, 0, 200, 0, 250, 250, 0, 0, 0, 200] + [0] * 756)
dp = ImageDraw.Draw(p); dp.rectangle([10, 10, 90, 90], fill=1); dp.rectangle([110, 10, 190, 90], fill=2); dp.rectangle([10, 110, 90, 190], fill=3)
p.save(os.path.join(D, 'palette.gif'), transparency=0)
# 16x16 pixel art (asymmetric)
px = Image.new('RGB', (16, 16), (255, 255, 255)); dpx = ImageDraw.Draw(px)
dpx.rectangle([2, 2, 6, 6], fill=(255, 0, 0)); dpx.rectangle([9, 2, 13, 4], fill=(0, 160, 0)); dpx.rectangle([2, 10, 4, 13], fill=(0, 0, 255))
px.save(os.path.join(D, 'pixel16.png'))
# 16x16 LEFT-RIGHT SYMMETRIC pixel art (an up arrow / shield)
s = Image.new('RGB', (16, 16), (240, 240, 240)); ds = ImageDraw.Draw(s)
ds.polygon([(8, 1), (14, 8), (1, 8)], fill=(200, 0, 0)); ds.rectangle([5, 8, 10, 14], fill=(0, 0, 150))
s = s.resize((16,16)); s.save(os.path.join(D, 'sym16.png'))
# larger LR symmetric emblem
e = Image.new('RGB', (512, 512), (20, 40, 90)); de = ImageDraw.Draw(e)
de.polygon([(256, 40), (440, 300), (72, 300)], fill=(240, 200, 30)); de.rectangle([180, 300, 332, 470], fill=(230, 230, 230))
de.ellipse([226, 140, 286, 200], fill=(180, 20, 20)); e.save(os.path.join(D, 'sym_emblem.png'))
# extreme aspect 4000x300
w = Image.new('RGB', (4000, 300), (0, 0, 0)); dw = ImageDraw.Draw(w)
for i in range(0, 4000, 400): dw.rectangle([i, 0, i + 199, 149], fill=(255, (i // 16) % 256, 0))
dw.rectangle([1850, 150, 2150, 299], fill=(0, 200, 255)); dw.rectangle([1850, 0, 1990, 149], fill=(255, 255, 255))
w.save(os.path.join(D, 'wide.png'))
# 16-bit grayscale png
import numpy as np
a = (np.add.outer(np.arange(128), np.arange(128) * 3) * 120).astype(np.uint16)
Image.fromarray(a).save(os.path.join(D, 'gray16.png'))
print('ok')
