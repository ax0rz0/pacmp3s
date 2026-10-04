# Fortnite emote commands

Wear `emote_fortnite` (D-class files, fine on ISD/GOC/tech), `emote_fortnite_isd` (exact for ISD/GOC/tech) or `emote_fortnite_medic`.
Trigger: `pac_event <command> 2` (toggle). Starting another emote stops the current one; press the same command again to stop.

| command | emote | length |
|---|---|---|
| `floss` | Floss (ActMod) | 1.6s loop |
| `dance` | Default Dance (ActMod) | 6.8s loop |
| `takethel` | Take the L | 2.1s |
| `deepdab` | Deep Dab | 1.6s |
| `infinidab` | Infinite Dab | 2.2s |
| `electro` | Electro Shuffle (ActMod) | 8.4s loop |
| `fresh` | Fresh (ActMod) | 5.1s loop |
| `wiggle` | Wiggle | 3.2s |
| `moonwalk` | Moonwalk | 2.1s |
| `ragequit` | Rage Quit | 3.9s |
| `windmill` | Windmill Floss | 2.7s |
| `boneless` | Boneless | 3.2s |
| `swipeit` | Swipe It | 3.5s |
| `shoot` | Shoot | 3.9s |
| `bunnyhop` | Bunny Hop | 2.1s |
| `crab` | Crab Rave | 3.9s |
| `candy` | Candy Dance | 4.2s |
| `electroswing` | Electro Swing (ActMod extension) | 8.0s loop |
| `twist` | Twist | 5.5s |
| `zippy` | Zippy Dance | 3.7s |
| `smoothride` | Smooth Ride | 3.9s |
| `hotstuff` | Hot Stuff | 2.0s |
| `fancyfeet` | Fancy Feet | 2.1s |
| `takethew` | Take the W | 2.3s |
| `onearmfloss` | One Arm Floss | 2.5s |
| `hiphop` | Hip Hop / Breakdown (ActMod) | 7.3s loop |
| `hula` | Hula | 3.6s |
| `yeet` | Yeet | 1.7s |
| `calculated` | Calculated | 1.8s |
| `hitwoah` | Hit the Woah | 0.9s |
| `showstopper` | Showstopper | 3.7s |
| `jabba` | Jabba Switchway (ActMod) | 10.2s (intro once, then loops) |
| `griddy` | Get Griddy (ActMod) | 6.1s loop |
| `pockets` | Empty Out Your Pockets (ActMod extension) | 10.8s (0.4s intro once, then a 10.4s loop) |
| `outwest` | Out West (ActMod) | 6.8s loop |
| `mufasa` | Go Mufasa (ActMod) | 7.6s loop |
| `maskoff` | Mask Off (ActMod extension) | 13.6s (0.8s intro once, then a 12.8s loop) |
| `toosie` | Toosie Slide (ActMod extension) | 5.9s loop |
| `droop` | Droop (wOS `CrazyDance`, re-timed to its real 30 fps speed) | 7.4s loop |
| `orangejustice` | Orange Justice (ActMod, 60 fps keys for the fast arm swings) | 7.1s (0.6s intro once, then a 6.5s loop) |
| `thoughtiwasdead` | Thought I Was Dead (ActMod AM4 Expansion Pack, Tyler, The Creator) | 19.1s (4.3s intro once, then a 14.8s loop) |
| `chickenwing` | Chicken Wing It (ActMod) | 10.4s (3.4s intro once, then a 7.0s loop) |
| `zany` | Zany (ActMod extension) | 9.1s loop |
| `scenario` | Scenario (ActMod extension) | 8.1s loop |
| `smoothmoves` | Smooth Moves (wOS `Kpop_02`, re-timed to its real 30 fps speed) | 7.7s loop |

Emotes marked ActMod come from the ActMod addons (`anim/am/` for floss, dance, electro, hiphop, fresh and electroswing; `anim/fn/` for jabba, griddy, pockets, outwest, mufasa, maskoff, toosie, orangejustice, thoughtiwasdead, chickenwing, zany, scenario and smoothmoves); the others are the wOS "Custom Taunt" versions.

Music: the generated outfits already hold a `sound2` part in the event of `jabba`, `griddy`, `dance`, `electro`, `hiphop`, `fresh`, `pockets`, `outwest`, `mufasa`, `maskoff`, `toosie`, `electroswing`, `droop`, `orangejustice`, `thoughtiwasdead`, `chickenwing`, `zany`, `scenario` and `smoothmoves` (the audio setup comes from the user's saved outfit). Files in the repo root,
raw link `https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/<file>`:

| file | emote | what was done to ActMod's file |
|---|---|---|
| `jabba_switchway.mp3` | `jabba` | padded to the 7.6 s loop, -3 dB |
| `jabba_switchway_sync.mp3` | (optional) | same, rotated 0.25 s so the beat lands on the animation's first pose |
| `get_griddy.mp3` | `griddy` | tempo-fitted to four animation loops (24.27 s, +0.55 %), rotated 0.25 s, -1.8 dB |
| `default_dance.mp3` | `dance` | trimmed to the 6.8 s animation loop (the 0.4 s tail is mixed onto the start), -2 dB |
| `electro_shuffle.mp3` | `electro` | none, byte-identical to ActMod's `emote_electroshuffle_01.mp3` (7.56 s) |
| `hip_hop.mp3` | `hiphop` | none, byte-identical to ActMod's `S5_HipHop_B_Loop.mp3` (14.5 s, two animation loops); it is mastered loud (-7.3 LUFS), so its part plays it at `Volume 0.6` |
| `fresh.mp3` | `fresh` | none, byte-identical to the extension's `emote_fresh_music01.mp3` (5.05 s, one animation loop); its part plays it at `Volume 0.85` |
| `empty_out_your_pockets.mp3` | `pockets` | none, byte-identical to the extension's `Emote_KelpLinen_C_Loop.mp3` (20.87 s, exactly two animation loops); `Volume 0.7`. ActMod also plays a 0.4 s intro sting (`Emote_KelpLinen_C_Intro.mp3`) before it, which is left out |
| `out_west.mp3` | `outwest` | none, byte-identical to ActMod's `amod_fortnite_julybooks.mp3` (27.33 s, exactly four animation loops); `Volume 0.6` (mastered at -7.7 LUFS, +1.7 dBTP) |
| `go_mufasa.mp3` | `mufasa` | none, byte-identical to ActMod's `amod_fortnite_sandwichbop.mp3` (7.57 s, one animation loop); `Volume 0.6` (-7.7 LUFS, +2.3 dBTP) |
| `mask_off.mp3` | `maskoff` | none, byte-identical to the extension's `Emote_Reveal_2.mp3` (6.4 s loop, half an animation loop); `Volume 0.6` (-8.3 LUFS, +3.7 dBTP). The 0.8 s intro `Emote_Reveal_1.mp3` is left out |
| `toosie_slide.mp3` | `toosie` | none, byte-identical to the extension's `Emote_Art_Giant01.mp3` (35.2 s, exactly six animation loops); `Volume 0.75` (-9.5 LUFS, +1.2 dBTP) |
| `electro_swing.mp3` | `electroswing` | none, byte-identical to the extension's `Emotes_ElectroSwing.mp3` (16.0 s, exactly two animation loops); `Volume 0.6` (-7.6 LUFS, +2.1 dBTP). This is the track `electro` used to share by accident, see below |
| `droop.mp3` | `droop` | no game file exists, so it was cut from the emote's preview video (the game's own audio): one 16-beat phrase (130 BPM, 7.385 s) from the second repeat with a 6 ms seam crossfade, tempo-fitted by -0.66 % to the 7.433 s animation loop, started where the dance's first frame lands after pac's 0.25 s ease-in, normalized to -12 LUFS (-1.5 dBTP). Source: 4nite.site/videos/emotes/droop.mp4 |
| `orange_justice.mp3` | `orangejustice` | none, byte-identical to ActMod's `Hip_Hop_Good_Vibes_Mix_01.mp3` (18.94 s = three 6.32 s phrases at 152 BPM; the shop preview plays the same audio, and the dance loops every 6.5 s there too, so the two drift against each other in the game as well); `Volume 1.2` because it is a quiet master (-15.7 LUFS, -1.7 dBFS peak) |
| `thought_i_was_dead.mp3` | `thoughtiwasdead` | none, byte-identical to the pack's `Emote_CanineCronutMix_2.mp3` (14.8 s loop = one animation loop); `Volume 0.45` because it is mastered extremely hot (-5.5 LUFS, +5.1 dBFS peak). ActMod also has a 4.07 s intro (`_1`) and a second variant (`_3` / `_4`, 4.14 s and 14.92 s), neither used |
| `chicken_wing_it.mp3` | `chickenwing` | none, byte-identical to ActMod's `amod_fortnite_noodles_loop.mp3` (13.93 s, two animation loops); `Volume 0.6` (-6.6 LUFS, +1.0 dBFS). The 3.4 s intro track is left out |
| `zany.mp3` | `zany` | none, byte-identical to the extension's `Emotes_Bendy.mp3` (9.14 s, one animation loop); `Volume 0.65` (-9.2 LUFS, +2.8 dBFS) |
| `scenario.mp3` | `scenario` | none, byte-identical to the extension's `Emote_KPopDance03.mp3` (32.54 s, exactly four animation loops, 118 BPM); `Volume 0.95` (-11.8 LUFS, +0.1 dBFS) |
| `smooth_moves.mp3` | `smoothmoves` | no game file exists, so it is the music of the emote's preview video (4nite.site/videos/emotes/smooth-moves.mp4): it repeats sample-exactly every 19.2 s (8 bars at 100 BPM), so the file is a cyclic 19.2 s window starting 0.25 s before the loop start, normalized to -12 LUFS (-1.4 dBTP). The dance loops every 7.67 s, so the two drift against each other (as in the game) |

Every event uses `Operator equal`. pac's default is `find simple`, a substring test, so `pac_event electroswing 2` also switched on the `electro` event and played Electro Shuffle's music (and `pac_event onearmfloss 2` also fired `floss`). Binds are unchanged.

Example binds (paste into the console):

```
bind kp_0 "pac_event floss 2"
bind kp_1 "pac_event dance 2"
bind kp_2 "pac_event takethel 2"
bind kp_3 "pac_event deepdab 2"
bind kp_4 "pac_event infinidab 2"
bind kp_5 "pac_event electro 2"
bind kp_6 "pac_event fresh 2"
bind kp_7 "pac_event wiggle 2"
bind kp_8 "pac_event moonwalk 2"
bind kp_9 "pac_event ragequit 2"
bind kp_enter "pac_event windmill 2"
bind kp_plus "pac_event boneless 2"
bind kp_minus "pac_event jabba 2"
bind kp_multiply "pac_event griddy 2"
```
