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
- Default → "transparent background"
- If the user specifies, use what they say

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

For follow-ups in an existing session, reference the previous generation naturally:
- "same warrior but in a walking pose, left foot forward"
- "adjust the colors to be darker, keep everything else the same"

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
2. Ask user: "Where should sprites be saved?" (default: `./sprites`)
3. Save config:
```bash
mkdir -p "${CLAUDE_PLUGIN_DATA}"
cat > "${CLAUDE_PLUGIN_DATA}/config.json" << 'EOF'
{
  "output_dir": "<user's answer>"
}
EOF
```
4. `python3 "${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py" check`

If config exists, read `output_dir` from it and use it for all `--output-dir` arguments.

## Paths

- Script: `${CLAUDE_SKILL_DIR}/scripts/sprite_gen.py`
- Config: `${CLAUDE_PLUGIN_DATA}/config.json`
