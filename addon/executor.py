"""
executor.py — Maps JSON command dicts to bpy API calls.

Intentionally has NO imports from the server package. All bpy calls are
wrapped in try/except so a bad command can never crash Blender.
"""
from __future__ import annotations

import math
from typing import Any

try:
    import bpy
except ImportError:
    bpy = None  # type: ignore[assignment]  # allows unit-testing outside Blender

# Tracks the name of the most recently created/duplicated object so that
# handlers can resolve the "last" target keyword.
_last_object_name: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ok(message: str = "") -> dict[str, Any]:
    return {"success": True, "message": message}


def _err(message: str) -> dict[str, Any]:
    return {"success": False, "error": message}


def _resolve_target(target: str) -> Any:
    """Return the bpy object for *target*, resolving 'last' automatically."""
    if target == "last":
        if _last_object_name is None:
            raise KeyError("No object has been created yet (cannot resolve 'last').")
        target = _last_object_name
    obj = bpy.data.objects.get(target)
    if obj is None:
        # Case-insensitive fallback
        target_lower = target.lower()
        obj = next(
            (o for o in bpy.data.objects if o.name.lower() == target_lower), None
        )
    if obj is None:
        raise KeyError(f"Object '{target}' not found in scene.")
    return obj


def _deselect_all() -> None:
    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action="DESELECT")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_add_object(params: dict[str, Any]) -> dict[str, Any]:
    global _last_object_name
    try:
        obj_type: str = params["type"]
        location: list[float] = params.get("location", [0.0, 0.0, 0.0])
        scale: list[float] = params.get("scale", [1.0, 1.0, 1.0])
        name: str | None = params.get("name")

        _deselect_all()

        add_ops = {
            "cube": bpy.ops.mesh.primitive_cube_add,
            "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
            "cylinder": bpy.ops.mesh.primitive_cylinder_add,
            "plane": bpy.ops.mesh.primitive_plane_add,
        }
        if obj_type not in add_ops:
            return _err(f"Unknown object type: '{obj_type}'")

        add_ops[obj_type](location=tuple(location))

        obj = bpy.context.active_object
        if obj is None:
            return _err("Object was not created (no active object after add).")

        obj.scale = tuple(scale)

        if name:
            obj.name = name
            obj.data.name = name

        _last_object_name = obj.name
        return _ok(f"Added {obj_type} '{obj.name}' at {location}.")
    except Exception as exc:
        return _err(f"add_object failed: {exc}")


def handle_transform(params: dict[str, Any]) -> dict[str, Any]:
    try:
        target: str = params["target"]
        obj = _resolve_target(target)

        if "location" in params and params["location"] is not None:
            obj.location = tuple(params["location"])

        if "rotation" in params and params["rotation"] is not None:
            obj.rotation_euler = tuple(
                math.radians(d) for d in params["rotation"]
            )

        if "scale" in params and params["scale"] is not None:
            obj.scale = tuple(params["scale"])

        return _ok(f"Transformed '{obj.name}'.")
    except KeyError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(f"transform failed: {exc}")


def handle_set_material(params: dict[str, Any]) -> dict[str, Any]:
    try:
        target: str = params["target"]
        color: list[float] = params.get("color", [1.0, 1.0, 1.0])
        metallic: float = float(params.get("metallic", 0.0))
        roughness: float = float(params.get("roughness", 0.5))

        obj = _resolve_target(target)

        mat_name = f"ForgeMat_{obj.name}"
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(name=mat_name)

        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is None:
            return _err("Could not find Principled BSDF node in material.")

        r, g, b = color[0], color[1], color[2]
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness

        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

        return _ok(f"Set material on '{obj.name}' — color={color}.")
    except KeyError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(f"set_material failed: {exc}")


def handle_delete_object(params: dict[str, Any]) -> dict[str, Any]:
    global _last_object_name
    try:
        target: str = params["target"]
        obj = _resolve_target(target)
        name = obj.name

        _deselect_all()
        obj.select_set(True)
        bpy.ops.object.delete()

        if _last_object_name == name:
            _last_object_name = None

        return _ok(f"Deleted '{name}'.")
    except KeyError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(f"delete_object failed: {exc}")


def handle_duplicate_object(params: dict[str, Any]) -> dict[str, Any]:
    global _last_object_name
    try:
        target: str = params["target"]
        count: int = int(params.get("count", 1))
        offset: list[float] = params.get("offset", [1.0, 0.0, 0.0])

        src = _resolve_target(target)
        names: list[str] = []

        for i in range(count):
            _deselect_all()
            src.select_set(True)
            bpy.context.view_layer.objects.active = src
            bpy.ops.object.duplicate()

            dup = bpy.context.active_object
            if dup is None:
                return _err(f"Duplication {i + 1} failed (no active object).")

            dup.location = (
                src.location[0] + offset[0] * (i + 1),
                src.location[1] + offset[1] * (i + 1),
                src.location[2] + offset[2] * (i + 1),
            )
            names.append(dup.name)
            _last_object_name = dup.name

        return _ok(f"Duplicated '{src.name}' {count}× → {names}.")
    except KeyError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(f"duplicate_object failed: {exc}")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_HANDLERS = {
    "add_object": handle_add_object,
    "transform": handle_transform,
    "set_material": handle_set_material,
    "delete_object": handle_delete_object,
    "duplicate_object": handle_duplicate_object,
}


def execute(command: dict[str, Any]) -> dict[str, Any]:
    """
    Dispatch a command dict to the appropriate handler.

    Expected shape: {"action": "<name>", "parameters": {...}}
    Returns: {"success": bool, ...}
    """
    action = command.get("action", "")
    handler = _HANDLERS.get(action)
    if handler is None:
        return _err(f"Unknown action: '{action}'")
    return handler(command.get("parameters", {}))
