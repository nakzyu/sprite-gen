# Chunky low-res pixel art pipeline

The locked-in recipe for game-ready sprites: **generate → snap**.
Output: `<char>_<action>.png` (and only that — no `_1x1`, no `_display`).
Engine-agnostic — drop into any 2D engine (Godot, Unity, Pico-8, raylib, web canvas, etc.) with NEAREST texture filter.

Use this pipeline whenever the user wants:
- Chunky low-res pixel art (RPG-classic, Octopath/Dead-Cells scale)
- Multiple actions (idle / attack / walk / hit / death / victory) of the same
  character to swap cleanly in an animation
- Engine-agnostic sheets ready for any 2D pipeline (Godot/Unity/Pico-8/etc.)

## Step 0 — Read project config (ALWAYS)

Before any snap/generate, **check for `<project_root>/sprite_spec.yaml`**:

```bash
cat ./sprite_spec.yaml 2>/dev/null
```

If present → use its values for `target_h`, `cell_h`, `canonical_anchor`,
etc. They override the defaults below.

If absent → use defaults (chars 32/48, monsters 64/72) AND offer to create
the file so the project has an explicit spec going forward.

The canonical anchor referenced in `sprite_spec.yaml` (or in `config.json`)
must exist on disk before any `generate` call — verify, and STOP+ask if
missing.

## Output spec (defaults — overridable via sprite_spec.yaml)

- **Characters**: native char height = 32 px, cell height = 48, cell width
  16-multiple auto-grown to fit feet_extent×2 + PAD×2.
- **Monsters**: native char height = 64 px, cell height = 72, cell width
  same auto-grow rule. Bigger than chars on screen at same render scale →
  natural visual threat hierarchy without runtime scaling.
- **Alignment**: feet bottom-aligned (PAD=4 from cell bottom), feet x-centered.
- **Alpha**: binary (0 or 255), no AA.
- **Filename**: `<char>_<action>.png` only. The script does NOT produce a
  display/preview PNG — preview by `open <path>` in Preview.app (auto-zoom).

## Style + aesthetic split

- **Characters** = clean Octopath chibi feel (modest detail, friendly readable
  proportions, minimalist face = eyes only).
- **Monsters** = grotesque/vile (irregular asymmetric forms, dripping ooze,
  visible innards, multiple uneven eyes, drooling fanged mouths, scars,
  dark sickly palettes — see `feedback_monster_aesthetic.md`).
- **Backgrounds** = ordinary scenes (grassland, forest) but with darkened
  palette overall.

## Combat orientation: HORIZONTAL ATTACKS

Game is left↔right side-view battle. **Every attack pose extends
horizontally toward the opponent (right or left side of the canvas), NOT
downward, NOT toward the viewer.** Weapons / lunges / strikes / projectiles
travel along the X axis. See `feedback_horizontal_attacks.md`.

## Step 1 — Generate (Gemini)

Call `sprite_gen.py generate` per frame.

**References (--files), in this order:**

| Frame                          | --files                                          |
|--------------------------------|--------------------------------------------------|
| First frame of a NEW character | Canonical style ref (e.g. `female_ref_3x.png`)   |
| Subsequent frames same char    | Approved IDLE of THAT character (only)           |
| First frame of a NEW monster   | Canonical style ref (chunkiness anchor)          |
| Subsequent frames same monster | Approved IDLE of THAT monster (only)             |
| Family-of-monster (e.g. giant_slime from slime) | Canonical + the related monster's idle (2 refs) |

The canonical style ref is the single chunky-style anchor the user committed
at the start. For non-idle frames of an existing creature, pass ONLY that
creature's approved idle — adding canonical too causes Gemini to drift away
from locked-in creature details (outfit, color, anatomy).

**HARD GATE — never call `sprite_gen.py generate` for a brand-new subject
without an anchor in `--files`.** If the project has no canonical reference
yet, STOP and ask the user. Anchor-less output drifts heavily.

**Prompt structure (deltas only, style comes from references):**

For a CHARACTER first frame:
```
Match image 1 EXACTLY — same chunky thick pixel blocks, same proportions,
same minimalist face style (eyes only, no nose, no mouth).
Female [class]. [outfit colors + items short list].
Idle pose, [stance hint]. Facing same direction as image 1.
3/4 front view: NEAR eye full, FAR eye half. (Don't pixel-spec eye layout.)
Exactly 2 arms, exactly N weapon(s).
```

For a CHARACTER non-idle frame:
```
Match image 1 EXACTLY (locked character) — same chunky pixels, same
proportions, same outfit (preserve all colors), same hair, same face style.
Pose change ONLY: [pose description, side-view battle, attack to the RIGHT].
Same chunky pixels. Exactly 2 arms, exactly 1 weapon.
```

For a MONSTER first frame:
```
Match the CHUNKY THICK PIXEL ART STYLE of image 1 — same large pixel blocks.
NOT a humanoid character — the SUBJECT is a [monster type].
[Anatomy spec — clear silhouette readable at small size].
Grotesque details: [matted/rotting/dripping/multi-eyed/fanged/etc.].
Idle pose, menacing stance.
```

For a MONSTER non-idle frame: same as character non-idle pattern.

Do NOT add style adjectives ("mature/gritty/clean") when a reference is
attached — they fight the visual reference.

Do NOT pixel-spec eye layouts (e.g. "NEAR eye 2 cols × 3 rows"). Stay coarse;
Gemini interprets pixel grid specs garbled. Trust the reference image.

If output drifts (face broken, outfit color wrong, etc.):
- Iterate in a FRESH session (`end-session` then new session). Sometimes
  session context decay is the issue, not the prompt.
- Emphasize the specific thing that broke ("OUTFIT COLORS must match image 1
  EXACTLY: [list colors]") in plain words — not pixel grids.

## Step 2 — Snap

```
python3 scripts/snap_single.py <src.png> <char> <action> \
  --out-dir <sprites_dir>/sheets \
  [--target-h 32] [--cell-h 48] [--top-crop N]
```

- **Characters**: `--target-h 32 --cell-h 48` (default).
- **Monsters**: `--target-h 64 --cell-h 72`.
- For BENT poses (forward-stab attack, dive) where source character is
  shorter, h32 makes pixels too fine — try `--target-h 28-30` for chars,
  eyeball compare.
- `--top-crop N` trims N rows off the source's tight-bbox top before
  snapping. Use when overlong hair/halo/aura pushes face down so eyes/face
  details get averaged out at h32. Try 40-100 px first; verify face not cut.

**Variation compare (when result looks off):** use the bundled
`scripts/snap_compare.py` to sweep h or top_crop and let the user pick:

```
# h sweep at fixed top_crop=0:
python3 scripts/snap_compare.py <src.png> --target-h-range 24 38 2

# top_crop sweep at fixed h32:
python3 scripts/snap_compare.py <src.png> --top-crop-range 0 200 20

# 2D grid: h × top_crop:
python3 scripts/snap_compare.py <src.png> \
  --target-h-range 28 36 2 --top-crop-range 0 100 20

# Monsters (bigger cell):
python3 scripts/snap_compare.py <src.png> --cell-h 72 \
  --target-h-range 56 70 2
```

Outputs a labeled grid PNG (default `/tmp/<src_stem>_compare.png`); `open`
it, the user picks the best (h, top_crop), then run `snap_single.py` with
those values for the final game file.

The pipeline inside snap_single.py:
1. Tight bbox of source figure (alpha > 10).
2. (Optional) trim top-crop rows.
3. Mode-downsample: each dest pixel = majority opaque color in its source
   block (opaque threshold alpha > 200, dest opaque if > 40% of block opaque).
4. Largest connected component cleanup (drops tiny isolated specks).
5. Outline pass: opaque dest pixels touching transparent are recolored
   with the darkest opaque color in their source block — preserves outlines
   that mode-color picks would dilute.
6. Bottom-center align with feet x-centering, cell_w = round_up_16(...),
   cell_h = `--cell-h`.

## Step 3 — Normalize (DEFAULT: skip)

**Default policy:** do NOT auto-run `normalize_sheets.py`. Each frame stays
at its native cell size from the snap.

- All character idle frames natively snap to **32×48** → uniform idle row
  across the roster.
- All monster idle frames natively snap to ~variable × **72** at h64 → also
  uniform within the monster tier.
- Attacks may be wider per creature (recruit attack with sword 80×48,
  giant_slime body-charge 96×72 etc.) — that's fine, no padding needed.

Run normalize only when the user explicitly asks for uniform cells:

| Mode                           | Command                                          |
|--------------------------------|--------------------------------------------------|
| Per-character max              | `normalize_sheets.py --sheets-dir DIR`           |
| Global max across roster       | `normalize_sheets.py --sheets-dir DIR --global`  |
| Forced exact cell (clip OK)    | `normalize_sheets.py --sheets-dir DIR --cell W H`|

## Step 4 — Show user

```
osascript -e 'tell application "Preview" to quit'
sleep 0.4
open -a Preview <sheets_dir>/<char>_idle.png <sheets_dir>/<char>_attack.png
```

Quit + reopen ensures both files load into ONE Preview window with a sidebar,
not separate windows. (Preview.app's automatic zoom-to-fit handles small
native PNGs — no need for upscaled `_display.png`.)

If the user says the snap is broken / weird:
1. Most common cause: wrong target_h. Run a compare grid (h26-h44 step 2).
2. Second cause: face details lost at h32 due to overlong hair → try
   `--top-crop 40-100`.
3. Third cause: source itself is bad → regenerate the source.

## Step 5 — Engine import

Engine-agnostic. The output PNGs work in any 2D pipeline; just respect:

- **NEAREST filter only** — never bilinear / smoothing. Otherwise pixel art blurs.
- **Feet anchor** — feet are at `(cell_w / 2, cell_h - PAD)` from texture top-left. Set the sprite origin / offset so the entity's logical position equals the feet position. (Godot 4: `AnimatedSprite2D.offset = (0, -PAD)`. Unity: pivot bottom-center. Pico-8: `spr` blits at top-left, so adjust by `cell_h`.)
- **Multi-frame actions** later follow `<char>_<action>_<N>x1.png` — N frames horizontally, hframes=N for engines that auto-split.
- **Different cell sizes per creature** are expected (chars 48 tall, monsters 72 tall by default). Group same-tier creatures into one atlas if your engine prefers uniform cells.

## What NOT to do

- Don't pixel-spec eye layouts in prompts — backfires.
- Don't add style adjectives when a reference is attached.
- Don't generate without a reference image — no style anchor, output drifts.
- Don't auto-derive target_h from a reference idle (tried; tiny output for
  bent poses).
- Don't combine multiple actions into one strip per character — each action
  stays in its own file.
- Don't snap chars at target_h ≥ 64 (too detailed, not chunky).
- Don't use LANCZOS or direct NEAREST resize — uneven pixels.
- Don't auto-run normalize_sheets.py — breaks idle uniformity across roster.
- Don't ship `_display.png` — we no longer create it; if you find one,
  delete it.
- Don't use 1.5× runtime scaling for monsters — non-integer pixel scaling
  produces uneven pixel chunks. Render natively bigger instead (h64).
- Don't aim attack poses downward or toward viewer — game is L↔R side-view,
  attacks must extend horizontally.
