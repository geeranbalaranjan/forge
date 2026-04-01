"""
client.py — Thin HTTP client for the Forge FastAPI server.

Uses only stdlib urllib so it works inside Blender's sandboxed Python
(no pip installs required).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

try:
    import bpy
except ImportError:
    bpy = None  # type: ignore[assignment]

SERVER_URL = "http://localhost:8000"


def _collect_scene_state() -> list[dict[str, Any]]:
    if bpy is None:
        return []
    return [
        {
            "name": obj.name,
            "type": obj.type,
            "location": [round(v, 3) for v in obj.location],
            "scale": [round(v, 3) for v in obj.scale],
        }
        for obj in bpy.data.objects
    ]


def send_command(prompt: str) -> dict[str, Any]:
    """
    POST {"prompt": prompt, "scene_state": [...]} to /command.

    Returns the parsed JSON response dict, or a dict with
    {"success": False, "error": "<message>"} on failure.
    """
    payload = json.dumps({
        "prompt": prompt,
        "scene_state": _collect_scene_state(),
    }).encode("utf-8")

    req = urllib.request.Request(
        url=f"{SERVER_URL}/command",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode())
        except Exception:
            detail = exc.reason
        return {"success": False, "error": f"Server error {exc.code}: {detail}"}
    except urllib.error.URLError as exc:
        reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
        return {
            "success": False,
            "error": (
                f"Could not reach Forge server at {SERVER_URL}. "
                f"Is it running? ({reason})"
            ),
        }
    except Exception as exc:
        return {"success": False, "error": f"Unexpected error: {exc}"}


def check_health() -> bool:
    """Return True if the server is reachable and healthy."""
    try:
        with urllib.request.urlopen(f"{SERVER_URL}/health", timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data.get("status") == "ok"
    except Exception:
        return False
