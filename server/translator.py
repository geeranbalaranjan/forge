from __future__ import annotations

import json
import logging
import os
from typing import Any

import openai

log = logging.getLogger(__name__)
from pydantic import TypeAdapter, ValidationError

from .schema import ForgeCommand, ForgeMultiCommand

_SCHEMA_DESCRIPTION = """
Single-action commands (respond with one object):

1. add_object
{"action": "add_object", "parameters": {"type": "cube"|"sphere"|"cylinder"|"plane", "name": "<string, optional>", "location": [x,y,z], "scale": [x,y,z]}}

2. transform
{"action": "transform", "parameters": {"target": "<name or 'last'>", "location": [x,y,z], "rotation": [x,y,z], "scale": [x,y,z]}}
(location, rotation, scale are all optional — only include what changes)

3. set_material
{"action": "set_material", "parameters": {"target": "<name or 'last'>", "color": [r,g,b], "metallic": <0-1>, "roughness": <0-1>}}

4. delete_object
{"action": "delete_object", "parameters": {"target": "<name or 'last'>"}}

5. duplicate_object
{"action": "duplicate_object", "parameters": {"target": "<name or 'last'>", "count": <int>, "offset": [x,y,z]}}

Multi-action commands (respond with a steps array):
{"steps": [<ForgeCommand>, <ForgeCommand>, ...]}
"""

# Rolling conversation history — last 5 exchanges (10 messages)
_history: list[dict[str, str]] = []

_command_adapter: TypeAdapter[ForgeCommand] = TypeAdapter(ForgeCommand)


def _build_system_prompt(scene_state: list[dict[str, Any]]) -> str:
    if scene_state:
        scene_str = json.dumps(scene_state, separators=(",", ":"))
    else:
        scene_str = "[]"

    return (
        "You are a 3D scene command translator for Blender.\n\n"
        f"Current scene objects: {scene_str}\n\n"
        "The user will describe what they want in natural language. "
        "You must respond ONLY with a valid JSON object — no explanation, no markdown, no code fences.\n\n"
        "For a single action, respond with one ForgeCommand object.\n"
        "For multiple actions (e.g. 'create 5 cubes in a row and make them all blue'), respond with:\n"
        '{"steps": [<ForgeCommand>, ...]}\n\n'
        "Rules:\n"
        "- Always use exact object names from the current scene list, including capitalisation.\n"
        "- Use 'last' as the target only when the scene is empty and no object exists yet.\n"
        "- Location units are Blender units. Rotation values are in degrees.\n"
        "- Color values are 0–1 RGB floats — NEVER 0–255. Example: red=[1,0,0], blue=[0,0,1], green=[0,1,0].\n"
        "- duplicate_object requires an existing object in the scene. If no suitable source exists, use multiple add_object steps instead.\n"
        "- When the user asks to create multiple objects (e.g. '3 spheres in a row'), always use a steps array with one add_object per object at different locations.\n"
        "- When the user says 'all', 'every', or refers to multiple objects by type (e.g. 'make all the spheres blue'), use a steps array with one command per matching object from the scene list.\n\n"
        "Available command schemas:\n"
        + _SCHEMA_DESCRIPTION
        + "\nNever respond with anything other than the JSON."
    )


def translate(
    prompt: str, scene_state: list[dict[str, Any]]
) -> ForgeCommand | ForgeMultiCommand:
    """Translate a natural language prompt into a validated ForgeCommand or ForgeMultiCommand."""
    global _history

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")

    client = openai.OpenAI(api_key=api_key)

    messages: list[dict[str, str]] = (
        [{"role": "system", "content": _build_system_prompt(scene_state)}]
        + _history[-10:]
        + [{"role": "user", "content": prompt}]
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=messages,
    )

    raw = response.choices[0].message.content.strip()
    log.info("GPT raw response: %s", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAI returned non-JSON output: {raw!r}") from exc

    # Multi-command path
    if "steps" in data:
        try:
            command = ForgeMultiCommand.model_validate(data)
        except ValidationError as exc:
            raise ValueError(
                f"OpenAI multi-command response failed validation.\n"
                f"Raw: {raw}\nError: {exc}"
            ) from exc
    else:
        try:
            command = _command_adapter.validate_python(data)
        except ValidationError as exc:
            raise ValueError(
                f"OpenAI response did not match any known command schema.\n"
                f"Raw: {raw}\nError: {exc}"
            ) from exc

    # Update rolling history
    _history.append({"role": "user", "content": prompt})
    _history.append({"role": "assistant", "content": raw})
    if len(_history) > 10:
        _history = _history[-10:]

    return command
