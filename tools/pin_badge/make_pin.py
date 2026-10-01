"""PAC3 pin badge generator CLI.

    python make_pin.py <image path or https URL> [--name NAME] [--url IMAGE_URL] [--mosaic]
                       [--res 64] [--colors 16] [--diameter 2.25] [--fit crop|pad] [--bg ffffff]
                       [--bone "spine 2"] [--no-gloss]
    python make_pin.py --reusable [--url IMAGE_URL]

Texture mode: an image URL is known (--url, or the positional arg is itself an https URL). The face
dome's Material is that URL and is visible. Mosaic layers are only generated with --mosaic, and are hidden.
Mosaic mode: no URL known (or --mosaic with no URL given): colour layers visible, textured face hidden.

Never runs git; prints the commands the user must run.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

import pin_common as pc
import pin_geometry as pg
import pin_image as pi
import pin_pac as pp
import pin_render as pr

DEFAULT_IMAGE_URL = 'https://raw.githubusercontent.com/ax0rz0/pacmp3s/refs/heads/main/img/pins/isd_badge.png'  # direct raw host; image loaders may not follow github.com redirects
PREVIEW = 384


class Fail(Exception):
    pass


# ---------------------------------------------------------------- helpers
def _is_url(s):
    return isinstance(s, str) and s.lower().startswith(('http://', 'https://'))


def _stem(src):
    if _is_url(src):
        base = os.path.basename(urllib.parse.urlparse(src).path)
    else:
        base = os.path.basename(src)
    return os.path.splitext(base)[0] or 'pin'


def _list_pin_files(folder, slug):
    if not os.path.isdir(folder):
        return set()
    pat = re.compile(r'^pin_' + re.escape(slug) + r'_.*\.obj$')
    return {f for f in os.listdir(folder) if pat.match(f)}


def _edge_color(grid, palette, diameter):
    """Most common colour among in-circle cells with centre radius > 0.85 R (same rule as build_mosaic)."""
    n = len(grid)
    R = diameter / 2.0
    counts = {}
    for r in range(n):
        x = R - (r + 0.5) * 2 * R / n
        for c in range(n):
            z = -R + (c + 0.5) * 2 * R / n
            rc = (x * x + z * z) ** 0.5
            if 0.85 * R < rc <= R:
                counts[grid[r][c]] = counts.get(grid[r][c], 0) + 1
    if not counts:
        return (1.0, 1.0, 1.0)
    ci = max(counts, key=lambda k: (counts[k], -k))
    return tuple(v / 255.0 for v in palette[ci])


def _quant_image(grid, palette):
    n = len(grid)
    im = Image.new('RGB', (n, n))
    im.putdata([palette[grid[r][c]] for r in range(n) for c in range(n)])
    return im


def _fit_square(im, size, bg=(30, 31, 34)):
    """Letterbox any image into a size x size tile (alpha composited over the preview bg)."""
    rgba = im.convert('RGBA')
    k = size / float(max(rgba.size))
    rgba = rgba.resize((max(1, round(rgba.width * k)), max(1, round(rgba.height * k))),
                       Image.NEAREST if k > 1 else Image.LANCZOS)
    tile = Image.new('RGBA', (size, size), bg + (255,))
    tile.alpha_composite(rgba, ((size - rgba.width) // 2, (size - rgba.height) // 2))
    return tile.convert('RGB')


def _orientation_ok(res):
    """Pass if clearly ok; accept near-perfect matches of (near) symmetric images as inconclusive."""
    if res['ok']:
        return True, None
    flips = [res['mirror_lr'], res['mirror_ud'], res['rot180']]
    if res['as_is'] < 2.0 and min(flips) - res['as_is'] < 2.0:
        return True, 'inconclusive (image is symmetric; as-is error %.2f)' % res['as_is']
    return False, None


def _git_report(slug, before, after, folder, extra_paths):
    new = sorted(after - before)
    removed = sorted(before - after)
    rel = 'obj/pins/%s' % slug
    lines = ['', 'Git (NOT run by this tool; run it yourself):', '  cd "%s"' % pc.REPO]
    paths = [rel] + list(extra_paths)
    lines.append('  git add -A %s' % ' '.join(paths))
    lines.append('  git commit -m "pin badge: %s"' % slug)
    lines.append('  git push')
    lines.append('  new files under %s: %d' % (rel, len(new)))
    for f in new:
        lines.append('    + %s/%s' % (rel, f))
    lines.append('  removed (stale) files under %s: %d' % (rel, len(removed)))
    for f in removed:
        lines.append('    - %s/%s' % (rel, f))
    return lines


def _manifest_path(slug):
    return os.path.join(pc.OUT_DIR, slug + '.json')


def _save_manifest(manifest):
    os.makedirs(pc.OUT_DIR, exist_ok=True)
    path = _manifest_path(manifest['slug'])
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, indent=2)
        f.write('\n')
    return path


def _load_texture_for_url(url):
    """Texture for previews: map a repo raw URL to the local file, else download."""
    p = pp.url_to_repo_path(url)
    if p and os.path.isfile(p):
        return pi.load_image(p)
    return pi.load_image(url)


def _with_mode(manifest, show):
    """Copy of the manifest with only the `show` face visible: 'texture' or 'mosaic'."""
    m = json.loads(json.dumps(manifest))
    for p in m['parts']:
        if p['role'] == 'texture':
            p['hidden'] = (show != 'texture')
        elif p['role'] == 'image':
            p['hidden'] = (show != 'mosaic')
    return m


# ---------------------------------------------------------------- per-image badge
def make_badge(args):
    src = args.image
    if not src:
        raise Fail('an image path or https URL is required')
    url_given = args.url or (src if _is_url(src) and src.lower().startswith('https://') else None)
    if args.url and not args.url.lower().startswith('https://'):
        raise Fail('--url must be https (the server whitelist is https-only)')
    if _is_url(src) and not src.lower().startswith('https://'):
        raise Fail('image URL must be https')

    name = ' '.join(args.name).strip() if args.name else _stem(src)
    slug = pc.slugify(name)
    texture_mode = bool(url_given)
    want_mosaic = (not texture_mode) or args.mosaic
    bg = tuple(int(args.bg[i:i + 2], 16) for i in (0, 2, 4))
    D = args.diameter
    res = args.res

    print('== pin badge "%s" (slug %s) mode=%s ==' % (name, slug, 'texture' if texture_mode else 'mosaic'))
    raw = pi.read_source_bytes(src)
    img = pi.load_image(src)
    print('source: %s  %dx%d' % (src, img.width, img.height))
    prepared = pi.prepare(img, res=res, fit=args.fit, bg=bg)
    grid, palette = pi.quantize(prepared, colors=args.colors)
    print('quantised: %d colours' % len(palette))
    quant = _quant_image(grid, palette)

    h = hashlib.sha1()
    h.update(raw)
    h.update(json.dumps({'res': res, 'colors': args.colors, 'd': D, 'fit': args.fit, 'bg': args.bg,
                         'url': url_given, 'mosaic': want_mosaic, 'gloss': not args.no_gloss,
                         'slug': slug, 'v': 1}, sort_keys=True).encode('utf-8'))
    hash6 = h.hexdigest()[:6]

    folder = pc.obj_dir(slug)
    before = _list_pin_files(folder, slug)
    for f in before:
        os.remove(os.path.join(folder, f))
    os.makedirs(folder, exist_ok=True)
    fname = lambda key: pc.obj_filename(slug, hash6, key)

    if want_mosaic:
        mosaic_parts, edge = pi.build_mosaic(grid, palette, folder, fname, diameter=D)
    else:
        mosaic_parts, edge = [], _edge_color(grid, palette, D)
    print('edge colour: %s' % pc.hex_color(edge))
    hw = pg.build_hardware(folder, fname, diameter=D, edge_color=edge)

    by_key = {p['key']: p for p in hw}
    if args.no_gloss:
        os.remove(by_key['gloss']['local_path'])
        hw = [p for p in hw if p['key'] != 'gloss']
        by_key = {p['key']: p for p in hw}

    face = by_key['face_uv']
    if url_given:
        face['material'] = url_given
    face['hidden'] = texture_mode is False
    for p in mosaic_parts:
        p['hidden'] = texture_mode

    order = [by_key['body'], face] + mosaic_parts
    order += [by_key[k] for k in ('gloss', 'back', 'rim') if k in by_key]
    for p in order:
        p['url'] = pc.obj_url(slug, p['file'])

    manifest = {
        'name': name, 'slug': slug, 'hash': hash6, 'diameter': D,
        'image_url': url_given, 'source_image': src, 'res': res, 'colors': args.colors,
        'mode': 'texture' if texture_mode else 'mosaic', 'bone': args.bone, 'parts': order,
    }
    mpath = _save_manifest(manifest)

    outfit_path = os.path.join(pc.PAC_DIR, 'pin_%s.txt' % slug)
    pp.write_outfit(manifest, outfit_path, bone=args.bone)
    print('outfit: ' + outfit_path)
    print('manifest: ' + mpath)

    tex_img = None
    if texture_mode:
        tex_img = img
        if img.width != img.height:
            print('WARNING: source image is %dx%d (not square); in game the URL texture is stretched to the '
                  'face square, so a square image is recommended.' % (img.width, img.height))
    ref = prepared if texture_mode else quant
    # orientation reference in texture mode: the prepared image, rendered from a texture of the same content
    orient_tex = prepared if texture_mode else None
    report = {}
    previews = os.path.join(pc.OUT_DIR, slug + '_preview.png')
    source_tile = _fit_square(img, PREVIEW)
    quant_tile = quant.resize((PREVIEW, PREVIEW), Image.NEAREST)

    # render previews with the true texture, but orient-check with the prepared texture
    v = pp.verify_outfit(outfit_path)
    print('verify_outfit: %s  counts=%s' % ('OK' if v['ok'] else 'FAILED', v['counts']))
    for msg in v['messages']:
        print('  ! ' + msg)
    front = pr.render(manifest, 'front', size=PREVIEW, texture_image=tex_img)
    tq = pr.render(manifest, 'three_quarter', size=PREVIEW, texture_image=tex_img)
    pr.contact_sheet([source_tile, quant_tile, front, tq],
                     ['source', 'quantised %dx%d' % (res, res), 'front render', '3/4 render'], previews)
    print('preview: ' + previews)

    problems = []
    orient = {}
    o = pr.orientation_check(manifest, ref, res, texture_image=orient_tex)
    ok, note = _orientation_ok(o)
    orient['primary'] = dict(o, accepted=ok, note=note, mode=manifest['mode'])
    print('orientation (%s): as_is=%.2f lr=%.2f ud=%.2f rot180=%.2f best=%s margin=%.2f ok=%s%s' % (
        manifest['mode'], o['as_is'], o['mirror_lr'], o['mirror_ud'], o['rot180'], o['best'], o['margin'],
        ok, ('  ' + note) if note else ''))
    if not ok:
        problems.append('orientation check FAILED (best match: %s)' % o['best'])
    if texture_mode and mosaic_parts:
        o2 = pr.orientation_check(_with_mode(manifest, 'mosaic'), quant, res)
        ok2, note2 = _orientation_ok(o2)
        orient['mosaic_layers'] = dict(o2, accepted=ok2, note=note2)
        print('orientation (hidden mosaic layers shown): as_is=%.2f lr=%.2f ud=%.2f rot180=%.2f ok=%s%s' % (
            o2['as_is'], o2['mirror_lr'], o2['mirror_ud'], o2['rot180'], ok2, ('  ' + note2) if note2 else ''))
        if not ok2:
            problems.append('mosaic layer orientation FAILED (best match: %s)' % o2['best'])
    if not v['ok']:
        problems.append('verify_outfit FAILED: ' + '; '.join(v['messages']))

    after = _list_pin_files(folder, slug)
    extra = []
    if url_given and pp.url_to_repo_path(url_given):
        rp = os.path.relpath(pp.url_to_repo_path(url_given), pc.REPO).replace('\\', '/')
        extra.append(rp)

    print('')
    print('parts:')
    for p in order:
        print('  %-8s %-34s verts=%-5d tris=%-5d %s%s' % (
            p['key'], p['label'][:34], p['verts'], p['tris'], 'hidden ' if p['hidden'] else '',
            'material=' + p['material'] if p.get('material') else ''))
    for line in _git_report(slug, before, after, folder, extra):
        print(line)
    print('')
    print('Wear it: pac editor -> load "pin_%s" from data/pac3 (parent is on bone "%s").' % (slug, args.bone))
    if texture_mode:
        print('Texture URL (must be reachable by the server after you push): %s' % url_given)

    result = {
        'slug': slug, 'name': name, 'hash': hash6, 'mode': manifest['mode'], 'outfit': outfit_path,
        'manifest': mpath, 'preview': previews,
        'parts': [{'key': p['key'], 'file': p['local_path'], 'verts': p['verts'], 'tris': p['tris'],
                   'hidden': p['hidden']} for p in order],
        'verify': {'ok': v['ok'], 'counts': v['counts'], 'messages': v['messages']},
        'orientation': orient, 'new_files': sorted(after - before), 'removed_files': sorted(before - after),
        'problems': problems,
    }
    if problems:
        print('')
        for pr_ in problems:
            print('FAIL: ' + pr_)
    return result, problems


# ---------------------------------------------------------------- reusable (static base set)
def make_reusable(url=None):
    url = url or DEFAULT_IMAGE_URL
    if not url.lower().startswith('https://'):
        raise Fail('--url must be https')
    slug, name = 'pin_badge', 'pin badge'
    print('== reusable pin badge (slug %s) face material = %s ==' % (slug, url))
    parts = pg.build_base_set()
    by_key = {p['key']: p for p in parts}
    base_url = pc.RAW_BASE + 'obj/pins/base/'
    for p in parts:
        p['url'] = base_url + p['file']
    by_key['face_uv']['material'] = url
    by_key['face_uv']['hidden'] = False
    manifest = {
        'name': name, 'slug': slug, 'hash': 'base', 'diameter': pc.DEFAULT_DIAMETER,
        'image_url': url, 'source_image': url, 'res': None, 'colors': None, 'mode': 'texture',
        'bone': pc.DEFAULT_BONE, 'parts': parts,
    }
    mpath = _save_manifest(manifest)
    outfit_path = os.path.join(pc.PAC_DIR, 'pin_badge.txt')
    pp.write_outfit(manifest, outfit_path)
    print('outfit: ' + outfit_path)
    print('manifest: ' + mpath)

    v = pp.verify_outfit(outfit_path)
    print('verify_outfit: %s  counts=%s' % ('OK' if v['ok'] else 'FAILED', v['counts']))
    for msg in v['messages']:
        print('  ! ' + msg)

    problems = []
    orient = {}
    previews = os.path.join(pc.OUT_DIR, 'pin_badge_preview.png')
    tex = None
    try:
        tex = _load_texture_for_url(url)
    except Exception as e:  # unpushed image URLs are expected to be unreachable
        print('WARNING: could not load texture for preview/orientation (%s); skipped' % e)
    if tex is not None:
        res = 64
        prepared = pi.prepare(tex, res=res, fit='crop')
        quant_like = prepared
        front = pr.render(manifest, 'front', size=PREVIEW, texture_image=tex)
        tq = pr.render(manifest, 'three_quarter', size=PREVIEW, texture_image=tex)
        pr.contact_sheet([_fit_square(tex, PREVIEW), front, tq], ['texture', 'front render', '3/4 render'],
                         previews)
        print('preview: ' + previews)
        o = pr.orientation_check(manifest, quant_like, res, texture_image=prepared)
        ok, note = _orientation_ok(o)
        orient['primary'] = dict(o, accepted=ok, note=note, mode='texture')
        print('orientation (texture): as_is=%.2f lr=%.2f ud=%.2f rot180=%.2f best=%s margin=%.2f ok=%s%s' % (
            o['as_is'], o['mirror_lr'], o['mirror_ud'], o['rot180'], o['best'], o['margin'], ok,
            ('  ' + note) if note else ''))
        if not ok:
            problems.append('orientation check FAILED (best match: %s)' % o['best'])
    if not v['ok']:
        problems.append('verify_outfit FAILED: ' + '; '.join(v['messages']))

    print('')
    print('parts:')
    for p in parts:
        print('  %-8s %-34s verts=%-5d tris=%-5d %s%s' % (
            p['key'], p['label'][:34], p['verts'], p['tris'], 'hidden ' if p['hidden'] else '',
            'material=' + p['material'] if p.get('material') else ''))
    print('')
    print('Git (NOT run by this tool; run it yourself):')
    print('  cd "%s"' % pc.REPO)
    print('  git add obj/pins/base img/pins')
    print('  git commit -m "pin badge: base set and example image"')
    print('  git push')
    print('Swap the image: paste a new https URL into the Material of the "image (paste URL into material)" part.')
    for p in problems:
        print('FAIL: ' + p)
    result = {
        'slug': slug, 'outfit': outfit_path, 'manifest': mpath, 'preview': previews if tex is not None else None,
        'parts': [{'key': p['key'], 'file': p['local_path'], 'verts': p['verts'], 'tris': p['tris'],
                   'hidden': p['hidden']} for p in parts],
        'verify': {'ok': v['ok'], 'counts': v['counts'], 'messages': v['messages']},
        'orientation': orient, 'problems': problems,
    }
    return result, problems


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description='PAC3 pin badge generator')
    ap.add_argument('image', nargs='?', help='image path or https URL')
    ap.add_argument('--name', nargs='+', help='badge name (default: image file stem)')
    ap.add_argument('--url', help='https URL the image will be reachable at (enables texture mode)')
    ap.add_argument('--mosaic', action='store_true', help='also generate the (hidden, in texture mode) mosaic layers')
    ap.add_argument('--res', type=int, default=64)
    ap.add_argument('--colors', type=int, default=16)
    ap.add_argument('--diameter', type=float, default=pc.DEFAULT_DIAMETER)
    ap.add_argument('--fit', choices=('crop', 'pad'), default='crop')
    ap.add_argument('--bg', default='ffffff', help='background hex for transparent/pad areas')
    ap.add_argument('--bone', default=pc.DEFAULT_BONE)
    ap.add_argument('--no-gloss', action='store_true')
    ap.add_argument('--reusable', action='store_true', help='build the static base set + pin_badge.txt')
    ap.add_argument('--json', action='store_true', help='print the machine-readable result at the end')
    args = ap.parse_args(argv)
    args.bg = args.bg.lstrip('#')
    if not re.fullmatch(r'[0-9a-fA-F]{6}', args.bg):
        ap.error('--bg must be 6 hex digits')

    try:
        if args.reusable:
            result, problems = make_reusable(args.url)
        else:
            result, problems = make_badge(args)
    except Fail as e:
        print('FAIL: %s' % e, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    if problems:
        return 1
    print('\nALL CHECKS PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
