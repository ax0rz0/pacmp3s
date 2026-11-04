# Thriller zombie dance (tools)

Procedural dance + pac3 outfit generator: you and two Half-Life 2 classic zombies doing a 32-beat (16 s at 120 BPM) zombie-dance loop to music, one toggle (`pac_event thriller 2`).
The dance is an original approximation written from move descriptions (zombie march, shoulder pops, monster pose, werewolf swipes, hip thrusts, claws, side steps, spiral and shimmy); it is not a copy of a recording.

## Run
```
python make_audio.py SRC.mp3 out/audio/thriller_loop.mp3 --downbeat 353.54 --loop 32.565868       # exact loop (a whole number of dance loops), downbeat 0.25 s into the file, seam crossfade baked in
python make_thriller.py --bpm 117.914867 --suffix _v2 --music thriller_loop.mp3 --plays 0 --prefix thriller_test_ --zombie-bone nobone --extra-zombie-bone pos_noang
python make_thriller.py                                                                           # the first (120 BPM stand-in music) pack
python prev.py thr_dance2 v2                                                                      # pose sheets (matplotlib, CPU only); Prev(...).gif(...) for a looping preview
```
`--bpm` is the tempo of the music (the dance is 32 beats = one loop; the frame rate is adjusted so the loop is exactly that long). `--plays 0` loops until the dance is toggled off.
Families: ethics (Female_04), classd, isd (ISD / GOC / tech), medic, zombie. Outfits: `thriller_<family>.txt` (zombies + your dance + music) and `thriller_zombies.txt` (zombies + music).

## Files
- `thr_core.py` rig loader + pose solver (pose parameters -> ManipulateBoneAngles per bone, IK legs, finger curls) + custom_animation JSON writer.
- `thr_dance.py` / `thr_dance2.py` pose vocabulary and the choreography (key poses -> spring followers, groove nod).
- `make_thriller.py` builds and checks everything (replay of pac's linear Euler lerp vs the exact pose, loop closure, pole proximity, part counts / banned classes, URL -> repo file).
- `poles.py margins.py keypoles.py armfit2.py winscan.py swings.py` design-time checks for Euler poles (see below).

## Notes that cost time
- pac advances at most one animation frame per tick and interpolates the Euler triples linearly, so the data is kept at 30 fps with bounded joint speed (spring followers) and every bone stays well below pitch 90 (Euler pole).
- Arm solver: elbow bend plane = `b*cos(flex) - u*sin(flex)` continuation for the wrist (the old `b - fa(b.fa)` flipped sign at flex = 90 and made hands snap); the elbow bend reference is the forward axis swung along with the arm from hanging, singular only for straight-up arms.
- `pole_guard` pushes an aimed arm direction away from the Euler pole of its parent frame; `margins.py` lists where a pose path still passes close.
- Audio: pac decodes web sounds whole, so the music is a 16 s loop (one dance loop). To use your own track, cut a bar-aligned loop with `make_audio.py` (`--bpm`, `--downbeat`) and set `BPM` in `thr_dance.py` to the track's tempo.
- Zombie binding: for a player, pac resolves a part's base frame by bone name; a bone that does not exist falls back to the player's position plus EyeAngles yaw (pitch 0), `pos_ang` is `GetPos()` / `GetAngles()`, `pos_noang` is the position with zero angles (world axes). All of them ignore the body, and every real bone descends from `Bip01_Pelvis`, which the dance animates, so a body-bound anchor needs a counter-animated helper bone.
- Music: your own loop must repeat exactly; `make_audio.py --loop` takes the measured repeat period (autocorrelation peak of the 4-6 s after the downbeat, refined to sub-sample), not 64 * beat period from a tempo fit.
