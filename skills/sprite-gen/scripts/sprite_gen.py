"""
sprite_gen.py - 2D game sprite generator and manager using Gemini.
Uses gemini_webapi (Google Gemini subscription-based cookie/OAuth authentication).
Designed for portable use - all paths are passed as arguments.
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SUPPORTED_SIZES = [16, 32, 64, 128]
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
# Gemini client
# ---------------------------------------------------------------------------

async def create_client(timeout: int = 60) -> GeminiClient:
    """Create a Gemini client via browser cookie auto-extraction."""
    try:
        client = GeminiClient()
        await client.init(timeout=timeout, auto_close=False)
        return client
    except Exception as e:
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
                       size: int, category: str, quiet: bool = False) -> dict | None:
    """Generate a single sprite. Returns the result dict. Prints JSON unless quiet."""
    if size not in SUPPORTED_SIZES:
        result = {"success": False, "error": f"Unsupported size: {size}. Available: {SUPPORTED_SIZES}"}
        if not quiet:
            print(json.dumps(result))
        return result
    if category not in CATEGORIES:
        result = {"success": False, "error": f"Unsupported category: {category}. Available: {CATEGORIES}"}
        if not quiet:
            print(json.dumps(result))
        return result

    if not name:
        name = description.lower().replace(" ", "_")[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{category}_{name}_{size}px_{timestamp}.png"

    category_dir = output_dir / category
    category_dir.mkdir(parents=True, exist_ok=True)
    output_path = category_dir / filename

    client = await create_client()

    try:
        response = await client.generate_content(description)

        if not response.images:
            result = {
                "success": False,
                "error": "No image was generated. Try adjusting the prompt.",
                "gemini_response": response.text[:500] if response.text else None,
            }
            if not quiet:
                print(json.dumps(result))
            return result

        image = response.images[0]
        await image.save(path=str(category_dir), filename=filename)

        if Image and output_path.exists():
            img = Image.open(output_path)
            if img.size != (size, size):
                img = img.resize((size, size), Image.NEAREST)
                img.save(output_path)

        entry = {
            "name": name,
            "filename": filename,
            "path": str(output_path),
            "category": category,
            "size": size,
            "description": description,
            "created_at": datetime.now().isoformat(),
        }
        manifest = load_manifest(output_dir)
        manifest["sprites"].append(entry)
        save_manifest(output_dir, manifest)

        result = {"success": True, "entry": entry}
        if not quiet:
            print(json.dumps(result, indent=2))
        return result

    finally:
        await client.close()


async def cmd_sheet(output_dir: Path, sheet_name: str, frames_json: str,
                    size: int, category: str):
    """Generate multiple sprites and combine into a spritesheet."""
    if not Image:
        print(json.dumps({"success": False, "error": "Pillow is required."}))
        return

    frames = json.loads(frames_json)
    results = []
    for frame in frames:
        result = await cmd_generate(
            output_dir=output_dir,
            description=frame["description"],
            name=frame.get("name"),
            size=size, category=category,
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
    sheet_filename = f"sheet_{sheet_name}_{size}px_{timestamp}.png"
    sheet_path = sheet_dir / sheet_filename
    sheet.save(sheet_path)

    print(json.dumps({
        "success": True,
        "sheet_path": str(sheet_path),
        "sprite_count": cols,
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
        print("  sprite_gen.py generate <desc> --output-dir DIR [--name N] [--size 32] [--category character]")
        print("  sprite_gen.py sheet <name> --output-dir DIR --frames '<json>' [--size 32] [--category character]")
        print("  sprite_gen.py list --output-dir DIR [--category CAT]")
        print("  sprite_gen.py delete <name> --output-dir DIR")
        print("  sprite_gen.py organize --output-dir DIR")
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

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
