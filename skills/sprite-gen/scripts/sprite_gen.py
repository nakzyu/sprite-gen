"""
sprite_gen.py - 2D game sprite generator and manager using Gemini.
Uses gemini_webapi (Google Gemini subscription-based cookie/OAuth authentication).
Designed for portable use - all paths are passed as arguments.
Supports multi-turn sessions for style-consistent sprite generation.
"""

import asyncio
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CATEGORIES = ["character", "item", "tile", "effect", "ui"]


def _ensure_dependencies():
    """Automatically install missing dependencies."""
    missing = []
    try:
        import gemini_webapi  # noqa: F401
    except ImportError:
        missing.append("gemini_webapi[browser]")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow")

    if missing:
        print(f"Auto-installing missing packages: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-U", *missing],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("Installation complete.")


_ensure_dependencies()

from gemini_webapi import GeminiClient  # noqa: E402

# Reduce retry delay between stream reconnects (default 5s → 1s).
# Image generation causes repeated stream interruptions; the default
# delays of 5/10/15/20/25s waste ~75s.  With factor=1 → 1/2/3/4/5s = 15s.
import gemini_webapi.utils.decorators as _deco  # noqa: E402
_deco.DELAY_FACTOR = 3

try:
    from PIL import Image
except ImportError:
    Image = None


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def _manifest_path(output_dir: Path) -> Path:
    return output_dir / "manifest.json"


def load_manifest(output_dir: Path) -> dict:
    mp = _manifest_path(output_dir)
    if mp.exists():
        with open(mp) as f:
            return json.load(f)
    return {"sprites": []}


def save_manifest(output_dir: Path, manifest: dict):
    mp = _manifest_path(output_dir)
    mp.parent.mkdir(parents=True, exist_ok=True)
    with open(mp, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _sessions_dir(output_dir: Path) -> Path:
    return output_dir / ".sessions"


def load_session(output_dir: Path, session_name: str) -> dict | None:
    """Load saved chat session metadata."""
    path = _sessions_dir(output_dir) / f"{session_name}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def save_session(output_dir: Path, session_name: str, metadata: list,
                 description: str | None = None, sprite_entry: dict | None = None):
    """Save chat session metadata and history for later resumption."""
    sess_dir = _sessions_dir(output_dir)
    sess_dir.mkdir(parents=True, exist_ok=True)
    path = sess_dir / f"{session_name}.json"

    existing = load_session(output_dir, session_name) or {
        "metadata": [],
        "created_at": datetime.now().isoformat(),
        "history": [],
    }

    existing["metadata"] = metadata
    existing["updated_at"] = datetime.now().isoformat()

    if description or sprite_entry:
        turn = {"timestamp": datetime.now().isoformat()}
        if description:
            turn["prompt"] = description
        if sprite_entry:
            turn["sprite"] = {
                "name": sprite_entry.get("name"),
                "filename": sprite_entry.get("filename"),
                "path": sprite_entry.get("path"),
                "category": sprite_entry.get("category"),
                "size": sprite_entry.get("size"),
            }
        existing.setdefault("history", []).append(turn)

    with open(path, "w") as f:
        json.dump(existing, f, indent=2)


def delete_session(output_dir: Path, session_name: str) -> bool:
    path = _sessions_dir(output_dir) / f"{session_name}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def list_sessions(output_dir: Path) -> list[str]:
    sess_dir = _sessions_dir(output_dir)
    if not sess_dir.exists():
        return []
    return [p.stem for p in sess_dir.glob("*.json")]


# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

def _clear_cookie_cache():
    """Delete cached cookies so the next init loads fresh ones from Chrome."""
    import tempfile
    cache_dir = Path(tempfile.gettempdir()) / "gemini_webapi"
    if cache_dir.exists():
        for f in cache_dir.glob(".cached_cookies_*.json"):
            f.unlink()
            print(f"Cleared stale cookie cache: {f.name}", file=sys.stderr)


async def create_client(timeout: int = 450) -> GeminiClient:
    """Create a Gemini client via browser cookie auto-extraction.
    Auto-clears cookie cache and retries if UNAUTHENTICATED."""
    from gemini_webapi.constants import AccountStatus

    for attempt in range(2):
        try:
            client = GeminiClient()
            await client.init(timeout=timeout, auto_close=False, watchdog_timeout=120)

            if client.account_status == AccountStatus.UNAUTHENTICATED and attempt == 0:
                print("Session expired, refreshing cookies from browser...", file=sys.stderr)
                await client.close()
                _clear_cookie_cache()
                continue

            return client
        except Exception as e:
            if attempt == 0:
                _clear_cookie_cache()
                continue
            print(f"Error: Could not authenticate with Gemini: {e}")
            print("  - Make sure you are logged in to gemini.google.com in Chrome/Firefox.")
            sys.exit(1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_check():
    """Verify Gemini authentication works."""
    client = await create_client(timeout=30)
    await client.close()
    print(json.dumps({"success": True, "message": "Gemini authentication OK."}))


async def cmd_generate(output_dir: Path, description: str, name: str | None,
                       size: int, category: str, session_name: str | None = None,
                       quiet: bool = False) -> dict | None:
    """Generate a single sprite. Uses chat session if session_name is provided."""
    if category not in CATEGORIES:
        result = {"success": False, "error": f"Unsupported category: {category}. Available: {CATEGORIES}"}
        if not quiet:
            print(json.dumps(result))
        return result

    if not name:
        name = description.lower().replace(" ", "_")[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{category}_{name}_{timestamp}.png"

    category_dir = output_dir / category
    category_dir.mkdir(parents=True, exist_ok=True)
    output_path = category_dir / filename

    client = await create_client()

    try:
        # Use multi-turn session if provided
        if session_name:
            saved = load_session(output_dir, session_name)
            if saved:
                chat = client.start_chat(metadata=saved["metadata"])
            else:
                chat = client.start_chat()
            response = await chat.send_message(description)
            # session metadata saved after sprite entry is created (below)
            _chat_to_save = chat
        else:
            _chat_to_save = None
            response = await client.generate_content(description)

        if response.images:
            image = response.images[0]
            await image.save(path=str(category_dir), filename=filename)
        elif response.text and re.search(r'https?://[^\s]*googleusercontent\.com/[^\s]+', response.text):
            # Fallback: library didn't parse the image URL, download directly
            url = re.search(r'https?://[^\s]*googleusercontent\.com/[^\s]+', response.text).group(0)
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome") as sess:
                cookies = getattr(client, 'cookies', None)
                resp = await sess.get(url, headers={
                    "Origin": "https://gemini.google.com",
                    "Referer": "https://gemini.google.com/",
                }, cookies=cookies)
                if resp.status_code == 200:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(resp.content)
                else:
                    result = {"success": False, "error": f"Image download failed: {resp.status_code}"}
                    if not quiet:
                        print(json.dumps(result))
                    return result
        else:
            if session_name and _chat_to_save:
                save_session(output_dir, session_name, _chat_to_save.metadata,
                             description=description)
            result = {
                "success": False,
                "error": "No image was generated. Try adjusting the prompt.",
                "gemini_response": response.text[:500] if response.text else None,
            }
            if not quiet:
                print(json.dumps(result))
            return result

        entry = {
            "name": name,
            "filename": filename,
            "path": str(output_path),
            "category": category,
            "size": size,
            "description": description,
            "session": session_name,
            "created_at": datetime.now().isoformat(),
        }
        manifest = load_manifest(output_dir)
        manifest["sprites"].append(entry)
        save_manifest(output_dir, manifest)

        if session_name and _chat_to_save:
            save_session(output_dir, session_name, _chat_to_save.metadata,
                         description=description, sprite_entry=entry)

        result = {"success": True, "entry": entry}
        if not quiet:
            print(json.dumps(result, indent=2))
        return result

    finally:
        await client.close()


async def cmd_sheet(output_dir: Path, sheet_name: str, frames_json: str,
                    size: int, category: str, session_name: str | None = None):
    """Generate multiple sprites and combine into a spritesheet.
    Uses a shared session across all frames for style consistency."""
    if not Image:
        print(json.dumps({"success": False, "error": "Pillow is required."}))
        return

    # Use sheet name as session if no explicit session given
    effective_session = session_name or sheet_name

    frames = json.loads(frames_json)
    results = []
    for frame in frames:
        result = await cmd_generate(
            output_dir=output_dir,
            description=frame["description"],
            name=frame.get("name"),
            size=size, category=category,
            session_name=effective_session,
            quiet=True,
        )
        if result and result.get("success"):
            results.append(result["entry"])

    if not results:
        print(json.dumps({"success": False, "error": "No sprites were generated."}))
        return

    cols = len(results)
    sheet = Image.new("RGBA", (size * cols, size), (0, 0, 0, 0))
    for i, entry in enumerate(results):
        sprite_path = Path(entry["path"])
        if sprite_path.exists():
            sprite = Image.open(sprite_path).convert("RGBA")
            sheet.paste(sprite, (i * size, 0))

    sheet_dir = output_dir / "sheets"
    sheet_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sheet_filename = f"sheet_{sheet_name}_{timestamp}.png"
    sheet_path = sheet_dir / sheet_filename
    sheet.save(sheet_path)

    print(json.dumps({
        "success": True,
        "sheet_path": str(sheet_path),
        "sprite_count": cols,
        "session": effective_session,
    }, indent=2))


def cmd_list(output_dir: Path, category: str | None):
    manifest = load_manifest(output_dir)
    sprites = manifest["sprites"]
    if category:
        sprites = [s for s in sprites if s["category"] == category]
    print(json.dumps(sprites, indent=2))


def cmd_delete(output_dir: Path, name: str):
    manifest = load_manifest(output_dir)
    to_remove = None
    for sprite in manifest["sprites"]:
        if sprite["name"] == name or sprite["filename"] == name:
            to_remove = sprite
            break

    if not to_remove:
        print(json.dumps({"success": False, "error": f"Not found: {name}"}))
        return

    file_path = Path(to_remove["path"])
    if file_path.exists():
        file_path.unlink()

    manifest["sprites"].remove(to_remove)
    save_manifest(output_dir, manifest)
    print(json.dumps({"success": True, "deleted": name}))


def cmd_organize(output_dir: Path):
    manifest = load_manifest(output_dir)
    original_count = len(manifest["sprites"])
    cleaned = [s for s in manifest["sprites"] if Path(s["path"]).exists()]
    manifest["sprites"] = cleaned
    save_manifest(output_dir, manifest)
    print(json.dumps({"total": len(cleaned), "removed_orphans": original_count - len(cleaned)}))


def cmd_sessions(output_dir: Path):
    """List all active sessions with their history."""
    session_names = list_sessions(output_dir)
    sessions = []
    for name in session_names:
        data = load_session(output_dir, name)
        if data:
            sessions.append({
                "name": name,
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "turns": len(data.get("history", [])),
                "history": data.get("history", []),
            })
    print(json.dumps({"sessions": sessions}, indent=2))


def cmd_end_session(output_dir: Path, session_name: str):
    """End (delete) a session."""
    deleted = delete_session(output_dir, session_name)
    print(json.dumps({"success": deleted, "session": session_name}))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(args: list[str]) -> dict:
    """Parse --key value pairs from args list."""
    result = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            key = args[i][2:].replace("-", "_")
            result[key] = args[i + 1]
            i += 2
        else:
            i += 1
    return result


async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  sprite_gen.py check")
        print("  sprite_gen.py generate <desc> --output-dir DIR [--name N] [--size 32] [--category character] [--session NAME]")
        print("  sprite_gen.py sheet <name> --output-dir DIR --frames '<json>' [--size 32] [--category character] [--session NAME]")
        print("  sprite_gen.py list --output-dir DIR [--category CAT]")
        print("  sprite_gen.py delete <name> --output-dir DIR")
        print("  sprite_gen.py organize --output-dir DIR")
        print("  sprite_gen.py sessions --output-dir DIR")
        print("  sprite_gen.py end-session <name> --output-dir DIR")
        return

    command = sys.argv[1]

    if command == "check":
        await cmd_check()
        return

    opts = parse_args(sys.argv[2:])
    output_dir = Path(opts.get("output_dir", "./sprites")).resolve()

    if command == "generate":
        if len(sys.argv) < 3 or sys.argv[2].startswith("--"):
            print("Error: Please provide a description.")
            return
        await cmd_generate(
            output_dir=output_dir,
            description=sys.argv[2],
            name=opts.get("name"),
            size=int(opts.get("size", 32)),
            category=opts.get("category", "character"),
            session_name=opts.get("session"),
        )

    elif command == "sheet":
        if len(sys.argv) < 3 or sys.argv[2].startswith("--"):
            print("Error: Please provide a sheet name.")
            return
        await cmd_sheet(
            output_dir=output_dir,
            sheet_name=sys.argv[2],
            frames_json=opts.get("frames", "[]"),
            size=int(opts.get("size", 32)),
            category=opts.get("category", "character"),
            session_name=opts.get("session"),
        )

    elif command == "list":
        cmd_list(output_dir, opts.get("category"))

    elif command == "delete":
        if len(sys.argv) < 3 or sys.argv[2].startswith("--"):
            print("Error: Please provide a sprite name.")
            return
        cmd_delete(output_dir, sys.argv[2])

    elif command == "organize":
        cmd_organize(output_dir)

    elif command == "sessions":
        cmd_sessions(output_dir)

    elif command == "end-session":
        if len(sys.argv) < 3 or sys.argv[2].startswith("--"):
            print("Error: Please provide a session name.")
            return
        cmd_end_session(output_dir, sys.argv[2])

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
