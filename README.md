# gemini-pixel-sprite-gen

A Claude Code skill for producing **chunky low-res pixel-art game sprites**
with consistent style across an entire roster — characters, monsters, and
boss variants — using Google Gemini for generation and a deterministic
post-process for snap+normalize.

Output is engine-agnostic: chunky-pixel `<char>_<action>.png` files with binary alpha — drop into any 2D engine (Godot, Unity, Pico-8, raylib, web canvas, etc.).

---

## Requirements

- Python 3.10+
- Google Gemini subscription (logged in to gemini.google.com in Chrome or Firefox)
- Claude Code

---

## Installation

```bash
/plugin marketplace add nakzyu/gemini-pixel-sprite-gen
/plugin install gemini-pixel-sprite-gen@gemini-pixel-sprite-gen
```

Local dev:

```bash
git clone https://github.com/nakzyu/gemini-pixel-sprite-gen.git
claude --plugin-dir ./gemini-pixel-sprite-gen
```

Dependencies are auto-installed on first run.

---

## First-run setup

The skill walks you through:

1. **Output dir** — where sprites are saved (default `./sprites`).
2. **Canonical style anchor** — a single reference image that locks the art
   style for the entire project (chunky pixel size, palette feel, body
   proportions). Every new character/monster's first frame uses this as the
   anchor. **Mandatory** — without it, generation drifts.
3. **`sprite_spec.yaml`** — project-level config defining `target_h` and
   `cell_h` for characters and monsters. Defaults: chars 32/48, monsters
   64/72. Created if missing.

You can stop here if you only need single-shot generation. The chunky
pixel-art pipeline below kicks in when you ask for game characters / sprite
rosters / multiple poses.

---

## The pipeline

For game-ready sprites with multiple poses per creature, the skill follows a
locked-in two-step pipeline: **generate → snap**.

### Step 1 — Generate (Gemini)

```
/gemini-pixel-sprite-gen recruit, female warrior, simple sword and tunic, idle pose
```

The skill picks the right anchor reference automatically:

| Frame                              | Anchor (`--files`)                          |
|------------------------------------|---------------------------------------------|
| First frame of a NEW character     | Canonical style anchor                      |
| Subsequent frames of same char     | That character's approved IDLE              |
| First frame of a NEW monster       | Canonical style anchor                      |
| Subsequent frames of same monster  | That monster's approved IDLE                |
| Family-of-monster (e.g. giant_slime from slime) | Canonical + parent monster's IDLE |

**Hard gate:** new subjects without an anchor → the skill stops and asks
you. No anchor-less generation.

Prompts emphasize what *differs* from the reference (pose, outfit, color),
not the style itself — the reference image carries the style. This keeps
the chunky pixel grid consistent across the roster.

### Step 2 — Snap (post-process)

```bash
python3 scripts/snap_single.py <gemini_output> <name> <action> \
  --out-dir <project>/sprites/sheets \
  --target-h 32 --cell-h 48        # characters
  # OR --target-h 64 --cell-h 72   # monsters
```

The snap pipeline:

1. Tight bbox of the figure (alpha > 10).
2. Optional `--top-crop N` to drop overlong hair/halo so the face survives at small native resolution.
3. **Mode-downsample** — each dest pixel = majority opaque color of its source block.
4. Largest connected component cleanup.
5. **Outline pass** — alpha-edge dest pixels recolored with the darkest opaque color in their source block, recovering outlines that mode-color picks would dilute.
6. Bottom-center align (feet at `cell_h - PAD`, x-centered).

Output: `<char>_<action>.png` only. No upscaled `_display.png`, no `_1x1` suffix.

---

## Style conventions (built into the skill)

- **Characters** = clean Octopath chibi feel. Modest detail, friendly readable proportions, minimalist face (eyes only — no mouth, no nose).
- **Monsters** = grotesque / vile. Irregular asymmetric forms, dripping ooze, visible innards, multiple uneven eyes, drooling fanged mouths, dark sickly palettes.
- **Backgrounds** = ordinary scenes (grassland, forest, cave) with darkened palettes.
- **Combat orientation** = side-view, left↔right. **Every attack pose extends horizontally** toward the opponent — never downward, never toward the camera.

These conventions are encoded in the skill's prompt templates so the user
doesn't have to repeat them.

---

## File layout

```
<project>/
├── sprite_spec.yaml          # project config
├── sprites/
│   ├── references/
│   │   └── <canonical>.png   # the style anchor
│   ├── character/            # raw Gemini outputs (with chromakey)
│   └── sheets/               # snapped game files
│       ├── recruit_idle.png
│       ├── recruit_attack.png
│       ├── slime_idle.png
│       └── ...
└── skills/
    └── gemini-pixel-sprite-gen/    # the skill (if installed locally)
        ├── SKILL.md
        ├── PIXEL_ART_PIPELINE.md
        └── scripts/
```

Filename invariant: `<creature>_<action>.png`. No prefixes, no suffixes.

---

## Engine import notes

- Set the engine's texture filter to **NEAREST** (no bilinear / no smoothing). Otherwise pixel art blurs.
- Each `<creature>_<action>.png` is one frame. Wire them into your engine's animation system per creature.
- Feet are at row `cell_h - PAD` from the texture top, x-centered. Set the sprite origin / offset so node position equals feet position (in Godot 4: `offset = (0, -PAD)`; in Unity: pivot bottom-center; in Pico-8: just blit at `(x, y - cell_h)`).
- Cell sizes can differ across creatures (chars 48 tall, monsters 72 tall by default). Group same-tier creatures into one atlas if your engine wants uniform cell.

---

## When things go wrong

- **Output drifted in style** → regenerate in a fresh session (`end-session` then start new). Session context can decay.
- **Eyes/face details lost at small resolution** → snap with `--top-crop 40-100` to drop hair/halo; the face gets more dest pixels.
- **Bent pose looks too detailed compared to idle** → snap the bent pose at lower target (e.g. `--target-h 28-30`) — bent figure has shorter source tight_h, h32 ends up finer.
- **Outfit color changed in non-idle frame** → the prompt didn't preserve colors strongly enough. Add explicit color list ("OUTFIT COLORS must match image 1 EXACTLY: [list]").
- **Attack aiming wrong direction** → the prompt forgot the horizontal-attack rule. Re-emphasize "side-view battle, attack extending RIGHT (or LEFT) horizontally."

---

## Other commands

```
/gemini-pixel-sprite-gen list                    # show all generated sprites
/gemini-pixel-sprite-gen list --category monster
/gemini-pixel-sprite-gen delete <name>
/gemini-pixel-sprite-gen organize                # remove orphaned manifest entries
/gemini-pixel-sprite-gen sessions                # list active sessions
/gemini-pixel-sprite-gen end-session <name>      # close a session
```

For one-off non-game-asset generation (single illustration, item icon, UI
element), the chunky pipeline doesn't activate — the skill just generates
and saves the image.

---

## How transparency works

Gemini cannot output PNG alpha channels — it draws checkerboard patterns
instead. This skill works around that:

1. Appends chromakey green (`#00FF00`) background instruction to every prompt
2. HSV-based color detection identifies and removes the green
3. Edge pixels are despilled to remove green color bleed
4. Result: clean PNG with binary (0 or 255) alpha — pixel-art friendly

---

## License

MIT
