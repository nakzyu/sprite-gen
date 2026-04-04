# gemini-sprite-gen

<p align="center">
  <img src="demo.gif" alt="Idle animation demo" width="256" />
  <br>
  <em>5-frame idle animation with eye blink — generated with Gemini Pro</em>
</p>

Claude Code plugin for generating 2D game sprites using Google Gemini.

Uses browser cookie auth ([`gemini_webapi`](https://github.com/HanaokaYuzu/Gemini-API)) — no API keys needed.

## Requirements

- Python 3.10+
- Google Gemini subscription (logged in to gemini.google.com in Chrome or Firefox)

## Installation

```bash
/plugin marketplace add nakzyu/gemini-sprite-gen
/plugin install gemini-sprite-gen@gemini-sprite-gen
```

Or for local development:

```bash
git clone https://github.com/nakzyu/gemini-sprite-gen.git
claude --plugin-dir ./gemini-sprite-gen
```

Dependencies are auto-installed on first run.

## Usage

### Generate

```
/gemini-sprite-gen warrior character
/gemini-sprite-gen 16-bit RPG warrior, front-facing, Final Fantasy style
```

If the request is vague, it asks 2-3 clarifying questions first.

### Reference images

Attach images to guide style or convert existing characters:

```
/gemini-sprite-gen convert this character to chibi pixel art [attach image]
/gemini-sprite-gen make this into a 16-bit RPG sprite [attach image]
```

### Multi-turn sessions

Each subject gets its own Gemini session for style consistency:

```
/gemini-sprite-gen cute slime for a platformer     ← new session
/gemini-sprite-gen make it jumping                  ← same session, same style
```

Sessions persist across conversations:

```
/gemini-sprite-gen what was I working on?           ← list previous sessions
/gemini-sprite-gen continue the warrior             ← resume with full context
```

### Sprite sheets

```
/gemini-sprite-gen warrior walk cycle, 4 frames, sprite sheet
```

Generates an anchor frame for approval, then remaining frames in the same session.

### Management

```
/gemini-sprite-gen list
/gemini-sprite-gen list --category character
/gemini-sprite-gen delete warrior
/gemini-sprite-gen organize
```

## Features

- **Gemini Pro** — uses `gemini-3-pro` for higher quality generation
- **Real transparency** — auto chromakey green screen + HSV removal with despill
- **Reference images** — attach images to guide style; prompt text stays minimal
- **Auto cookie refresh** — detects expired sessions, reloads from browser
- **Watermark removal** — reverse alpha blending removes Gemini sparkle watermark
- **Portable manifest** — relative paths for cross-machine compatibility

## How transparency works

Gemini cannot output PNG alpha channels — it draws checkerboard patterns instead. This plugin works around that:

1. Appends chromakey green (`#00FF00`) background instruction to every prompt
2. HSV-based color detection identifies and removes the green background
3. Edge pixels are despilled to remove green color bleed
4. Result: clean PNG with real transparency

## License

MIT
