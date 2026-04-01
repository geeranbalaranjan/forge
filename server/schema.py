from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field


class AddObjectParams(BaseModel):
    type: Literal["cube", "sphere", "cylinder", "plane"]
    name: str | None = None
    location: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])


class AddObjectCommand(BaseModel):
    action: Literal["add_object"]
    parameters: AddObjectParams


class TransformParams(BaseModel):
    target: str
    location: list[float] | None = None
    rotation: list[float] | None = None
    scale: list[float] | None = None


class TransformCommand(BaseModel):
    action: Literal["transform"]
    parameters: TransformParams


class SetMaterialParams(BaseModel):
    target: str
    color: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])
    metallic: float = Field(default=0.0, ge=0.0, le=1.0)
    roughness: float = Field(default=0.5, ge=0.0, le=1.0)


class SetMaterialCommand(BaseModel):
    action: Literal["set_material"]
    parameters: SetMaterialParams


class DeleteObjectParams(BaseModel):
    target: str


class DeleteObjectCommand(BaseModel):
    action: Literal["delete_object"]
    parameters: DeleteObjectParams


class DuplicateObjectParams(BaseModel):
    target: str
    count: int = Field(default=1, ge=1)
    offset: list[float] = Field(default_factory=lambda: [1.0, 0.0, 0.0])


class DuplicateObjectCommand(BaseModel):
    action: Literal["duplicate_object"]
    parameters: DuplicateObjectParams


ForgeCommand = Annotated[
    Union[
        AddObjectCommand,
        TransformCommand,
        SetMaterialCommand,
        DeleteObjectCommand,
        DuplicateObjectCommand,
    ],
    Field(discriminator="action"),
]


class ForgeMultiCommand(BaseModel):
    steps: list[ForgeCommand]


class CommandRequest(BaseModel):
    prompt: str
    scene_state: list[dict[str, Any]] = Field(default_factory=list)
