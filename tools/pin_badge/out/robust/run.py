import subprocess, sys, json, re
R = 'out/robust/'
def run(label, args):
    p = subprocess.run([sys.executable, 'make_pin.py'] + args + ['--json'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = p.stdout
    j = None
    m = out.find('\n{\n  "slug"')
    if m >= 0:
        try: j = json.loads(out[m:out.rfind('}') + 1])
        except Exception as e: j = None
    print('=' * 8, label, 'exit', p.returncode)
    for l in out.splitlines():
        if re.match(r'(quantised|edge colour|orientation|verify_outfit|WARNING|FAIL|  ! |== )', l):
            print('   ', l)
    if p.stderr.strip():
        print('   STDERR:', '\n    '.join(p.stderr.strip().splitlines()[-4:]))
    if j:
        print('    slug=%s hash=%s parts=%d new=%d removed=%d maxtris=%d' % (j['slug'], j['hash'], len(j['parts']), len(j['new_files']), len(j['removed_files']), max(x['tris'] for x in j['parts'])))
    return p, j
tests = {
 'transparent_mosaic': [R+'transparent.png', '--name', 'rb', 'transparent'],
 'transparent_tex': [R+'transparent.png', '--name', 'rb', 'transparent', 'tex', '--url', 'https://files.catbox.moe/abcdef.png', '--mosaic'],
 'gray_jpg': [R+'gray.jpg', '--name', 'rb', 'gray'],
 'gray16': [R+'gray16.png', '--name', 'rb', 'gray16'],
 'palette_gif': [R+'palette.gif', '--name', 'rb', 'palette', '--bg', '000000'],
 'pixel16': [R+'pixel16.png', '--name', 'rb', 'pixel16'],
 'sym16': [R+'sym16.png', '--name', 'rb', 'sym16'],
 'sym16_tex': [R+'sym16.png', '--name', 'rb', 'sym16', 'tex', '--url', 'https://files.catbox.moe/abcdef.png'],
 'sym_emblem': [R+'sym_emblem.png', '--name', 'rb', 'emblem'],
 'sym_emblem_tex': [R+'sym_emblem.png', '--name', 'rb', 'emblem', 'tex', '--url', 'https://files.catbox.moe/abcdef.png', '--mosaic'],
 'wide': [R+'wide.png', '--name', 'rb', 'wide'],
 'wide_tex_pad': [R+'wide.png', '--name', 'rb', 'wide', 'tex', '--url', 'https://files.catbox.moe/abcdef.png', '--fit', 'pad', '--mosaic'],
 'colors2': [R+'pixel16.png', '--name', 'rb', 'c2', '--colors', '2'],
 'colors32': ['../../img/pins/isd_badge.png', '--name', 'rb', 'c32', '--colors', '32'],
 'res24': ['../../img/pins/isd_badge.png', '--name', 'rb', 'r24', '--res', '24'],
 'res128': ['../../img/pins/isd_badge.png', '--name', 'rb', 'r128', '--res', '128'],
}
sel = sys.argv[1:] or list(tests)
for k in sel: run(k, tests[k])
