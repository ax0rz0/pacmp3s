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
| `fresh` | Fresh | 5.1s |
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
| `electroswing` | Electro Swing | 4.4s |
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

Emotes marked ActMod come from the ActMod addon (`anim/am/` for floss, dance, electro and hiphop; `anim/fn/` for jabba and griddy); the others are the wOS "Custom Taunt" versions.

Music: the generated outfits already hold a `sound2` part in the event of `jabba`, `griddy`, `dance`, `electro` and `hiphop` (the audio setup comes from the user's saved outfit). Files in the repo root,
raw link `https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/<file>`:

| file | emote | what was done to ActMod's file |
|---|---|---|
| `jabba_switchway.mp3` | `jabba` | padded to the 7.6 s loop, -3 dB |
| `jabba_switchway_sync.mp3` | (optional) | same, rotated 0.25 s so the beat lands on the animation's first pose |
| `get_griddy.mp3` | `griddy` | tempo-fitted to four animation loops (24.27 s, +0.55 %), rotated 0.25 s, -1.8 dB |
| `default_dance.mp3` | `dance` | trimmed to the 6.8 s animation loop (the 0.4 s tail is mixed onto the start), -2 dB |
| `electro_shuffle.mp3` | `electro` | none, byte-identical to ActMod's `emote_electroshuffle_01.mp3` (7.56 s) |
| `hip_hop.mp3` | `hiphop` | none, byte-identical to ActMod's `S5_HipHop_B_Loop.mp3` (14.5 s, two animation loops); it is mastered loud (-7.3 LUFS), so its part plays it at `Volume 0.6` |

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
