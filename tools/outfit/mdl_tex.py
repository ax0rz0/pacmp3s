"""List the textures, cdmaterials, skin families and body groups of a Source .mdl (v44-49): python mdl_tex.py FILE.mdl | hl2:models/Humans/Group01/Female_04.mdl"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdl_anim import cstr, _vpk_get, HL2_VPK


def read_mdl_bytes(spec):
    if spec.startswith('hl2:'):
        return _vpk_get(HL2_VPK, spec[4:].lower())
    return open(spec, 'rb').read()


def info(raw):
    ver = struct.unpack_from('<i', raw, 4)[0]
    name = raw[12:76].split(b'\0')[0].decode('latin1')
    nbones, boneidx = struct.unpack_from('<2i', raw, 156)
    ntex, texidx = struct.unpack_from('<2i', raw, 204)
    ncd, cdidx = struct.unpack_from('<2i', raw, 212)
    nskinref, nskinfam, skinidx = struct.unpack_from('<3i', raw, 220)
    nbody, bodyidx = struct.unpack_from('<2i', raw, 232)
    textures = []
    for i in range(ntex):
        o = texidx + i * 64
        ni = struct.unpack_from('<i', raw, o)[0]
        textures.append(cstr(raw, o + ni)[0])
    cds = []
    for i in range(ncd):
        off = struct.unpack_from('<i', raw, cdidx + i * 4)[0]
        cds.append(cstr(raw, off)[0])
    skins = []
    for f in range(nskinfam):
        skins.append(struct.unpack_from('<%dh' % nskinref, raw, skinidx + f * nskinref * 2))
    bodies = []
    for i in range(nbody):
        o = bodyidx + i * 16
        ni, nm, base, mi = struct.unpack_from('<4i', raw, o)
        bname = cstr(raw, o + ni)[0]
        models = []
        for j in range(nm):
            mo = o + mi + j * 148
            models.append(raw[mo:mo + 64].split(b'\0')[0].decode('latin1'))
        bodies.append((bname, models))
    return dict(version=ver, name=name, bones=nbones, textures=textures, cdmaterials=cds, skinref=nskinref, skins=skins, bodygroups=bodies)


if __name__ == '__main__':
    for spec in sys.argv[1:]:
        d = info(read_mdl_bytes(spec))
        print('== %s  (v%d, %d bones)' % (spec, d['version'], d['bones']))
        print('   cdmaterials:', d['cdmaterials'])
        for i, t in enumerate(d['textures']):
            print('   tex[%d] %s' % (i, t))
        print('   skinref %d, families %d: %s' % (d['skinref'], len(d['skins']), d['skins'][:4]))
        print('   bodygroups:', d['bodygroups'])
