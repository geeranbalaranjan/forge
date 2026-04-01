"""
panel.py — Forge N-panel UI.

Provides:
  - Text input for natural language commands
  - "Run" button that calls the FastAPI server and executes the result
  - Scrollable output log (last 10 commands)
  - "Start Server" button that launches main.py as a subprocess
"""
from __future__ import annotations

import os
import subprocess
import sys

import bpy
from bpy.props import StringProperty
from bpy.types import Context, Operator, Panel

from . import client, executor

# ---------------------------------------------------------------------------
# Module-level log (last 10 entries)
# ---------------------------------------------------------------------------

_LOG: list[str] = []
_MAX_LOG = 10
_server_process: subprocess.Popen | None = None  # type: ignore[type-arg]


def _log(entry: str) -> None:
    _LOG.append(entry)
    if len(_LOG) > _MAX_LOG:
        _LOG.pop(0)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class FORGE_OT_run_command(Operator):
    bl_idname = "forge.run_command"
    bl_label = "Run"
    bl_description = "Send the prompt to the Forge server and execute the result"

    def execute(self, context: Context) -> set[str]:
        props = context.scene.forge_props
        prompt = props.prompt.strip()
        if not prompt:
            self.report({"WARNING"}, "Prompt is empty.")
            return {"CANCELLED"}

        _log(f"> {prompt}")

        response = client.send_command(prompt)

        # Network / server error from client
        if "error" in response and "action" not in response and "steps" not in response:
            msg = response["error"]
            _log(f"  ERROR: {msg}")
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        # Multi-step command
        if "steps" in response:
            all_ok = True
            for i, step in enumerate(response["steps"], 1):
                result = executor.execute(step)
                if result.get("success"):
                    _log(f"  [{i}] OK: {result.get('message', 'Done.')}")
                else:
                    msg = result.get("error", "Unknown error.")
                    _log(f"  [{i}] FAIL: {msg}")
                    self.report({"ERROR"}, msg)
                    all_ok = False
                    break
            if all_ok:
                self.report({"INFO"}, f"Completed {len(response['steps'])} steps.")
        else:
            result = executor.execute(response)
            if result.get("success"):
                msg = result.get("message", "Done.")
                _log(f"  OK: {msg}")
                self.report({"INFO"}, msg)
            else:
                msg = result.get("error", "Unknown error.")
                _log(f"  FAIL: {msg}")
                self.report({"ERROR"}, msg)

        props.prompt = ""
        return {"FINISHED"}


class FORGE_OT_start_server(Operator):
    bl_idname = "forge.start_server"
    bl_label = "Start Server"
    bl_description = "Launch the Forge FastAPI server as a background process"

    def execute(self, context: Context) -> set[str]:
        global _server_process

        if _server_process is not None and _server_process.poll() is None:
            self.report({"INFO"}, "Server is already running.")
            return {"CANCELLED"}

        # Locate the server package relative to this addon directory.
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        forge_root = os.path.dirname(addon_dir)
        server_module = "server.main"

        try:
            _server_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    server_module + ":app",
                    "--host", "127.0.0.1",
                    "--port", "8000",
                ],
                cwd=forge_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _log("Server started (PID %d)." % _server_process.pid)
            self.report({"INFO"}, "Forge server started.")
        except FileNotFoundError:
            msg = "uvicorn not found. Install it with: pip install uvicorn"
            _log(f"  ERROR: {msg}")
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        except Exception as exc:
            _log(f"  ERROR: {exc}")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class ForgeProperties(bpy.types.PropertyGroup):
    prompt: StringProperty(  # type: ignore[assignment]
        name="",
        description="Natural language command for Forge",
        default="",
    )


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class FORGE_PT_main_panel(Panel):
    bl_label = "Forge AI"
    bl_idname = "FORGE_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forge"

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.forge_props

        # Server controls
        box = layout.box()
        box.label(text="Server", icon="NETWORK_DRIVE")
        box.operator("forge.start_server", icon="PLAY")

        layout.separator()

        # Command input
        layout.label(text="Command:")
        layout.prop(props, "prompt")
        layout.operator("forge.run_command", icon="PLAY")

        layout.separator()

        # Output log
        layout.label(text="Log (last %d):" % _MAX_LOG)
        log_box = layout.box()
        if _LOG:
            for line in _LOG:
                log_box.label(text=line)
        else:
            log_box.label(text="(no output yet)")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    ForgeProperties,
    FORGE_OT_run_command,
    FORGE_OT_start_server,
    FORGE_PT_main_panel,
)


def register() -> None:
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.forge_props = bpy.props.PointerProperty(type=ForgeProperties)


def unregister() -> None:
    del bpy.types.Scene.forge_props
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
