# Pin badge generator: build contract

Goal: a wearable PAC3 pin badge (round button badge) for ax0rz0's GMod SCP-RP server
(OLD pac3 build) whose face shows ANY image.

Two ways to show the image:

1. **URL texture (main path).** The face is a UV-mapped dome mesh. Its pac `Material` is set to an
   image URL (GitHub raw or `https://files.catbox.moe/....png`). The user swaps images by pasting a new URL.
2. **Geometry mosaic (fallback).** If a server blocks URL images, the tool converts the image into
   per-colour mesh layers (one OBJ + one model2 part per colour) so no texture is needed.

Everything lives in `tools/pin_badge/` of the repo `C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s`
(raw URL base `https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/`). Python 3.13 with Pillow 12
and numpy 2.3 are installed (`python` / `py`). No other dependencies. Windows paths.
Read `pin_common.py` first: use its constants and helpers, do not duplicate them.

## Frame (non-negotiable)

pac's urlobj loader reads OBJ `v x y z` verbatim (no axis swap), reads `vt u v` and stores `1 - v`
(standard OBJ convention, v = 1 is the image TOP), ignores normals unless present, and REVERSES face
winding (so standard CCW-front OBJ faces render front-facing in Source).

Badge local frame = OBJ coordinates:
- `+Y` = face normal (out of the chest; the badge parent sits on bone `spine 2` whose frame is X up, Y forward, Z player-left)
- `+X` = image up
- `+Z` = image right **as seen by a viewer standing in front of the wearer**
- Front faces: CCW in 2D `(z, x)` coordinates (z horizontal, x vertical). Check: (0,0,0) → (0,0,1) → (1,0,0) has normal +Y.
- Image pixel (row r from top, col c from left) of an N×N grid over the face disc of radius R:
  `x = R - (r + 0.5) * 2R/N`, `z = -R + (c + 0.5) * 2R/N`.
- UVs for the texture face: `u = (z / R + 1) / 2`, `v = (x / R + 1) / 2` (v = 1 at the top). A square image maps
  to the square around the disc; only the inscribed circle shows.

## Geometry (units ≈ inches, defaults in pin_common.py)

Diameter D (default 2.25), body radius R = D/2. The image face uses the same R.
- **body**: closed cylinder radius R, y ∈ [0, BODY_THICKNESS]; side wall + back cap (+ front cap optional,
  hidden under the dome). CIRCLE_SEGMENTS around. Colour: the image's edge colour (looks like the print
  wraps round the edge); white when unknown.
- **face_uv**: dome surface over the disc, y = `dome_y(x, z, R) + TEXTURE_LIFT`, with vt per vertex.
  Use a polar or lattice tessellation fine enough to look round (≥ 128 rim segments, ≥ 12 rings).
- **mosaic layers** (fallback): for each palette colour, all cells of that colour, each cell clipped to the
  circle polygon with `clip_convex` (boundary cells become smooth arcs, no jaggies), vertices on the dome
  `dome_y`, welded per file with `MeshBuilder`. Neighbouring cells share identical corner coordinates so
  layers never crack. Lift LAYER_LIFT (0).
- **gloss**: translucent white crescent highlight on the upper-left (viewer's view) of the dome, lifted
  GLOSS_LIFT above the dome, alpha GLOSS_ALPHA.
- **back**: metal back plate disc (radius 0.9R, y ∈ [-0.04, 0]) + horizontal pin needle along Z behind it
  + small clasp barrel at one end. One mesh, METAL_COLOR.
- **rim** (hidden by default): thin raised metal ring around the edge for a framed look.
- Keep every OBJ under MAX_LAYER_TRIS triangles. Plain `v` / `vt` / `f` lines only, 1-based, no negatives,
  triangles only. Written with `write_obj`.

## Files and naming

- Static base set (shared by `pin_badge.txt`): `obj/pins/base/pin_base_<key>.obj`, keys `body`, `face_uv`,
  `gloss`, `back`, `rim`.
- Per-badge set from the tool: `obj/pins/<slug>/pin_<slug>_<hash6>_<key>.obj` (`obj_filename`), keys as above
  plus `c01`, `c02`, ... for mosaic colours. hash6 = first 6 hex of sha1 over the image bytes + parameters, so a
  changed badge gets new URLs (pac caches by URL). Unique per-badge files also avoid pac's duplicate-URL
  "Download aborted" when two badges are worn. The tool deletes stale `pin_<slug>_*.obj` in that folder only.
- Example images: `img/pins/<name>.png` (raw URL = RAW_BASE + that path).
- Outfits: `PAC_DIR/pin_badge.txt` (the reusable URL one) and `PAC_DIR/pin_<slug>.txt` per generated badge.
- Previews/manifests/test images: `tools/pin_badge/out/`.

## Manifest (JSON, written per badge to out/<slug>.json, consumed by pin_pac and pin_render)

```json
{
  "name": "isd badge", "slug": "isd_badge", "hash": "a1b2c3", "diameter": 2.25,
  "image_url": "https://... or null", "source_image": "local path or url or null",
  "res": 64, "colors": 16,
  "parts": [
    {"key": "body", "role": "body", "label": "pin badge (MOVE ME)", "file": "pin_...obj",
     "local_path": "C:\\...", "url": "https://...", "color": [1, 1, 1], "alpha": 1.0,
     "translucent": false, "hidden": false, "material": null, "verts": 0, "tris": 0},
    {"key": "face_uv", "role": "texture", "label": "image (paste URL into material)", "material": "https://...png", ...},
    {"key": "c01", "role": "image", "label": "mosaic #1a2b3c", "pixels": 812, ...},
    {"key": "gloss", "role": "gloss", "translucent": true, "alpha": 0.22, ...},
    {"key": "back", "role": "back", ...},
    {"key": "rim", "role": "rim", "hidden": true, ...}
  ]
}
```
Exactly one part has role `body`; it becomes the parent. Mosaic layers are hidden when a texture URL is the
active face, and the texture face is hidden when the mosaic is active (mode decided by the tool).

## PAC outfit rules (old server build, all field-verified)

- Line 1 exactly `-- claude skill made by ax0rz0`, then a blank line. UTF-8 WITHOUT BOM, `\n` newlines,
  tab indentation, trailing newline, no comment at the end of the file.
- Canonical form with no outer braces: `["self"] = {...},` then `["children"] = {...},`.
- Root: `group`, `Name` = `pin badge: <name>`, `Notes` = `claude skill made by ax0rz0`, `EditorExpand` = true.
- Parent part = body: `model2`, `Bone` = DEFAULT_BONE, `Position`/`Angles` = defaults, `EditorExpand` = true.
- Every other part is a child of the body with no `Bone` and no transform (all coordinates are baked).
- Every `model2`: `ClassName`, `Name`, `Model` (raw https URL ending exactly in `.obj`, no query string),
  `ForceObjUrl` = true, `Material` (`models/debug/debugwhite`, or the image URL for the texture face),
  `NoLighting` = true, `Color` = `Vector(r, g, b)` 0..1, `UniqueID` = `uid(slug, key)`.
  Image/texture/gloss layers also `NoCulling` = true. Hidden parts `Hide` = true. Gloss `Translucent` = true,
  `Alpha` = 0.22. Texture face `Color` = `Vector(1, 1, 1)`.
- Keys alphabetised inside each `self`. Only literals, `Vector(...)`, `Angle(...)`. No duplicate UniqueIDs,
  no two parts with the same Model URL.

## Verification every module must support

- Front render (camera at +Y looking toward −Y, screen right = +Z, screen up = +X) of a badge must reproduce
  the source image unmirrored and upright: sampling the render at cell centres must match the quantised image
  better than its left-right mirror, up-down mirror and 180° rotation.
- Vertex/triangle counts reported; no degenerate triangles; layers partition the disc (total covered area ≈ πR²).
