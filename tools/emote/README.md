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
The "[ActMod] More Emotes Fortnite" extension (workshop 3567487307, 60.6 MB) adds `anim_m_04` / `anim_m_05` to the same `add_fortnite` folder: extract it and point `ACTMOD_EXT_DIR` (environment variable, see `make_fn_pack.py`) at its `models/player/ani_am4`.
It is what `fresh` (a replacement, `make_actmod_replace.py`) and `pockets` (Empty Out Your Pockets, a new emote in `make_actmod_emotes.py`) are built from. Its `lua/actmod/am_animc/am4_fortniteme.lua` lists every emote with `Config.Name`, `Custom.Anim = { Time2 = loop seconds, Cycle = loop start as a fraction of the clip }`, `Custom.Sound = { Time1, Time2 }` (sound restart timers) and `Sounds = { Start, StartExtra (with a Delay), Repeat }`. `pockets` is `Amod_Fortnite_KelpLinen_C`: a 0.367 s intro (frame 11), then a 10.433 s loop, matching `Cycle 0.03395` and `Time2 10.43333`.
Workshop items can be fetched without a Steam login: Valve's `steamcmd` (signed by Valve, from steamcdn-a.akamaihd.net) with `+login anonymous +workshop_download_item 4000 <id> +quit` writes `<id>_via_crowbar.gma`.
`maskoff` (Future's Mask Off, `Amod_Fortnite_Reveal`) also comes from the extension: a 0.767 s intro (frame 23), then a 12.8 s loop. `outwest` (`JulyBooks`) and `mufasa` (`SandwichBop`) are in the main addon and loop over their whole clips. ActMod's audio for Out West, Go Mufasa, Jabba Switchway, Bust a Move, My World, Oki Doki, Groove Destroyer, Deep Explorer, Humble and Two is Epic's censored version; the workshop addon 3566843414 ("Uncensored Fortnite Icon Emote Audio For ActMod", 3.9 MB) replaces it.
`toosie` (Drake's Toosie Slide, `Amod_Fortnite_ArtGiant`, 5.867 s) is also from the extension and loops over its whole clip; its pelvis travels about 24 units sideways inside the loop and the loop seam is under 0.3 units.
`electroswing` now uses the extension's `Amod_Fortnite_Electroswing` (8.0 s loop, `am_electroswing.json`) and its own 16 s track. `droop` (Droop = `EID_CrazyDance`) comes from the wOS pack's male `CrazyDance`, which is tagged 60 fps although the game animation is 30 fps (7.4 s, 223 frames; the intro is a separate 0.67 s clip), so `build(src_fps=30)` / the 7th field of `SPECS` re-times it. The 'All Fortnite emotes in one model' SFM packs (workshop 2189312269 and 2967034278, direct zip downloads) keep each animation's native fps and match ActMod's durations for all 12 emotes checked, so they are the reference for the true speed. Against them the wOS male set is at the right speed for Wiggle, Moonwalk, Windmill Floss, Boneless, Swipe It, Shoot, Zippy, Take the W and Hula, and runs twice too fast for Deep Dab, Rage Quit, Crab Rave, Twist, Hot Stuff, Fancy Feet, Yeet, Calculated and Showstopper (the others had no clear match).
`droop.mp3` shows how to get audio when no addon has it: fan sites such as 4nite.site keep the item-shop preview of every emote as `https://4nite.site/videos/emotes/<name>.mp4` (45 s, 588x940, AAC stereo, very quiet, about -41 LUFS) and that is the game's own mix. The video repeats the dance, so the audio gives the loop (onset autocorrelation: 130 BPM beat 0.4615 s, phrase 7.3846 s), and the dance's frame 0 is located in the video by correlating the video's motion energy with the animation's (here at 0.87 s, after a 0.67 s intro). The loop is cut so the file starts 0.25 s (pac's ease-in) before that point. Plain `curl` fails on some of these hosts on this machine (libcurl error 43); Python `urllib` with a browser User-Agent works. Fandom wiki pages are behind a Cloudflare challenge.
`orangejustice` (`EID_GoodVibes`; ActMod calls it `maskoff`, display name Orange Justice, sequence `Amod_Fortnite_MaskOff` in `anim_m_03`) has a 0.6 s intro and a 6.5 s loop. Its arms swing so fast that 30 fps keys leave a replay error of p99 7.2 / max 22 degrees (pac Euler-lerps between keys); 60 fps keys bring it to p99 2.2 / max 7 at 1.2 MB, so `SPECS` entries take an 8th field, the key fps (default 30), and this one uses 60.
`thoughtiwasdead` (Tyler, The Creator's Icon Series emote from November 2025, internal name `CanineCronutMix`) comes from the "[ActMod] AM4 Expansion Pack" (workshop 3682041393, 87.5 MB, the 'Commission Hub'): its animations are in `models/player/ani_am4/m_ani_01.mdl`, so `make_fn_pack.taunt()` accepts `actmodexp:m_ani_01` (extracted folder in `ACTMOD_EXP_DIR`). One `lua/actmod/am_animc/s_fortnite_<name>.lua` per emote holds the config: for this one `Cycle 0.2238` (intro 4.27 s, frame 128) and `Time2 14.8`. The emote throws a prop (a cronut) that ActMod animates with a script; the pac version does not reproduce it. `chickenwing` is ActMod's `noodles` (3.43 s intro, 6.97 s loop) and `zany` the extension's `Bendy` (whole 9.1 s clip loops, closure 0.14 degrees).
`scenario` is the extension's `KPOPDance_03` (whole 8.13 s clip loops, music exactly four loops). `smoothmoves` (`EID_KPopDance02`, ActMod language id `kpop_02` but no animation or sound in the extracted addons) is the wOS `Kpop_02`, re-timed with the 7th `SPECS` field like `droop`; its audio comes from the emote's preview video, where the music repeats sample-exactly every 19.2 s, so any 19.2 s window is a seamless loop (cut so it starts 0.25 s before the loop start; the dance itself loops every 7.67 s and is not locked to the music).
The extension also holds Take The L (`DanceLoser`), Infinite Dab, Wiggle, Crabby (`CrabDance`), Electro Swing, Twist, Fancy Feet and One Arm Floss ("No Sweat"), which are not converted yet.

### Emote music (`prep_audio.py`)

Music is a web sound (`sound2`) part next to the `custom_animation`, inside the same `command` event: it starts when the event shows the part and `StopOnHide` stops it with the emote.
`PlayCount` is how often the file plays (0 = loop forever). pac downloads the whole file into `data/pac3_cache/downloads` first, so only the first play can lag.
`make_fn_outfit.py` writes these parts for `jabba` and `griddy` (`MUSIC`: file and PlayCount 13 / 51, `Radius 500`, `Bone head`, `StopOnHide`), copied from the setup saved in game,
so the generated outfits already carry the audio.
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
`jabba_switchway.mp3` is the same audio without the 0.25 s shift (starts at 0). The user prefers the ActMod audio left alone where possible, so `electro_shuffle.mp3` is ActMod's file as it is (ActMod loops it every 7.56 s
while the animation loops every 8.43 s, so the two run independently there too) and `default_dance.mp3` is only cut to the 6.8 s animation loop (`--length 6.8 --wrap-tail --lufs -11.4 --tp -1`). `hip_hop.mp3` is ActMod's `S5_HipHop_B_Loop.mp3` as it is; its `sound2` part uses `Volume 0.6` (`VOLUME` in `make_fn_outfit.py`) because the track is mastered at -7.3 LUFS. Rage Quit has no music in ActMod or the wOS pack, and the user dropped it. Output is 44.1 kHz stereo 192 kbps CBR, no tags; the script decodes the result again and prints length, loudness, true peak,
clipped samples and the loop-seam jump.
