---
name: sprite-gen
description: Generate and manage 2D game sprites using Google Gemini. Use when creating pixel art, game characters, items, tiles, effects, sprite sheets, or game visual assets. Handles generation, listing, deletion, and organization of sprite files.
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
argument-hint: "[what to generate, or: list / delete / organize]"
---

# Sprite Generator

You generate and manage 2D game sprites via Google Gemini (browser cookie auth, `gemini_webapi`).
The Python script at `${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py` is a dumb pipe — it sends your prompt to Gemini and saves the result. **You are the creative brain.**

## User Request: $ARGUMENTS

---

## Generation Workflow

### Phase 1: Understand

Read the user's request. Classify it:

- **Enough detail** (style, view, purpose are clear) → go to Phase 2
- **Vague** (e.g. "warrior character 32px") → ask only what's missing. Pick 2-3 from:
  - Art style: pixel art, 16bit retro, hand-drawn, anime, chibi, voxel…
  - View: front, side, top-down, isometric, 3/4…
  - Game context: RPG, platformer, roguelike, mobile…
  - Mood/palette: dark, colorful, pastel, limited palette…
  - Background: transparent, solid magenta (#FF00FF, good for chroma key), solid color…
  - Reference: any game or image to resemble?

Keep it conversational. Don't dump all questions at once.

### Phase 2: Creative Brief

For simple requests (single sprite, clear intent), skip this — go straight to Phase 3.

For complex requests (sprite sheet, multiple variants, specific art direction), write a 2-3 line brief before generating:

```
Brief: 16-bit JRPG warrior, front-facing idle pose. Dark steel armor with red cape.
       Limited 32-color palette, NES-inspired. Transparent background.
       Reference: Final Fantasy VI sprite style.
```

Show the brief to the user. If they approve (or you're confident), proceed.

### Phase 3: Craft Prompt

Translate the user's intent into an English prompt for Gemini. Rules:

- Include ONLY what the user expressed (directly or through Q&A)
- Write in plain English, be specific and visual
- End with technical constraints: size, single sprite, background type
- For game sprites, "solid magenta (#FF00FF) background" often works better than "transparent" for clean extraction

Example prompts:
- `"16-bit RPG warrior sprite, front-facing idle pose, dark steel armor with red cape, NES-inspired limited palette, solid magenta background, single 32x32 sprite"`
- `"cute slime monster, side view, bouncy shape, green translucent body, pixel art style, 64x64, transparent background"`

### Phase 4: Generate

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" generate "<your crafted prompt>" \
  --output-dir "<from config>" \
  --name <short_name> \
  --size <size> \
  --category <category>
```

### Phase 5: Validate & Show

1. Display the image with Read tool
2. Check: does it match the brief? Is the style consistent?
3. If the image looks off, tell the user what went wrong and offer to regenerate with an adjusted prompt

### Phase 6: Iterate

Ask if they want changes. Common adjustments:
- "Change the pose?"
- "Adjust the colors?"
- "More detail / simpler?"
- "Try a different style?"

If they say it's good, you're done.

---

## Sprite Sheet Workflow (Anchor-Frame Method)

When generating multiple frames (walk cycle, attack animation, etc.):

1. **Generate the anchor frame first** — this sets the style, palette, proportions
2. Show the anchor to the user for approval
3. **Generate remaining frames in as few prompts as possible**, referencing the anchor's style explicitly in each prompt
4. Combine into a sheet:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" sheet "<name>" \
  --output-dir "<from config>" \
  --size <size> \
  --category <category> \
  --frames '<json: [{"name":"idle","description":"..."},{"name":"walk1","description":"..."}]>'
```

Tip: describe each frame relative to the anchor. E.g.:
- Anchor: "16-bit warrior, front-facing idle, dark armor, red cape, pixel art, 32x32"
- Frame 2: "same warrior as before, left foot forward, walking pose, same style and palette"
- Frame 3: "same warrior, right foot forward, walking pose, same style and palette"

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

---

## First Run Setup

Before any command, check if config exists:
```bash
cat "${CLAUDE_PLUGIN_DATA}/config.json" 2>/dev/null
```

If it doesn't exist or fails, run setup:

1. `pip install -U 'gemini_webapi[browser]' Pillow`
2. Ask user: "Where should sprites be saved?" (default: `./sprites`)
3. Save config:
```bash
mkdir -p "${CLAUDE_PLUGIN_DATA}"
cat > "${CLAUDE_PLUGIN_DATA}/config.json" << 'EOF'
{
  "output_dir": "<user's answer>",
  "default_size": 32
}
EOF
```
4. `python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" check`

If config exists, read `output_dir` from it and use it for all `--output-dir` arguments.

## Paths

- Script: `${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py`
- Config: `${CLAUDE_PLUGIN_DATA}/config.json`

## Options

| Option | Values | Default |
|--------|--------|---------|
| `--size` | 16, 32, 64, 128 | 32 |
| `--category` | character, item, tile, effect, ui | character |
| `--name` | any string | auto from description |
