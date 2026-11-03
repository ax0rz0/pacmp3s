# Thriller zombie dance (tools)

Procedural dance + pac3 outfit generator: you and two Half-Life 2 classic zombies doing a 32-beat (16 s at 120 BPM) zombie-dance loop to music, one toggle (`pac_event thriller 2`).
The dance is an original approximation written from move descriptions (zombie march, shoulder pops, monster pose, werewolf swipes, hip thrusts, claws, side steps, spiral and shimmy); it is not a copy of a recording.

## Run
```
python make_audio.py SRC.ogg out/audio/thriller_dance.mp3 --downbeat 270.0708      # 16 s loop, downbeat 0.25 s into the file, seam crossfade baked in
python make_thriller.py                                                             # animations -> anim/thriller/<family>/, mp3 -> repo root, outfits -> data/pac3 + outfits/thriller/
python prev.py thr_dance2 v2                                                        # pose sheets (matplotlib, CPU only); Prev(...).gif(...) for a looping preview
```
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
