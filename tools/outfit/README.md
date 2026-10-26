# BNA outfit tools

Generators for the BNA-palette outfits in `outfits/bna/` (own textures and own geometry, linked by raw GitHub URL):

| outfit | made by | what it is |
|---|---|---|
| `d-class low sec bna.txt` | `make_dclass_outfit.py` | copy of `d-class low sec.txt`, emote pack removed, gray uniform kept, BNA accessories only |
| `ethics asst bna formal / anima / neon.txt` | `make_ethics_textures.py`, `make_ethics_outfits.py` | three re-textured Ethics Assistant looks on `jericho/citizens/female_04`; only Anima has ears, none has a tail |
| `tech expert bna.txt` | `make_tech_textures.py`, `make_tech_outfit.py` | copy of `tech expert.txt` (its groups untouched) with a pink / navy retexture through a group of material parts and a tech accessory group |

Palette: PINK `#fc2c9d`, MAGENTA `#c62c80`, INDIGO `#554eae`, ROYAL `#21388c`, NAVY `#0f215e`. Every generated outfit starts with `-- claude skill made by ax0rz0`, has `Notes` on each top-level group and UniqueIDs ending in `a0c3f`.

## Requirements

Python 3 with numpy, scipy, Pillow and opencv-python. Paths of the local machine are constants at the top of `ethics_common.py` (SCP playermodel pack, HL2 VPKs), `dclass_scene.py`, `make_*_outfit*.py` (the `data/pac3` folder) and `ethics_styles.py` (fonts); adjust them if the folders move.
Generated caches and previews go to `ethics/`, `stage_bna/` and `tech/` next to the scripts (git-ignored).

## Running

```
python make_dclass_outfit.py
python verify_derivative.py "stage_bna/outfits/d-class low sec bna.txt" "<data/pac3>/d-class low sec.txt" stage_bna --n-original 4

python make_ethics_textures.py            # once: position maps + painted textures (make_ethics_textures.py --check compares with the cache)
python make_ethics_outfits.py [formal anima neon]
python verify_ethics.py stage_bna "stage_bna/outfits/ethics asst bna formal.txt" ...

python make_tech_outfit.py                # also paints the textures when they are missing
python verify_tech.py "stage_bna/outfits/tech expert bna.txt" "<data/pac3>/tech expert.txt" stage_bna
```

Publishing (the order matters, pac caches a 404 for a url and keeps it until `pac_restart`):

1. copy `stage_bna/obj/bna/*` to `obj/bna/`, `stage_bna/tex/bna/*` to `tex/bna/` and `stage_bna/outfits/*.txt` to `outfits/bna/`, commit and push;
2. `python wait_assets_live.py stage_bna 8 tech_` (prefixes `dclass_`, `ethics_`, `tech_`) until every file is live with the right size;
3. only then copy the outfit txt into `garrysmod/data/pac3` and load it fresh in the editor (do not save an old editor session over it).

Previews (point-splat renderer, no game needed): `run_tech_preview.py orig|slots|bna`, `run_tech_acc.py bind|game full|head|arm|pack|chest [views] [height]` (`game` renders the body deformed by the outfit's feminiser bone scales with the accessories placed the way pac draws them), `dclass_fit_check.py`. Close-ups are memory hungry (keep the height at 460 or lower while Garry's Mod runs). `inspect_models.py`, `show_tree.py` print model slots / an outfit's part tree.

## How it works

* **Textures** are `material_3d` parts whose `basetexture` is the url of a PNG (`bna_parts.material_part`, built from a real saved part of the server's pac: `material_template.py`). pac downloads the file with a plain HTTP request (`pac.resource.DownloadTexture`; png, jpg and vtf are accepted), loads it wrapping and with mipmaps, and other parts use the material part **by name**: the `Materials` list of an `entity2` (one entry per model material slot, 1-based, `null` hides a slot) and the `Material` of a `model2`. pac re-resolves these names after the whole outfit is loaded (each part's first think), so the order of the parts does not matter. The same route is what `mf doom thaum.txt` uses for its badge. Keep every texture under 1 MB (servers may cap web content with `sv_pac_webcontent_limit`); the dark cloth atlases of the tech expert are 256-colour PNGs.
* Image urls written straight into `Materials` / `Material` take another route: a hidden browser panel renders the image into a 1024x1024 square (no mipmaps, ` noclamp` flag for wrapping). That is what the first version of these outfits used and it did not show on the server, so do not use it.
* With several `entity2` parts in one outfit only the last one shown draws (it replaces `ent.RenderOverride`), so `make_tech_outfit.py` names the material parts in both entity2 parts of the original and keeps their `null` slots; the material parts sit in a first group of their own.
* **Accessories** are authored in world space (x forward, y left, z up, bind pose) on the real body surface (ray casts) and baked into **bone-local OBJs** (`Position`/`Angles` stay 0, `Size` equals the entity2 size). Bone names are the pac friendly names (`head`, `spine 4`, `left forearm`, ...). Closed shapes are wound outward, UVs are only used by textured parts, every OBJ carries the watermark comment.
* **Ethics textures** are painted in UV space from position maps (`uvmap.py`): every texel knows its 3D position, so stripes, cuffs, gradients and the vector emblem are defined on the body. **Tech expert textures** keep the original atlases and recolor them (`tech_paint.py`: orange to PINK, white to lavender white, gray cloth through NAVY / ROYAL / INDIGO ramps).
* **Feminiser bone scales** (`bone3` parts on pelvis, thighs, upper arms) are inherited by child bones in game while pac draws a part at the bone's position and angles only. `tech_deform.DeformedRig` emulates that (bone matrices with the scales, Source `MatrixAngles` of the sheared matrix) and localises the accessories accordingly. The D-class outfit was generated before this existed (plain bind pose, about 0.4 units looser at the wrists).

## Modules

| file | role |
|---|---|
| `vtf.py`, `vpk_tools.py`, `mdl_mesh.py`, `mdl_tex.py`, `mdl_anim.py` | VTF / VPK / MDL (+VVD, VTX) readers |
| `uvmap.py`, `preview.py`, `meshgen.py` | position maps, point-splat renderer, mesh generators (torus, tube, ribbon, card, bow, ...) |
| `pac_parse.py`, `pac_write.py`, `bna_parts.py`, `material_template.py` | read / write pac3 outfit files byte-exactly, part builders (model2, sprite, material_3d), asset staging |
| `ethics_*.py`, `scene.py` | femsuit_04 body, painters, accessory builders for the Ethics looks |
| `dclass_*.py` | class_d_mike body (+ bonemerged Female_04 head) and the D-class accessories |
| `tech_*.py` | technical_expert body, recolor, accessories, deformation, previews |
| `verify_*.py`, `check_live.py`, `wait_assets_live.py` | checks of the generated files and of the published urls |

## Not verified in game

The material_3d + url PNG route on the server (it is the one `mf doom thaum.txt` uses), the bodygroup choices through `ModelModifiers`, the material slot numbers on the actual job models (the Ethics Assistant model is assumed to be `jericho/citizens/female_04`), bone friendly names, accessory fit in animation poses, glow sprites, and which of the tech expert's two entity2 parts draws.

## Advanced Ethics Assistant outfits (`outfits/adv/`, `obj/adv/`)

Eight outfits for `jericho/citizens/female_04` (six with own geometry; the head-only one and the researcher are built from the custom head package, the researcher also bone-merges a job model's coat), made with the `adv_*` modules. No `light`, `halo`, `projected_texture`, `shake` or `sunbeams` parts anywhere; every outfit stays under the
"heavy above" values of the PAC outfit cost window (checked by `adv_parts.validate`: URL models <= 16, model parts <= 60, proxies, particle emitters <= 4, no URL textures).

| outfit | made by | what it is | console |
|---|---|---|---|
| `ethics asst cyber oni.txt` | `make_adv_oni.py` | robotic oni mask: hard-surface plates on a black under-layer, glowing visor slits, hinged jaw (follows the voice meter), two short swept-back horns, ear cups, hoses | `pac_proxy oni_theme 0-3` accent colour, `pac_proxy oni_jaw 0-1` open the jaw |
| `ethics asst netrunner.txt` | `make_adv_net.py` | respirator face cover with hex vents + filters, right-eye cyber implant, headset, silver hair with a neon-tipped swinging ponytail (jiggle), black gloves + vambraces, fingertip trails | `nr_theme 0-3`, `nr_hair 0-3` |
| `ethics asst netrunner custom head.txt` | `make_adv_net_custom.py` | the same without the hair, on a **donor head** (see below): mask / implant / headset re-fitted to her face (`adv_panels.WarpSurf`) | `nr_theme 0-3` |
| `ethics asst custom head.txt` | `make_adv_head_swap.py` | nothing but the custom head package: an entity2 that hides the player's head slots + the `custom head` group | - |
| `ethics asst researcher.txt` | `make_adv_researcher.py` | the small blend-in one: a white lab coat over a dark shirt and tie (the Armacham scientist model `models/armacham/scientists/scientists_1.mdl` of the SCP playermodel pack, bone-merged, only its `suit_shirt` / `body_scientist` / `tiesandties` slots drawn), the player's own suit and head hidden, plus the custom head package | - |
| `ethics asst ghost.txt` | `make_adv_ghost.py` | spectral archivist: additive translucent body that hovers (a `bone3` on the pelvis: an entity2 offset is a draw-time matrix, the bones every attached part reads do not follow it), porcelain veil mask, hood + veil strips, glowing spine / ribs / core with gyro rings, ragged shroud, chains (cloth and chains sway through jiggle parts), plasma trails, soul motes | `gh_theme 0-3` |
| `ethics asst protocol unit.txt` | `make_adv_cyborg.py` | cyborg: left half of the face is a chrome endoskeleton (lens eye, steel teeth, piston), neck collar, heavy left arm (pauldron, elbow ball, gauntlet), back reactor with steaming vents | `cb_theme 0-3` |
| `ethics asst neon seraph.txt` | `make_adv_seraph.py` | cyber angel: data-wings that breathe, sweep back with running speed and flap / spread on demand, translucent visor, shoulder fins, hologram ring on the left forearm, four orbs circling the waist, wing-tip trails | `sr_theme 0-3`, `sr_open 0-1`, `sr_flap 0-1` |

Accent colours are blended by a proxy named like the console command (the old pac build reads `command()` from the proxy's own name, so the names matter).

**Custom head package** (`adv_head_pkg.py` + `adv_head_obj.py` + `adv_neck.py`, Song So Mi from Cyberpunk 2077: Phantom Liberty, Workshop 3283215678): nothing needs the Workshop addon, pac downloads the head itself
from this repo. The donor's compiled model is only read (never run), skinned into the Ethics Assistant's bind frame the way BoneMerge would, moved into the head bone's frame and written as static meshes
(`obj/adv/hd_*.obj`, every file under 1 MiB) with their textures (`tex/adv/hd_*.png|jpg`, the VMT `$color2` tints baked in): `hd_head.obj` (skin cut under the skull + the eyeballs, texture
`hd_head.jpg` 2048x1024), `hd_extras.obj` (lipstick, eye makeup, brows, cyberware lines, lashes and the nape port, one translucent atlas), `hd_hair_a|b|c.obj` (alpha tested hair cards, `hd_hair.png` palette
png), `hd_neck_b.obj` (a skin neck on the neck bone whose uvs borrow a patch of the head texture; the donor has no neck below the jaw and the player's own neck goes with her head slot).
Materials are `material_3d` parts with url basetextures used by name (`hd skin`, `hd extras`, `hd hair`). The outfit's entity2 hides the player's head slots (1 chau_facemap = head AND neck, 2 / 3 eyeballs,
4 mouth). The head is rigid on the head bone (no lip sync / blinking). `make_adv_head_swap.py <outfit>` also adds the package to an editor-saved outfit with a single entity2 by plain text edit (that outfit's
other bytes stay identical) and writes the result as a new file.

**Colour ranges:** `trail2` `StartColor` / `EndColor` are 0..1 (`ProperColorRange`, multiplied by 255 when drawn), `sprite` and `particles` colours are 0..255, `model2` / `material_3d` colours are 0..1.
`adv_parts.trail` takes 0..255 and writes 0..1; a proxy driving a trail colour uses `theme_expr(..., 1.0)`.

Tools: `adv_geom.py` (loft / spike / solidify / Cyl / Radial, `write_obj_smooth` with shared normals and no degenerate faces), `adv_panels.py` (raised plates draped on a head / limb surface, ribbons, bolts, `WarpSurf`),
`adv_parts.py` (part builders + the validator), `donor_tools.py` (skins another playermodel into the Ethics Assistant's frame the way BoneMerge does), `ax_render.py` (previews through the ax3d engine,
optional), `verify_adv.py` (outfit / OBJ checks), `steam_details.py` (Workshop file details + thumbnails), `wait_assets_live_adv.py`, `pacview.py` (renders an outfit FILE the way pac places it: friendly bone names through `pac.BoneNameReplacements`, base_movable world matrices, proxies, entity2 `Materials`,
bone-merged donors with `$color2` tints and clip planes, OBJs fetched from the live host or `PV_LOCAL=1` from `stage_adv`; checks the files rather than the generator). Run a builder, then `python verify_adv.py`; publish like the BNA outfits
(copy `stage_adv/obj/adv/*` to `obj/adv/`, `stage_adv/outfits/*.txt` to `outfits/adv/`, push, `python wait_assets_live_adv.py`, then copy the txt into `garrysmod/data/pac3`).
