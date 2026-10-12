import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pac_parse as pp
import pac_write as pw
t = pp.load(sys.argv[1])
def show(p, depth=0):
    s = p['self']
    keys = {k: s[k] for k in ('Model','Bone','Position','Angles','Size','Scale','Material','Materials','ModelModifiers','Skin','Color','Alpha','Hide','Event','Name','Notes') if k in s and s[k] not in ('', None)}
    print('  '*depth + '%s %r' % (s['ClassName'], s.get('Name')), {k: (v if len(str(v)) < 150 else str(v)[:150]+'...') for k, v in keys.items() if k not in ('Name','ClassName')})
    ch = p.get('children', {})
    for k in sorted(ch):
        show(ch[k], depth+1)
for k in sorted(t):
    print('[%d]' % k)
    show(t[k], 1)
