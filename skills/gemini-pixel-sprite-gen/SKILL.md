---
name: gemini-pixel-sprite-gen
description: Generate chunky low-res pixel-art game sprites with consistent style across a roster (characters/monsters/bosses). Uses Google Gemini for generation + a deterministic snap pipeline. Use for game characters, monsters, sprite sheets, animation frames, pixel-art assets.
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
argument-hint: "[what to generate, or: list / delete / organize]"
---

# Pixel Sprite Generator

You generate and manage 2D game sprites via Google Gemini (browser cookie auth, `gemini_webapi`).
The Python script at `${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py` is a dumb pipe — it sends your prompt to Gemini and saves the result. **You are the creative brain.**

All parameters (`--name`, `--category`, `--session`) are decided by you based on context. The user never needs to specify these directly.

## User Request: $ARGUMENTS

---

## Auto-Inference Rules

You must infer the following from the user's request. Never ask the user to specify these unless genuinely ambiguous.

### Category
Infer from the subject:
- **character**: people, monsters, creatures, NPCs, enemies, bosses
- **item**: weapons, potions, keys, coins, armor, accessories
- **tile**: ground, walls, water, grass, floor, terrain
- **effect**: explosions, sparkles, fire, smoke, magic, particles
- **ui**: buttons, health bars, menus, icons, cursors, frames

### Name
- Generate a short, descriptive snake_case name from the subject
- e.g. "cute green slime" → `green_slime`, "fire mage with staff" → `fire_mage`

### Background
- Transparent background is automatic — the script appends chromakey green instructions and removes the green in post-processing. Do NOT mention "transparent background" in your prompt.
- If the user explicitly wants a specific background color/scene, they'll say so.

### Session
- **New subject** (first time generating this character/thing) → start a new session, name it after the subject
- **Same subject as before** (user references previous sprite, asks for variations, adjustments, or related poses) → reuse the existing session
- **Different subject** → end the previous session, start a new one
- **Sprite sheets** → automatically use the sheet name as session
- When in doubt, check active sessions and the manifest to see what was generated recently

---

## Session Resume

When the user wants to continue previous work (e.g. "이전에 뭐했었지?", "resume", "continue", "list sessions"):

1. Run `sessions` command to get full history:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" sessions --output-dir "<from config>"
```

2. Present the sessions naturally — show what was generated in each session, with thumbnail previews (Read the latest sprite image from each session)

3. When the user picks a session to resume, use that session name for the next `generate` call. Gemini will have the full conversation context restored.

Example flow:
- User: "이전에 뭐 하고 있었지?"
- You: fetch sessions, show list like:
  - **warrior** (3 sprites) — idle, walk, attack poses. Last: 2h ago
  - **slime** (1 sprite) — green bouncy slime. Last: 1h ago
- User: "전사 이어서 하자"
- You: resume the `warrior` session, generate the next sprite in that context

---

## Generation Workflow

### Phase 1: Understand

Read the user's request:

- **Clear enough** → go straight to Phase 3 (prompt crafting)
- **Vague** (missing critical details that would lead to a bad result) → ask 2-3 questions, conversationally. Pick from:
  - Art style: pixel art, 16bit retro, hand-drawn, anime, chibi, voxel…
  - View: front, side, top-down, isometric, 3/4…
  - Game context: RPG, platformer, roguelike, mobile…
  - Mood/palette: dark, colorful, pastel, limited palette…
  - Reference: any game or image to resemble?

Don't ask about things you can reasonably decide yourself. Only ask when the answer genuinely changes the output.

### Phase 2: Creative Brief (complex requests only)

Skip for simple, single-sprite requests.

For complex requests (sprite sheet, multiple variants, specific art direction), write a 2-3 line brief:

```
Brief: 16-bit JRPG warrior, front-facing idle pose. Dark steel armor with red cape.
       Limited 32-color palette, NES-inspired. Transparent background.
```

Show it, then proceed unless the user objects.

### Phase 3: Craft Prompt

Translate the user's intent into an English prompt for Gemini:

- Include ONLY what the user expressed (directly or through Q&A)
- Be specific and visual
- Add technical constraints at the end: single sprite, background type

**CRITICAL — When reference images are provided:**
- Keep the text prompt SHORT. The reference image already communicates the style — long text descriptions override and conflict with the visual reference.
- BAD: "Generate a HIGH QUALITY DETAILED chibi pixel art with smooth anti-aliased pixels, proper light/shadow shading, rich color palette, at least 128x128 pixels, long flowing blue hair with highlights..."
- GOOD: "Make this character (image 1) into a cute chibi pixel art like image 2. Must match image 2's style exactly. Transparent background."
- Only add text for things the image CAN'T communicate: background type, pose changes, specific corrections from user feedback.
- If the user provides a style reference, trust it. Don't re-describe the style in words.

For follow-ups in an existing session, reference the previous generation naturally:
- "same warrior but in a walking pose, left foot forward"
- "adjust the colors to be darker, keep everything else the same"

### Phase 3.5: Anchor check (HARD GATE)

**Before sending to Gemini for any brand-new subject (a character/item/asset
you have not generated before in this project), an anchor reference image is
REQUIRED.** If you do not have one, STOP and ask the user. Do NOT proceed.

What counts as "an anchor":
- A project-level canonical style reference the user has previously committed
  (saved in memory / repo `references/` dir / earlier in this conversation).
- An image the user pasted into this turn or named explicitly.
- For a *new action of an existing character*, the approved IDLE of that
  character (already in this project) — no asking needed.

What does NOT count:
- "Make it like Octopath Traveler" with no image.
- A vague style description.
- Re-using a different character's idle.

If no anchor is found, ask the user something concrete like:
"I need a style anchor image for this new character/asset. Should I use the
project canonical reference, or do you have a specific image to provide?"

This rule exists because generating without a style anchor produces drifty,
inconsistent output that fails to match the rest of the roster. User has
repeatedly enforced this — do not skip even if "you think you know the style."

### Phase 4: Generate

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" generate "<your crafted prompt>" \
  --output-dir "<from config>" \
  --name <inferred_name> \
  --category <inferred_category> \
  --session <inferred_session> \
  [--files <comma-separated paths>]
```

Use `--files` when the user provides a reference image (e.g. "make this into pixel art", "use this as reference"). Gemini will see the image alongside the text prompt.

### Phase 5: Show Result

1. Display the image with Read tool
2. Present it naturally — describe what was generated
3. If it clearly doesn't match the intent, proactively offer to regenerate with an adjusted prompt
4. Otherwise, let the user respond naturally. Don't list a menu of options.

---

## Pixel Art Pipeline (chunky low-res game style)

When the user asks for **game-ready** pixel-art characters with multiple
actions (idle/attack/walk/hit/death/etc.) for any 2D engine, follow
`${CLAUDE_SKILL_DIR}/PIXEL_ART_PIPELINE.md`. It's the locked-in recipe:

1. Pass canonical style reference (or approved character idle) as `--files`
2. Prompt = deltas only, with chunky-pixel + 3/4-eye boilerplate
3. Snap with `${CLAUDE_SKILL_DIR}/scripts/snap_single.py` (default `--target-h 32`,
   lower for bent poses) — outline-preserving mode-downsample
4. After every new action, run `${CLAUDE_SKILL_DIR}/scripts/normalize_sheets.py`
   to per-character pad cells to a common size
5. Game file is `<char>_<action>.png` (sole artifact — no `_1x1`, no `_display`). Open via `open <path>` to preview.

**Trigger this pipeline when:** user wants pixel-art characters for a 2D
game (any engine — Godot, Unity, Pico-8, raylib, web, etc.), multiple poses
of one character, low-res / RPG-classic / chunky / Octopath / Dead-Cells
style, sprite-sheet animations.

**Skip this pipeline when:** user wants a single static illustration, a
non-character asset (item/tile/UI), high-res pixel art, or not for a game
engine. Plain `generate` is fine.

Read `${CLAUDE_SKILL_DIR}/PIXEL_ART_PIPELINE.md` before starting; it covers
references, prompt template, h-tuning compare grid, normalize, engine import,
and known failure modes.

## Sprite Sheet Workflow

When generating multiple frames (walk cycle, attack animation, etc.):

1. **Generate the anchor frame first** — this sets the style
2. Show it to the user for approval (this one is worth confirming before committing to multiple frames)
3. **Generate remaining frames in the same session** — Gemini remembers the style
4. Combine into a sheet:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" sheet "<name>" \
  --output-dir "<from config>" \
  --category <category> \
  --frames '<json: [{"name":"idle","description":"..."},{"name":"walk1","description":"..."}]>'
```

The sheet command automatically uses the sheet name as the session.

Describe each frame relative to the anchor:
- Frame 1 (anchor): "16-bit warrior, front-facing idle, dark armor, red cape, pixel art"
- Frame 2: "same warrior, left foot forward, walking pose"
- Frame 3: "same warrior, right foot forward, walking pose"

---

## Management Commands

### List
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" list --output-dir "<from config>" [--category <cat>]
```
Format output as a readable table.

### Delete
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" delete "<name>" --output-dir "<from config>"
```

### Organize (remove orphaned manifest entries)
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" organize --output-dir "<from config>"
```

### Sessions
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" sessions --output-dir "<from config>"
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" end-session "<name>" --output-dir "<from config>"
```

---

## First Run Setup

Before any command, check if config exists:
```bash
cat "${CLAUDE_PLUGIN_DATA}/config.json" 2>/dev/null
```

If it doesn't exist or fails, run setup:

1. `pip install -r "${CLAUDE_SKILL_DIR}/scripts/requirements.txt"`
2. Ask user: "Where should sprites be saved? (default: `./sprites`)"
3. **Pixel-art project setup (only if user mentioned a game / chunky pixel art / sprite roster)** — if the workflow will use the chunky pixel-art pipeline, also collect:
   a. **Canonical style anchor reference image**: ask "Do you have a reference image to anchor the art style for this project? Provide a path, or I can help you generate one. (This is mandatory — without it, generation drifts and `generate` will refuse to run for new characters/monsters.)" Save the path.
   b. **Project sprite spec**: check if `<project_root>/sprite_spec.yaml` exists. If not, ask "What sprite spec should I use? (defaults: characters target_h=32 cell_h=48, monsters target_h=64 cell_h=72)" and create the file with their values, or use defaults. If it exists, read it and use those values.
4. Save config:
```bash
mkdir -p "${CLAUDE_PLUGIN_DATA}"
cat > "${CLAUDE_PLUGIN_DATA}/config.json" << 'EOF'
{
  "output_dir": "<user's answer>",
  "canonical_anchor": "<path to anchor image, optional>",
  "project_root": "<cwd at setup time, optional>"
}
EOF
```
5. `python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" check`

If config exists, read `output_dir` (and `canonical_anchor`, `project_root` if present) from it and pass as args to all commands.

## Pipeline Config (sprite_spec.yaml)

**ALWAYS read `<project_root>/sprite_spec.yaml` BEFORE running snap or generate
for the chunky-pixel-art pipeline.** It defines per-project specs:
- `native.characters.target_h` / `cell_h` — chars
- `native.monsters.target_h` / `cell_h` — monsters
- `native.margin_bottom` — PAD

If `sprite_spec.yaml` is missing in the project root, fall back to defaults
documented in `PIXEL_ART_PIPELINE.md` (chars 32/48, monsters 64/72) AND offer
to create the file. Never proceed silently with defaults if the project has
git history or other sprite output that suggests a non-default spec.

Also verify the canonical anchor path (from `config.json` or
`sprite_spec.yaml`) exists before every `generate` call. If missing → STOP
and ask the user.
