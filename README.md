# sprite-gen

Claude Code plugin for generating and managing 2D game sprites using Google Gemini.

Uses Gemini's image generation via subscription-based browser cookie authentication (`gemini_webapi`), not API keys.

## Requirements

- Python 3.10+
- Google Gemini subscription (must be logged in to gemini.google.com in your browser)
- Chrome or Firefox

## Installation

```bash
/plugin marketplace add nakzyu/sprite-gen
/plugin install sprite-gen@sprite-gen
```

Or for local development:

```bash
git clone https://github.com/nakzyu/sprite-gen.git
claude --plugin-dir ./sprite-gen
```

Dependencies (`gemini_webapi[browser]`, `Pillow`) are auto-installed on first run.

## Usage

### Generate a sprite

```
/sprite-gen warrior character 32px
```

If the request is vague, it will ask about style, view angle, purpose, etc.
If detailed enough, it generates immediately.

```
/sprite-gen 16-bit RPG warrior, front-facing, Final Fantasy style, 32px
```

### Generate a sprite sheet

```
/sprite-gen warrior walk cycle, 4 frames, sprite sheet
```

Uses an anchor-frame method: generates the first frame, gets approval, then generates remaining frames referencing the anchor's style for consistency.

### List sprites

```
/sprite-gen list
/sprite-gen list --category character
```

### Delete a sprite

```
/sprite-gen delete warrior
```

### Organize (remove orphaned manifest entries)

```
/sprite-gen organize
```

## Workflow

```
Request → (if vague) Questions → Creative brief → Gemini prompt → Generate → Validate → Iterate
```

1. **Understand**: Analyze the request. Ask 2-3 questions if key details are missing
2. **Brief**: For complex requests, write a 2-3 line creative brief
3. **Prompt**: Translate user intent into an English prompt for Gemini (constructed by Claude)
4. **Generate**: Send prompt to Gemini, save the image
5. **Validate**: Display result, suggest regeneration if it doesn't match intent
6. **Iterate**: Apply adjustments based on user feedback

## Options

| Option | Values | Default |
|--------|--------|---------|
| size | 16, 32, 64, 128 | 32 |
| category | character, item, tile, effect, ui | character |

## Project Structure

```
sprite-gen/
├── .claude-plugin/
│   └── marketplace.json        # Plugin manifest
├── skills/
│   └── sprite-gen/
│       ├── SKILL.md            # Skill definition (workflow)
│       └── scripts/
│           └── sprite_gen.py   # Gemini call script
├── .gitignore
├── LICENSE
└── README.md
```

## How It Works

- **SKILL.md**: Claude's workflow instructions. All logic for questioning, prompt construction, and validation lives here
- **sprite_gen.py**: A dumb pipe — calls Gemini API, saves images, manages the manifest
- **Prompt construction**: Claude interprets user intent and crafts the Gemini prompt directly. The script adds nothing to the prompt

## License

MIT
