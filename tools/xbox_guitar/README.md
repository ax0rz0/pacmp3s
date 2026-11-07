# Xbox + guitar pacs (Ethics Assistant rig)

Generators for two `pac_event` toggles that live in `eca main 4`:

* `pac_event xbox 2` — a table, a TV and a console in front of you. You hold a pad (`models/maxofs2d/button_06.mdl`) in your left hand, lean in and press the console's power button, the LED
  lights up and the TV plays a real Xbox One boot (a few frames a second, with the startup sound) into the real home screen while you stand there holding the pad with both hands.
  After four seconds on the home screen the TV goes dark and loops 6.25 s of real Xbox One gameplay (a Need for Speed Rivals capture) with its sound.
* `pac_event guitar 2` — a Martin D-45 (`models/custom/guitar/m_d_45.mdl`, the velkon_guitar model) on your chest, playing Brain Damage (instrumental recording). The picking hand and body are scrubbed
  along the recording's real beats; the fretting hand follows the chords detected in the recording.

Both are built for the female_04 Ethics Assistant rig (`tc.rig_for('ethics')`, ~62 units tall).

## Assets they use (in the repo root / `anim/` / `tex/`)

| file | what |
|---|---|
| `anim/xbox/ethics/xbox_ethics_v2.json` | the gesture (109 frames at 30 fps, holds the last pose) |
| `tex/xbox/xbox_screen_game.vtf` | 62 frames, 512x256 DXT1, stepped by a proxy on `frame`: 23 of the real Xbox One boot capture, 1 black, 38 of the gameplay loop (6.08 frames a second) |
| `xbox_startup.mp3` | the boot capture's audio, mono, behind 2.0 s of silence (the TV boots 2.0 s after the toggle) |
| `xbox_game_loop.mp3` | the gameplay loop's audio, mono, 6.25 s with a 0.2 s crossfade at the seam, about -20 LUFS; `sound2` `PlayCount 0` under a `timerx` event that fires 21 s after the toggle, when the picture loop starts |
| `anim/guitar/ethics/guitar_play_ethics.json` | layer A: body sway, nod, foot tap, right (picking) hand; one 2-beat pattern, played with `Rate 0` and a proxy on `Offset` |
| `anim/guitar/ethics/guitar_chords_ethics.json` | layer B: left (fretting) hand, 48 chord changes over the whole song, holds the last chord |
| `brain_damage.mp3` | the recording, mono 96 kbps, 0.25 s of lead silence (the animations' ease-in) |

`xbox_ethics.json`, `xbox_boot.vtf` (drawn screen) and `xbox_boot_real.vtf` (boot frames only) are earlier versions and are no longer used.

## How the guitar syncs

`song_analysis.py` / `song_analysis2.py` decode `~/Downloads/braindamage.mp3`, track the beats (66 BPM, 256 beats, drifting between 65 and 69 BPM) and read a chord root per beat from chroma.
`song_warp.py` turns the beat times into a piecewise-linear tempo curve written as a sum of `max(timeex() - t, 0)` hinge terms: that is the expression of the proxy that drives the
animation's `Offset` (the old pac build scrubs an animation by `Offset` when its `Rate` is 0, so the pose depends only on the clock, not on the frame rate). `song_chords.py` turns the chord
roots into left hand shape changes. The picking pattern itself comes from `midi_guitar.py` (a MIDI of the song).

## Rebuild

```
python guitar_outfit.py            # layers + outfit text, writes anim/guitar/ethics/*.json (needs the mp3 / MIDI in ~/Downloads, see the paths in song_analysis.py / midi_guitar.py)
python xbox_outfit.py              # gesture + real-capture VTF + startup sound
python assemble_eca4.py            # eca main 3 (untouched) + both roots -> data/pac3/eca main 4.txt
python write_standalones.py        # outfits/xbox_guitar/*.txt
```

The Xbox screen needs two captures from the Internet Archive and `ffmpeg` on the PATH (default `$XBOX_WORK` = the folder above this one):
`2013-xbox-one-pal-gameplay-full-demostration-startup-sequence` (the `.mp4`) saved as `$XBOX_WORK/xbox_real/dl/xboxone2013/xboxone2013.mp4`, and
`youtube-c-9_lkuVW9c` (Need for Speed Rivals gameplay) saved as `$XBOX_WORK/xbox_real/dl/nfsrivals/nfsrivals.mp4`.
`xbox_real.TIMES` lists the source-clip times of the boot frames, `GAME_START` / `GAME_LEN` / `GAME_N` pick the gameplay loop (`gameplay_loop.py` scans the clip for start / length pairs whose
last frame looks most like the first; `T_BLACK` / `T_GAME` say when the TV goes dark and the loop starts).

## Known limits

* Not checked in game yet (CPU stick-figure previews only). Hands are fitted by fingertip targets; the solver (`thr_core.Solver.solve`) leaves the finger bones' world positions (`AP`) at the
  straight-finger values, so the fits ignore the finger curl and the curled fingers sit up to ~2-3 units short of the target in game. Fix: set `AP[bidx] = AP[p] + AR[p] @ r.Lp[bidx]` in its finger
  loop and re-run the fits.
* The Xbox boot frames and startup sound are Microsoft's, the guitar recording is Pink Floyd's.
