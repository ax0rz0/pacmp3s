"""write the Xbox and guitar pacs as standalone outfit files (just my parts, no eca main) into the repo's outfits/xbox_guitar/ folder"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import outfit_lib as ol
import guitar_build as gb
import guitar_outfit as go
import xbox_outfit as xo


def main(out=None):
    out = out or os.path.join(ol.REPO, 'outfits', 'xbox_guitar')
    os.makedirs(out, exist_ok=True)
    G, jsA, infoA, jsB, infoB, expr, terms, beats = gb.build(go.FAMILY)
    items = (('xbox_ethics.txt', xo.standalone_text()), ('guitar_ethics.txt', go.standalone_text(G, expr)))
    for name, text in items:
        probs, n = ol.verify(text)
        if probs:
            raise SystemExit('%s: %s' % (name, probs))
        with open(os.path.join(out, name), 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        print('wrote', os.path.join(out, name), len(text), 'bytes,', n, 'ids')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
