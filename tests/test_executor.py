"""
Unit tests for addon/executor.py.

bpy is mocked so these run outside Blender with plain pytest.
"""
from __future__ import annotations

import importlib
import math
import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Build a minimal bpy mock before importing executor
# ---------------------------------------------------------------------------

def _make_bpy_mock() -> MagicMock:
    bpy = MagicMock(name="bpy")

    # --- bpy.ops.mesh ---
    mesh_ops = MagicMock()
    mesh_ops.primitive_cube_add = MagicMock(return_value={"FINISHED"})
    mesh_ops.primitive_uv_sphere_add = MagicMock(return_value={"FINISHED"})
    mesh_ops.primitive_cylinder_add = MagicMock(return_value={"FINISHED"})
    mesh_ops.primitive_plane_add = MagicMock(return_value={"FINISHED"})
    bpy.ops.mesh = mesh_ops

    # --- bpy.ops.object ---
    obj_ops = MagicMock()
    obj_ops.select_all = MagicMock(return_value={"FINISHED"})
    obj_ops.select_all.poll = MagicMock(return_value=True)
    obj_ops.delete = MagicMock(return_value={"FINISHED"})
    obj_ops.duplicate = MagicMock(return_value={"FINISHED"})
    bpy.ops.object = obj_ops

    # --- active object returned after add/duplicate ---
    active_obj = MagicMock()
    active_obj.name = "Cube"
    active_obj.location = [0.0, 0.0, 0.0]
    active_obj.scale = [1.0, 1.0, 1.0]
    active_obj.rotation_euler = [0.0, 0.0, 0.0]
    active_obj.data = MagicMock()
    active_obj.data.materials = []
    active_obj.data.name = "Cube"

    bpy.context.active_object = active_obj
    bpy.context.view_layer = MagicMock()

    # --- bpy.data.objects ---
    objects_store: dict[str, MagicMock] = {"Cube": active_obj}

    def _objects_get(name: str) -> MagicMock | None:
        return objects_store.get(name)

    bpy.data.objects.get = _objects_get

    # --- bpy.data.materials ---
    materials_store: dict[str, MagicMock] = {}

    def _mats_get(name: str) -> MagicMock | None:
        return materials_store.get(name)

    def _mats_new(name: str) -> MagicMock:
        mat = MagicMock()
        mat.name = name
        mat.use_nodes = False
        bsdf = MagicMock()
        bsdf.inputs = {
            "Base Color": MagicMock(),
            "Metallic": MagicMock(),
            "Roughness": MagicMock(),
        }
        mat.node_tree = MagicMock()
        mat.node_tree.nodes.get = MagicMock(return_value=bsdf)
        materials_store[name] = mat
        return mat

    bpy.data.materials.get = _mats_get
    bpy.data.materials.new = _mats_new

    return bpy


# ---------------------------------------------------------------------------
# Fixture: patch bpy and (re)import executor fresh each test
# ---------------------------------------------------------------------------

@pytest.fixture()
def bpy_mock() -> MagicMock:
    mock = _make_bpy_mock()
    sys.modules["bpy"] = mock
    # Force a fresh import of executor so module-level `bpy` binding is current.
    if "addon.executor" in sys.modules:
        del sys.modules["addon.executor"]
    # Also remove any cached top-level executor import
    for key in list(sys.modules.keys()):
        if "executor" in key:
            del sys.modules[key]
    return mock


@pytest.fixture()
def executor(bpy_mock: MagicMock):  # noqa: F811
    # Add forge root to path so `from addon import executor` works
    import os
    forge_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if forge_root not in sys.path:
        sys.path.insert(0, forge_root)

    spec = importlib.util.spec_from_file_location(
        "executor",
        os.path.join(forge_root, "addon", "executor.py"),
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    # Reset module state
    mod._last_object_name = None
    return mod


# ---------------------------------------------------------------------------
# add_object
# ---------------------------------------------------------------------------

class TestHandleAddObject:
    def test_add_cube_success(self, executor: Any, bpy_mock: MagicMock) -> None:
        result = executor.handle_add_object(
            {"type": "cube", "location": [1.0, 2.0, 3.0], "scale": [1.0, 1.0, 1.0]}
        )
        assert result["success"] is True
        bpy_mock.ops.mesh.primitive_cube_add.assert_called_once()

    def test_add_sphere(self, executor: Any, bpy_mock: MagicMock) -> None:
        result = executor.handle_add_object({"type": "sphere"})
        assert result["success"] is True
        bpy_mock.ops.mesh.primitive_uv_sphere_add.assert_called_once()

    def test_add_cylinder(self, executor: Any, bpy_mock: MagicMock) -> None:
        result = executor.handle_add_object({"type": "cylinder"})
        assert result["success"] is True

    def test_add_plane(self, executor: Any, bpy_mock: MagicMock) -> None:
        result = executor.handle_add_object({"type": "plane"})
        assert result["success"] is True

    def test_unknown_type_returns_error(self, executor: Any) -> None:
        result = executor.handle_add_object({"type": "torus"})
        assert result["success"] is False
        assert "torus" in result["error"]

    def test_sets_last_object_name(self, executor: Any, bpy_mock: MagicMock) -> None:
        executor.handle_add_object({"type": "cube"})
        assert executor._last_object_name == bpy_mock.context.active_object.name

    def test_custom_name_applied(self, executor: Any, bpy_mock: MagicMock) -> None:
        executor.handle_add_object({"type": "cube", "name": "MyCube"})
        bpy_mock.context.active_object.name == "MyCube"

    def test_no_active_object_returns_error(
        self, executor: Any, bpy_mock: MagicMock
    ) -> None:
        bpy_mock.context.active_object = None
        result = executor.handle_add_object({"type": "cube"})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# transform
# ---------------------------------------------------------------------------

class TestHandleTransform:
    def test_transform_location(self, executor: Any, bpy_mock: MagicMock) -> None:
        result = executor.handle_transform(
            {"target": "Cube", "location": [5.0, 0.0, 0.0]}
        )
        assert result["success"] is True
        assert bpy_mock.data.objects.get("Cube").location == (5.0, 0.0, 0.0)

    def test_transform_rotation_converts_degrees(
        self, executor: Any, bpy_mock: MagicMock
    ) -> None:
        result = executor.handle_transform(
            {"target": "Cube", "rotation": [90.0, 0.0, 0.0]}
        )
        assert result["success"] is True
        obj = bpy_mock.data.objects.get("Cube")
        # rotation_euler was set via tuple assignment
        expected = tuple(math.radians(d) for d in [90.0, 0.0, 0.0])
        obj.rotation_euler == expected

    def test_transform_missing_object(self, executor: Any) -> None:
        result = executor.handle_transform(
            {"target": "DoesNotExist", "location": [0, 0, 0]}
        )
        assert result["success"] is False
        assert "DoesNotExist" in result["error"]

    def test_transform_last_resolves(
        self, executor: Any, bpy_mock: MagicMock
    ) -> None:
        executor._last_object_name = "Cube"
        result = executor.handle_transform({"target": "last", "scale": [2.0, 2.0, 2.0]})
        assert result["success"] is True

    def test_transform_last_no_object_yet(self, executor: Any) -> None:
        executor._last_object_name = None
        result = executor.handle_transform({"target": "last", "location": [0, 0, 0]})
        assert result["success"] is False
        assert "last" in result["error"].lower() or "No object" in result["error"]


# ---------------------------------------------------------------------------
# set_material
# ---------------------------------------------------------------------------

class TestHandleSetMaterial:
    def test_set_material_success(self, executor: Any, bpy_mock: MagicMock) -> None:
        result = executor.handle_set_material(
            {"target": "Cube", "color": [1.0, 0.0, 0.0], "metallic": 0.0, "roughness": 0.5}
        )
        assert result["success"] is True

    def test_set_material_missing_object(self, executor: Any) -> None:
        result = executor.handle_set_material(
            {"target": "Ghost", "color": [1.0, 1.0, 1.0]}
        )
        assert result["success"] is False

    def test_set_material_no_bsdf_node(
        self, executor: Any, bpy_mock: MagicMock
    ) -> None:
        # Simulate a material with no BSDF node
        bad_mat = MagicMock()
        bad_mat.node_tree = MagicMock()
        bad_mat.node_tree.nodes.get = MagicMock(return_value=None)
        bpy_mock.data.materials.new = MagicMock(return_value=bad_mat)
        result = executor.handle_set_material(
            {"target": "Cube", "color": [0.5, 0.5, 0.5]}
        )
        assert result["success"] is False
        assert "Principled BSDF" in result["error"]


# ---------------------------------------------------------------------------
# delete_object
# ---------------------------------------------------------------------------

class TestHandleDeleteObject:
    def test_delete_success(self, executor: Any, bpy_mock: MagicMock) -> None:
        executor._last_object_name = "Cube"
        result = executor.handle_delete_object({"target": "Cube"})
        assert result["success"] is True
        bpy_mock.ops.object.delete.assert_called_once()

    def test_delete_clears_last(self, executor: Any, bpy_mock: MagicMock) -> None:
        executor._last_object_name = "Cube"
        executor.handle_delete_object({"target": "Cube"})
        assert executor._last_object_name is None

    def test_delete_missing_object(self, executor: Any) -> None:
        result = executor.handle_delete_object({"target": "Phantom"})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# duplicate_object
# ---------------------------------------------------------------------------

class TestHandleDuplicateObject:
    def test_duplicate_success(self, executor: Any, bpy_mock: MagicMock) -> None:
        result = executor.handle_duplicate_object(
            {"target": "Cube", "count": 2, "offset": [1.0, 0.0, 0.0]}
        )
        assert result["success"] is True
        assert bpy_mock.ops.object.duplicate.call_count == 2

    def test_duplicate_missing_object(self, executor: Any) -> None:
        result = executor.handle_duplicate_object({"target": "Void", "count": 1})
        assert result["success"] is False

    def test_duplicate_updates_last(
        self, executor: Any, bpy_mock: MagicMock
    ) -> None:
        executor.handle_duplicate_object(
            {"target": "Cube", "count": 1, "offset": [1.0, 0.0, 0.0]}
        )
        assert executor._last_object_name is not None


# ---------------------------------------------------------------------------
# Top-level dispatcher
# ---------------------------------------------------------------------------

class TestExecuteDispatcher:
    def test_unknown_action(self, executor: Any) -> None:
        result = executor.execute({"action": "fly", "parameters": {}})
        assert result["success"] is False
        assert "fly" in result["error"]

    def test_missing_action(self, executor: Any) -> None:
        result = executor.execute({})
        assert result["success"] is False

    def test_dispatches_add_object(
        self, executor: Any, bpy_mock: MagicMock
    ) -> None:
        result = executor.execute(
            {"action": "add_object", "parameters": {"type": "plane"}}
        )
        assert result["success"] is True
