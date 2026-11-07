"""first / last frame (and the middle) of a few candidate loops, side by side: loop_preview.py start:length ..."""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.environ.get('XBOX_WORK', os.path.dirname(HERE))
SRC = os.path.join(SP, 'xbox_real', 'dl', 'nfsrivals', 'nfsrivals.mp4')
OUT = os.path.join(SP, 'xbox_real', 'sheets')


def frame(t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % t, '-i', SRC, '-frames:v', '1', '-vf', 'scale=320:180:flags=lanczos', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    return Image.fromarray(np.frombuffer(raw, np.uint8).reshape(180, 320, 3))


def main(specs):
    sheet = Image.new('RGB', (320 * 4, 180 * len(specs)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for r, spec in enumerate(specs):
        s, L = [float(v) for v in spec.split(':')]
        for c, t in enumerate((s, s + L / 2, s + L - 0.125, s + L)):
            sheet.paste(frame(t), (c * 320, r * 180))
            d.rectangle([c * 320, r * 180, c * 320 + 120, r * 180 + 12], fill=(0, 0, 0))
            d.text((c * 320 + 3, r * 180 + 1), 'loop %s  t=%.2f' % (spec, t), fill=(255, 255, 0))
    p = os.path.join(OUT, 'loop_candidates.png')
    sheet.save(p)
    print('wrote', p)


if __name__ == '__main__':
    main(sys.argv[1:])
