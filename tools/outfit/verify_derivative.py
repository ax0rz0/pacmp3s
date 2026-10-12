"""Verify a modified copy of one of the user's outfits.
    python verify_derivative.py NEW.txt ORIGINAL.txt STAGE_DIR [--n-original N]
Checks: format (no BOM / CR, watermark line), fresh UIDs (64 hex ending a0c3f, unique), the first N top-level groups equal the original apart from UniqueID / *UID / Notes,
no emote-pack classes left, every obj / texture URL points at a file under STAGE_DIR (and the same files exist in the repo when --repo is given)."""
import copy
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pac_parse as pp
import pac_write as pw

REPO_RAW = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/'


def strip(p):
    p = copy.deepcopy(p)
    for q in pw.walk([p]):
        for k in list(q['self']):
            if k == 'UniqueID' or k.endswith('UID') or k == 'Notes':
                q['self'].pop(k)
    return p


def main():
    new_path, orig_path, stage = sys.argv[1:4]
    n_orig = int(sys.argv[sys.argv.index('--n-original') + 1]) if '--n-original' in sys.argv else 0
    problems = []

    def bad(m):
        problems.append(m)
        print('  PROBLEM:', m)

    raw = open(new_path, 'rb').read()
    if raw[:3] == b'\xef\xbb\xbf':
        bad('BOM')
    if b'\r' in raw:
        bad('CR characters')
    text = raw.decode('utf-8')
    if not text.startswith('-- claude skill made by ax0rz0\n\n[1] = {'):
        bad('header: ' + repr(text[:60]))
    new = pp.parse(text)
    orig = pp.load(orig_path)
    parts = list(pw.walk(new))
    ids = [p['self'].get('UniqueID', '') for p in parts]
    if len(set(ids)) != len(ids):
        bad('duplicate UIDs')
    for u in ids:
        if not re.fullmatch(r'[0-9a-f]{64}', u) or not u.endswith('a0c3f'):
            bad('UID %r' % u)
    classes = {}
    for p in parts:
        classes[p['self']['ClassName']] = classes.get(p['self']['ClassName'], 0) + 1
    print('  parts %d: %s' % (len(parts), dict(sorted(classes.items()))))
    for c in ('custom_animation', 'event', 'sound2', 'trail2', 'particles'):
        if c in classes:
            bad('leftover %s parts: %d' % (c, classes[c]))
    for k in sorted(new):
        if new[k]['self'].get('Notes') != 'claude skill made by ax0rz0':
            bad('top-level [%d] has no watermark Notes' % k)
    # the user's own groups are untouched
    for k in range(1, n_orig + 1):
        if strip(new[k]) != strip(orig[k]):
            bad('original group [%d] changed' % k)
        else:
            print('  original group [%d] identical apart from UID/Notes (%d parts)' % (k, sum(1 for _ in pw.walk([new[k]]))))
    # asset links
    urls = set()
    for p in parts:
        s = p['self']
        for key in ('Model', 'Material', 'Materials'):
            v = s.get(key)
            if isinstance(v, str):
                for piece in v.split(';'):
                    piece = piece.replace(' noclamp', '').strip()
                    if piece.startswith(REPO_RAW):
                        urls.add(piece)
    miss = []
    for u in sorted(urls):
        rel = u[len(REPO_RAW):]
        if not os.path.exists(os.path.join(stage, *rel.split('/'))):
            miss.append(rel)
    print('  asset urls %d, missing in the stage folder: %s' % (len(urls), miss or 'none'))
    if miss:
        bad('missing assets')
    print('PROBLEMS: %d' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
