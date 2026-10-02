# Emote converter: Mixamo FBX -> PAC3 custom_animation (ValveBiped playermodels)

Python 3 + numpy + Pillow/matplotlib (matplotlib only for the preview). Reads the SCP workshop pack and HL2 VPK
straight from your Steam folders to get each model's bones and base pose, so nothing needs extracting.

## Convert an animation

```
python make_emote.py "C:\path\Samba Dancing.fbx" --name samba --root-motion --out ..\..\anim --preview
python make_emote.py "...fbx" --name samba_medic  --root-motion --model models/frostbyte/cn_s65_combatmedic.mdl --out ..\..\anim
python make_emote.py "...fbx" --name samba_classd --root-motion --model models/player/kerry/class_d_7.mdl --out ..\..\anim
```

Options: `--fps 30` (keep 30, 20 fps doubles the worst-case error), `--start/--end` seconds to crop, `--ease-in 0.25`
(seconds to blend from the base pose into frame 1), `--interp linear|cosine`, `--root-motion` (hip travel, keeps feet
planted), `--no-loop`, `--decimals 1`. The script prints a playback simulation that replays the JSON exactly like pac
does and reports the error against the exact retarget (aim for max < 5 degrees), plus the loop-closure error.

Target model matters because the animation is relative to the model's base pose (its local sequence 0):
ISD, GOC and tech expert share one base (use the default ISD model), the combat medic's sequence 0 is a baton idle,
D-class has slightly different arms.

## Build the outfits

`python make_emote_outfit.py` writes `emote_samba*.txt` into garrysmod/data/pac3. Each emote is a `command` event wrapping a
`custom_animation` part whose URL is a raw GitHub link to the JSON (push `anim/` first). Trigger: `pac_event samba 2`
(toggle), e.g. `bind kp_5 "pac_event samba 2"`. `animtest` plays a tiny inline clip that checks the whole chain.

## Where Mixamo files come from

mixamo.com (free Adobe login): pick a character, an animation, download FBX Binary, "Without Skin", 30 fps, in place off
if you want hip travel. The three.js repo ships `examples/models/fbx/Samba Dancing.fbx` for quick tests.
Do not commit the Mixamo FBX itself; only the generated JSON.

## How the retarget works (short)

Each Valve bone gets a desired world rotation from the Mixamo pose, solved top-down so every manipulation angle is
relative to the already-posed parent. Spine, neck, head, clavicles, feet and toes copy Mixamo's world delta; upper arms,
forearms, thighs and calves aim along the Mixamo limb direction with minimal twist; hands aim and then spin so the palm
normals agree. Full write-up: the pac3 skill, references/emotes-custom-animation.md.
