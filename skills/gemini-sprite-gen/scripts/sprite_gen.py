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
    """Install missing dependencies from requirements.txt."""
    try:
        import gemini_webapi  # noqa: F401
        from PIL import Image  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        req_file = Path(__file__).parent / "requirements.txt"
        print(f"Installing dependencies from {req_file.name}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("Installation complete.")


_ensure_dependencies()

from gemini_webapi import GeminiClient  # noqa: E402
from gemini_webapi.constants import Model  # noqa: E402

# Reduce retry delay between stream reconnects (default 5s → 1s).
# Image generation causes repeated stream interruptions; the default
# delays of 5/10/15/20/25s waste ~75s.  With factor=1 → 1/2/3/4/5s = 15s.
import gemini_webapi.utils.decorators as _deco  # noqa: E402
_deco.DELAY_FACTOR = 3

try:
    from PIL import Image
except ImportError:
    Image = None


GREENSCREEN_PROMPT_SUFFIX = """

CRITICAL BACKGROUND REQUIREMENT:
- Background MUST be solid, flat, uniform chromakey green (#00FF00, RGB 0,255,0).
- NO gradients, NO shadows, NO lighting effects on the background.
- The subject itself must NOT contain any green colors.
"""


def _remove_green_screen(image_path: Path):
    """Remove chromakey green background and replace with real transparency."""
    if not Image:
        return
    try:
        import numpy as np
    except ImportError:
        return

    img = Image.open(image_path).convert("RGBA")
    data = np.array(img, dtype=np.float32)
    rgb = data[:, :, :3]

    # Convert RGB to HSV for robust green detection
    r, g, b = rgb[:, :, 0] / 255, rgb[:, :, 1] / 255, rgb[:, :, 2] / 255
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    delta = max_c - min_c

    # Hue
    hue = np.zeros_like(max_c)
    mask_g = (max_c == g) & (delta != 0)
    mask_b = (max_c == b) & (delta != 0)
    mask_r = (max_c == r) & (delta != 0)
    hue[mask_r] = (60 * ((g[mask_r] - b[mask_r]) / delta[mask_r]) + 360) % 360
    hue[mask_g] = (60 * ((b[mask_g] - r[mask_g]) / delta[mask_g]) + 120) % 360
    hue[mask_b] = (60 * ((r[mask_b] - g[mask_b]) / delta[mask_b]) + 240) % 360

    # Saturation and Value (0-100 scale)
    sat = np.zeros_like(max_c)
    sat[max_c != 0] = (delta[max_c != 0] / max_c[max_c != 0]) * 100
    val = max_c * 100

    # Detect green: hue near 120°, high saturation, high value
    hue_diff = np.abs(hue - 120)
    hue_diff = np.minimum(hue_diff, 360 - hue_diff)
    green_mask = (hue_diff < 30) & (sat > 40) & (val > 40)

    # Dilate mask slightly to catch anti-aliased edge pixels
    from scipy import ndimage
    green_mask = ndimage.binary_dilation(green_mask, iterations=1)

    # Apply transparency and zero out RGB for transparent pixels
    alpha = data[:, :, 3].copy()
    alpha[green_mask] = 0
    data[:, :, 3] = alpha
    data[green_mask, 0] = 0
    data[green_mask, 1] = 0
    data[green_mask, 2] = 0

    # Despill: remove green tint from edge pixels (semi-transparent neighbors)
    edge_mask = ndimage.binary_dilation(green_mask, iterations=2) & ~green_mask
    for y, x in zip(*np.where(edge_mask)):
        r_val, g_val, b_val = data[y, x, 0], data[y, x, 1], data[y, x, 2]
        if g_val > max(r_val, b_val):
            data[y, x, 1] = max(r_val, b_val)

    result = Image.fromarray(np.clip(data, 0, 255).astype(np.uint8))
    result.save(image_path)


def _remove_watermark(image_path: Path):
    """Remove the Gemini sparkle watermark using reverse alpha blending.
    Uses pre-extracted alpha maps from the official watermark."""
    if not Image:
        return
    try:
        import base64
        import struct
        import numpy as np
    except ImportError:
        return

    alpha_file = Path(__file__).parent / "watermark_alpha.json"
    if not alpha_file.exists():
        return

    img = Image.open(image_path).convert("RGBA")
    w, h = img.size

    # Select watermark size based on image dimensions
    if w > 1024 and h > 1024:
        logo_size, margin = 96, 64
    else:
        logo_size, margin = 48, 32

    with open(alpha_file) as f:
        alpha_b64 = json.load(f).get(str(logo_size))
    if not alpha_b64:
        return

    data = base64.b64decode(alpha_b64)
    n = len(data) // 4
    alpha_map = np.array(struct.unpack(f"<{n}f", data), dtype=np.float32).reshape(logo_size, logo_size)

    # Watermark position: bottom-right corner with margin
    x = w - margin - logo_size
    y = h - margin - logo_size
    region = np.array(img.crop((x, y, x + logo_size, y + logo_size)), dtype=np.float32)

    # Reverse alpha blending: original = (watermarked - α * 255) / (1 - α)
    mask = alpha_map > 0.001
    for c in range(3):
        region[:, :, c][mask] = (
            (region[:, :, c][mask] - alpha_map[mask] * 255.0) / (1.0 - alpha_map[mask])
        )
    region = np.clip(region, 0, 255).astype(np.uint8)

    img.paste(Image.fromarray(region), (x, y))
    img.save(image_path)


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
            await client.init(timeout=timeout, auto_close=False, watchdog_timeout=300)

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
# Patch: fix image parsing when files are attached
# ---------------------------------------------------------------------------
# When files are attached to a request, candidate_data[12] comes back as a
# list containing dicts instead of nested lists. The library's _parse_candidate
# looks at [12][7][0] (list indexing) which misses the dict structure.
# The actual image URL is at: candidate_data[12][0]['8'][0][0][0][3][1]

def _patch_parse_candidate():
    """Monkey-patch GeminiClient._parse_candidate to handle dict responses."""
    from gemini_webapi.utils.parsing import get_nested_value
    from gemini_webapi.types import GeneratedImage

    _original = GeminiClient._parse_candidate

    def _patched(self, candidate_data, cid, rid, rcid):
        result = _original(self, candidate_data, cid, rid, rcid)
        text, thoughts, web_images, generated_images, generated_videos, generated_media = result

        # If no generated images found, check for dict structure
        if not generated_images:
            try:
                cd12 = get_nested_value(candidate_data, [12], None)
                if cd12 and isinstance(cd12, list) and len(cd12) > 0 and isinstance(cd12[0], dict):
                    items = cd12[0].get('8', [])
                    for img_idx, item in enumerate(items):
                        url = None
                        try:
                            # item structure: [[[None, None, None, [None, 1, 'file.png', 'https://...', ...]]]]
                            url_data = item[0][0][3]
                            # Find the googleusercontent URL in the list
                            for v in url_data:
                                if isinstance(v, str) and 'googleusercontent.com' in v:
                                    url = v
                                    break
                        except (IndexError, TypeError, KeyError):
                            pass
                        if url:
                            image_id = None
                            try:
                                image_id = item[0][0][3][2]
                            except (IndexError, TypeError, KeyError):
                                pass
                            if not image_id:
                                image_id = f"image_{img_idx}"
                            generated_images.append(
                                GeneratedImage(
                                    url=url,
                                    title=f"[Generated Image {img_idx}]",
                                    alt="",
                                    proxy=self.proxy,
                                    client=self.client,
                                    client_ref=self,
                                    cid=cid, rid=rid, rcid=rcid,
                                    image_id=image_id,
                                )
                            )
            except Exception:
                pass

        return text, thoughts, web_images, generated_images, generated_videos, generated_media

    GeminiClient._parse_candidate = _patched

_patch_parse_candidate()


async def _download_image(client, url: str, output_path: Path):
    """Download image using the library's internal authenticated session directly."""
    inner_session = getattr(client, 'client', None)
    if not inner_session:
        raise RuntimeError("No internal session available for image download")

    headers = {"Referer": "https://gemini.google.com/"}

    # Build a set of URL variants to try — different suffixes resolve differently
    base_url = url
    for suffix in ["=s2048-rj", "=s1024-rj", "=s512-rj", "=d-I?alr=yes"]:
        if suffix in base_url:
            base_url = base_url.replace(suffix, "")
            break

    urls_to_try = [
        url,                         # original URL as-is
        base_url + "=s1024-rj",      # preview size
        base_url + "=s512-rj",       # smaller preview
        base_url,                    # bare URL (no suffix)
        base_url + "=s2048-rj",     # full size
    ]
    # Deduplicate while preserving order
    seen = set()
    urls_to_try = [u for u in urls_to_try if not (u in seen or seen.add(u))]

    last_status = None
    for try_url in urls_to_try:
        resp = await inner_session.get(try_url, headers=headers)
        if resp.status_code == 200 and len(resp.content) > 100:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(resp.content)
            return
        last_status = resp.status_code

    # Last resort: create a fresh client with new cookies and retry
    try:
        fresh_client = await create_client(timeout=30)
        fresh_session = getattr(fresh_client, 'client', None)
        if fresh_session:
            for try_url in urls_to_try:
                resp = await fresh_session.get(try_url, headers=headers)
                if resp.status_code == 200 and len(resp.content) > 100:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(resp.content)
                    await fresh_client.close()
                    return
                last_status = resp.status_code
            await fresh_client.close()
    except Exception:
        pass

    raise RuntimeError(f"Image download failed after all attempts, last status: {last_status}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_check():
    """Verify Gemini authentication works."""
    client = await create_client(timeout=30)
    await client.close()
    print(json.dumps({"success": True, "message": "Gemini authentication OK."}))


async def cmd_generate(output_dir: Path, description: str, name: str | None,
                       category: str, session_name: str | None = None,
                       files: list[str] | None = None,
                       quiet: bool = False) -> dict | None:
    """Generate a single sprite. Uses chat session if session_name is provided.
    files: optional list of file paths to attach (images, etc.)."""
    # Auto-append green screen instructions for transparent background
    description = description + GREENSCREEN_PROMPT_SUFFIX

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
        # Resolve file paths
        file_paths = [Path(f) for f in files] if files else None

        # Use multi-turn session if provided
        if session_name:
            saved = load_session(output_dir, session_name)
            if saved:
                chat = client.start_chat(metadata=saved["metadata"], model=Model.BASIC_PRO)
                try:
                    response = await chat.send_message(description, files=file_paths)
                except Exception as e:
                    # Session likely deleted on Gemini's side — clean up and start fresh
                    print(f"Session '{session_name}' expired on Gemini, starting fresh: {e}", file=sys.stderr)
                    delete_session(output_dir, session_name)
                    chat = client.start_chat(model=Model.BASIC_PRO)
                    response = await chat.send_message(description, files=file_paths)
            else:
                chat = client.start_chat(model=Model.BASIC_PRO)
                response = await chat.send_message(description, files=file_paths)
            # session metadata saved after sprite entry is created (below)
            _chat_to_save = chat
        else:
            _chat_to_save = None
            response = await client.generate_content(description, files=file_paths, model=Model.BASIC_PRO)

        if response.images:
            image = response.images[0]
            saved_ok = False
            # Try library save (full size first, then preview size)
            for full_size in [True, False]:
                try:
                    await image.save(path=str(category_dir), filename=filename, full_size=full_size)
                    saved_ok = True
                    break
                except Exception:
                    continue
            if not saved_ok:
                # Fallback: download with authenticated session
                image_url = getattr(image, 'url', None)
                if image_url:
                    await _download_image(client, image_url, output_path)
                else:
                    raise RuntimeError("No image URL available for download")
        elif response.text and re.search(r'https?://[^\s]*googleusercontent\.com/[^\s]+', response.text):
            # Fallback: library didn't parse the image URL, download directly
            url = re.search(r'https?://[^\s]*googleusercontent\.com/[^\s]+', response.text).group(0)
            await _download_image(client, url, output_path)
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

        _remove_watermark(output_path)
        _remove_green_screen(output_path)

        entry = {
            "name": name,
            "filename": filename,
            "path": str(output_path.relative_to(output_dir)),
            "category": category,
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
                    category: str, session_name: str | None = None):
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
            category=category,
            session_name=effective_session,
            quiet=True,
        )
        if result and result.get("success"):
            results.append(result["entry"])

    if not results:
        print(json.dumps({"success": False, "error": "No sprites were generated."}))
        return

    # Combine into horizontal strip using actual image sizes
    images = []
    for entry in results:
        sprite_path = output_dir / entry["path"]
        if sprite_path.exists():
            images.append(Image.open(sprite_path).convert("RGBA"))

    if not images:
        print(json.dumps({"success": False, "error": "No sprite images found."}))
        return

    max_h = max(img.height for img in images)
    total_w = sum(img.width for img in images)
    sheet = Image.new("RGBA", (total_w, max_h), (0, 0, 0, 0))
    x_offset = 0
    for img in images:
        sheet.paste(img, (x_offset, 0))
        x_offset += img.width

    sheet_dir = output_dir / "sheets"
    sheet_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sheet_filename = f"sheet_{sheet_name}_{timestamp}.png"
    sheet_path = sheet_dir / sheet_filename
    sheet.save(sheet_path)

    print(json.dumps({
        "success": True,
        "sheet_path": str(sheet_path),
        "sprite_count": len(images),
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

    file_path = output_dir / to_remove["path"]
    if file_path.exists():
        file_path.unlink()

    manifest["sprites"].remove(to_remove)
    save_manifest(output_dir, manifest)
    print(json.dumps({"success": True, "deleted": name}))


def cmd_organize(output_dir: Path):
    manifest = load_manifest(output_dir)
    original_count = len(manifest["sprites"])
    cleaned = [s for s in manifest["sprites"] if (output_dir / s["path"]).exists()]
    manifest["sprites"] = cleaned
    save_manifest(output_dir, manifest)
    print(json.dumps({"total": len(cleaned), "removed_orphans": original_count - len(cleaned)}))


async def cmd_sessions(output_dir: Path):
    """List all active sessions with their history.
    Automatically validates against Gemini's chat list and removes stale sessions."""
    session_names = list_sessions(output_dir)
    sessions = []
    removed = []

    # Build set of valid chat IDs from Gemini server
    valid_cids = None
    if session_names:
        try:
            client = await create_client(timeout=30)
            chats = client.list_chats()
            if chats is not None:
                valid_cids = {chat.cid for chat in chats}
            await client.close()
        except Exception:
            pass

    for name in session_names:
        data = load_session(output_dir, name)
        if not data:
            continue

        # Validate: check if the session's chat ID still exists on Gemini
        if valid_cids is not None and data.get("metadata"):
            meta = data["metadata"]
            # metadata[0] is the chat ID (cid)
            cid = meta[0] if meta and len(meta) > 0 else None
            if cid and cid not in valid_cids:
                delete_session(output_dir, name)
                removed.append(name)
                continue

        sessions.append({
            "name": name,
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "turns": len(data.get("history", [])),
            "history": data.get("history", []),
        })

    result = {"sessions": sessions}
    if removed:
        result["removed_stale"] = removed
    print(json.dumps(result, indent=2))


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
        print("  sprite_gen.py generate <desc> [--output-dir DIR] [--name N] [--category character] [--session NAME] [--files path1,path2]")
        print("  sprite_gen.py sheet <name> [--output-dir DIR] --frames '<json>' [--category character] [--session NAME]")
        print("  sprite_gen.py list [--output-dir DIR] [--category CAT]")
        print("  sprite_gen.py delete <name> [--output-dir DIR]")
        print("  sprite_gen.py organize [--output-dir DIR]")
        print("  sprite_gen.py sessions [--output-dir DIR]")
        print("  sprite_gen.py end-session <name> [--output-dir DIR]")
        print("  (default output-dir: ./sprites)")
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
        files_str = opts.get("files")
        files = files_str.split(",") if files_str else None
        await cmd_generate(
            output_dir=output_dir,
            description=sys.argv[2],
            name=opts.get("name"),
            category=opts.get("category", "character"),
            session_name=opts.get("session"),
            files=files,
        )

    elif command == "sheet":
        if len(sys.argv) < 3 or sys.argv[2].startswith("--"):
            print("Error: Please provide a sheet name.")
            return
        await cmd_sheet(
            output_dir=output_dir,
            sheet_name=sys.argv[2],
            frames_json=opts.get("frames", "[]"),
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
        await cmd_sessions(output_dir)

    elif command == "end-session":
        if len(sys.argv) < 3 or sys.argv[2].startswith("--"):
            print("Error: Please provide a session name.")
            return
        cmd_end_session(output_dir, sys.argv[2])

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
