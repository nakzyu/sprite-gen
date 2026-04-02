# sprite-gen

Claude Code plugin for generating and managing 2D game sprites using Google Gemini.

Uses Gemini's image generation via subscription-based browser cookie authentication (`gemini_webapi`), not API keys.

## Requirements

- Python 3.10+
- Google Gemini subscription (logged in to gemini.google.com in Chrome/Firefox)

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

Dependencies (`gemini_webapi`, `Pillow`) are auto-installed on first run.

## Usage

### Generate a sprite

```
/sprite-gen warrior character
```

If detailed enough, it generates immediately. If vague, it asks 2-3 questions first.

```
/sprite-gen 16-bit RPG warrior, front-facing, Final Fantasy style
```

### Style consistency (multi-turn sessions)

The plugin automatically maintains Gemini conversation sessions for related sprites. Gemini remembers the art style, palette, and design from previous generations.

```
/sprite-gen cute slime character for a platformer
```
→ generates slime

```
/sprite-gen make the same slime but jumping
```
→ same session — consistent style

### Resume previous work

```
/sprite-gen what was I working on?
```
→ shows previous sessions with generated sprites

```
/sprite-gen continue the warrior
```
→ resumes with full Gemini context

### Sprite sheets

```
/sprite-gen warrior walk cycle, 4 frames, sprite sheet
```

Generates an anchor frame first for approval, then remaining frames in the same session.

### Management

```
/sprite-gen list
/sprite-gen list --category character
/sprite-gen delete warrior
/sprite-gen organize
```

## Features

- **Auto cookie refresh**: Detects expired Gemini sessions and automatically reloads cookies from browser
- **Watermark removal**: Automatically removes the Gemini sparkle watermark from generated images
- **Image URL fallback**: Directly downloads images when the library fails to parse the response
- **Retry optimization**: Reduced stream reconnection delays for faster generation

## How It Works

- **SKILL.md**: Claude's workflow instructions — questioning, prompt construction, session management
- **sprite_gen.py**: Calls Gemini, saves images, manages manifest and sessions. Claude constructs all prompts
- **Multi-turn sessions**: Maintains Gemini conversation context via `gemini_webapi` ChatSession for style consistency

## Project Structure

```
sprite-gen/
├── .claude-plugin/
│   └── marketplace.json
├── skills/
│   └── sprite-gen/
│       ├── SKILL.md
│       └── scripts/
│           └── sprite_gen.py
├── .gitignore
├── LICENSE
└── README.md
```

## License

MIT
