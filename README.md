# sprite-gen

Claude Code plugin for generating and managing 2D game sprites using Google Gemini.

Uses Gemini's image generation via browser cookie authentication ([`gemini_webapi`](https://github.com/HanaokaYuzu/Gemini-API)), not API keys.

## Requirements

- Python 3.10+
- Google Gemini subscription (logged in to gemini.google.com in Chrome or Firefox)

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

Dependencies are auto-installed on first run via `requirements.txt`.

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

The plugin uses Gemini's multi-turn conversation to keep sprites consistent. Each subject gets its own session — Gemini remembers the art style, palette, and design from previous turns, so follow-up requests produce visually coherent results without re-describing everything.

```
/sprite-gen cute slime character for a platformer
```
→ generates slime, starts a new session

```
/sprite-gen make the same slime but jumping
```
→ same session — Gemini already knows the slime's style

### Resume previous work

Sessions persist across conversations. You can pick up where you left off:

```
/sprite-gen what was I working on?     ← shows previous sessions
/sprite-gen continue the warrior       ← resumes with full Gemini context
```

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

- **Auto cookie refresh** — detects expired Gemini sessions and reloads cookies from browser automatically
- **Watermark removal** — removes the Gemini sparkle watermark via reverse alpha blending, restoring original pixels with zero artifacts

## License

MIT
