import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdl_tex import info
P = os.path.join(r'C:\Users\poopy\Downloads\cg_scp_pm_combined_2830971578', 'models')
for m in sys.argv[1:]:
    d = info(open(os.path.join(P, *m.split('/')), 'rb').read())
    print('\n== %s (v%d, %d bones)' % (m, d['version'], d['bones']))
    print('   cdmaterials:', d['cdmaterials'])
    for i, t in enumerate(d['textures']):
        print('   tex[%2d] -> Materials slot %2d: %s' % (i, i + 1, t))
    print('   skinref %d, families %d' % (d['skinref'], len(d['skins'])))
    for name, models in d['bodygroups']:
        print('   bodygroup %-12s %s' % (name, models))
