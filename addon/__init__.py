"""
Forge — AI-powered Blender addon.

Lets users control a 3D scene with natural language commands routed through
a local FastAPI server backed by Claude.
"""
from __future__ import annotations

bl_info = {
    "name": "Forge",
    "author": "Forge Contributors",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Forge",
    "description": "Control your 3D scene with natural language via Claude AI",
    "category": "3D View",
}

from . import panel  # noqa: E402 — must come after bl_info


def register() -> None:
    panel.register()


def unregister() -> None:
    panel.unregister()
