from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schema import CommandRequest, ForgeMultiCommand
from .translator import translate

app = FastAPI(title="Forge", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/command", response_model=None)
def command(request: CommandRequest) -> dict:
    try:
        result = translate(request.prompt, request.scene_state)
    except EnvironmentError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if isinstance(result, ForgeMultiCommand):
        return {"steps": [step.model_dump() for step in result.steps]}
    return result.model_dump()
