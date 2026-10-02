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

## Fortnite emotes (from the wOS "Custom Taunt" addon, workshop 2274808442)

Those addons ship ~550 Fortnite emotes already on the Valve skeleton (`models/player/custom_taunt/fortnite1..3.mdl` + `.ani`, 60 fps,
sectioned). `make_fn_pack.py` decodes them straight from the GMA (`mdl_anim.py` handles sections and external `.ani` blocks), retargets
them onto each model family with the same solver (rest poses differ by ~13 deg, so rotations are not copied blindly), picks a key rate
(30/40/60 fps) by replaying the JSON the way pac interpolates it, drops static finger chains, and appends a short blend when an emote
does not loop cleanly. `make_fn_outfit.py` writes `emote_fortnite*.txt`; `fn_preview.py` renders a blue/red skeleton overlay.

```
python make_fn_pack.py --out ..\..\anim\fn         # all emotes, families isd / medic / classd
python make_fn_pack.py --only floss --families classd --out %TEMP%\fn_test
python make_fn_outfit.py
```
Add an emote: append `(command, title, model file, sequence label)` to `SPECS` in `make_fn_pack.py` (`taunt_catalog.txt`-style listing:
every sequence label is in the three models; `f_` twins are the female-skeleton set and run at twice the length).

### Second pack (20 more) and the screening run

`make_fn_pack2.py` holds a 40-emote candidate pool (`POOL`) and the chosen 20 (`FINAL`); `screen_pool.py <family> <outdir> [keys]` builds
emotes with the same auto-key-rate pipeline as pack one (`finger_min` 60) and prints a quality row per emote. Emotes were rejected when they end far from
where they start (Pop Lock 113 deg, Disco Fever 171, Sprinkler 167, Facepalm 139, Skeleton Dance 177: the 0.35 s loop blend would look violent), work on the
floor (The Worm, Break Dance, high replay error), need a prop (Mic Drop) or are huge (Robot 1.4 MB, Treadmill 1.6 MB, Jazz 1.1 MB, Dream Feet 1 MB).
`fn_thin.py` is an adaptive keyframe-thinning experiment: it did not help (mocap-grade curvature means dropping any 60 fps frame costs about 1.2 deg), so the
shipped files use plain 30/40/60 fps selection. `EMOTES.md` lists every command with its length and example binds.

### ActMod emotes (Jabba Switchway, Get Griddy)

`make_actmod_emotes.py` converts emotes from an extracted ActMod addon (workshop 2538387266; set `ACTMOD_DIR` in `make_fn_pack.py` to the folder). ActMod keeps its Fortnite emotes as
`Amod_Fortnite_*` sequences in `models/player/ani_am4/add_fortnite/anim_m_01.mdl` (male skeleton, 30 fps); display names are in `lua/actmod/am_actmod_lan.lua`.
There is no `reference` animation, so `ValveAnimSource` uses the bind pose rotated into the game frame as the rest pose. Jabba Switchway is a 2.567 s intro followed by a 7.6 s loop
(`loop_start`, which sets `RestartFrame`); Get Griddy loops over its whole length. ActMod's page says it must not be modified or re-published, so keep the converted data private.
`find_emote_local.py <regex>` searches every installed addon for sequence or file names.


### ActMod replacements for the older emotes (`am_` files)

ActMod's own versions of Floss, Dance Moves (Default Dance), Electro Shuffle and Hip Hop (listed as "Breakdown" in ActMod) replace the wOS-derived ones in the outfits.
They are new files, `anim/am/<family>/am_<command>.json`; the old `fn_` files stay in the repo. `make_actmod_replace.py` builds them and `fn_loop.py` picks the loop window
automatically: it scores every start/end frame pair by world-rotation closure plus angular-velocity continuity and keeps the longest window within 0.75 deg of the best score
(all four are whole-clip loops, closure <= 0.2 deg, so nothing needed a blend). `make_fn_outfit.py` points the commands in `AM_KEYS` at the `am_` files.

```
python make_actmod_replace.py --out am_out                    # all four, families isd / medic / classd
python make_actmod_replace.py --out am_out --only floss --families classd
```
Emotes that exist only in the "[ActMod] More Emotes Fortnite" extension (workshop 3567487307) can be added the same way once that addon is extracted next to the main one.

### Emote music (`prep_audio.py`)

Music is a `sound2` part next to the `custom_animation`, inside the same `command` event (it starts and stops with the emote and replays `PlayCount` times).
Three timing facts decide how the file has to be cut:

- pac eases the first pose in over 0.25 s (`FrameRate 4`), so the animation runs 0.25 s behind the moment the event fires and the sound. `--rotate 0.25` moves the last 0.25 s of a seamless
  loop to the front, which puts the downbeat on the animation's first pose (and the loop stays seamless).
- Each replay of a file restarts it, so its length should be a whole number of animation loops. ActMod restarts its own sound on a timer (Jabba 7.6 s, Griddy 24.4 s). Griddy's
  animation loops every 6.0667 s, so four loops are 24.2667 s and ActMod's 24.4 s track drifts by 0.13 s per cycle. `--stretch` fits the track to the exact loop length with a pitch-preserving tempo
  change (+0.55 %, inaudible); without it the track is padded with silence or trimmed.
- ActMod's mp3s are mastered above full scale (Jabba +2.0 dBFS true peak, Griddy +0.7), so a gain is applied: `--gain -3` or `--lufs -11.4 --tp -1` (integrated loudness target plus true-peak ceiling).

```
python prep_audio.py amod_fortnite_griddle.mp3 ..\..\get_griddy.mp3 --length 24.266667 --stretch --rotate 0.25 --lufs -11.4 --tp -1
python prep_audio.py amod_fortnite_januarybop.mp3 ..\..\jabba_switchway_sync.mp3 --length 7.6 --rotate 0.25 --gain -3
```
`jabba_switchway.mp3` is the same audio without the 0.25 s shift (starts at 0). Output is 44.1 kHz stereo 192 kbps CBR, no tags; the script decodes the result again and prints length, loudness, true peak,
clipped samples and the loop-seam jump.
