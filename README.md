# Forge

AI-powered Blender addon — control your 3D scene with natural language.

```
"create a red cube at the origin"  →  Claude  →  JSON  →  bpy  →  cube appears
```

---

## Project structure

```
forge/
├── addon/          # Blender addon (pure stdlib, no pip inside Blender)
│   ├── __init__.py
│   ├── panel.py    # N-panel UI
│   ├── executor.py # JSON → bpy calls
│   └── client.py   # urllib HTTP client
├── server/         # FastAPI server (runs outside Blender)
│   ├── main.py
│   ├── translator.py
│   └── schema.py
├── tests/
│   └── test_executor.py
├── requirements.txt
└── README.md
```

---

## 1 — Install the server dependencies

```bash
cd forge
pip install -r requirements.txt
```

Set your Anthropic API key:

```bash
# Linux / macOS
export ANTHROPIC_API_KEY=sk-ant-...

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

---

## 2 — Start the FastAPI server

Run from the **forge/** root (so the `server` package is importable):

```bash
uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Verify it's up:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## 3 — Install the Blender addon

1. Zip the `addon/` folder:
   ```bash
   # from forge/
   zip -r forge_addon.zip addon/
   ```
2. In Blender: **Edit → Preferences → Add-ons → Install…**
3. Select `forge_addon.zip` and enable **Forge**.
4. Open the **N-panel** (press `N` in the 3D viewport) and click the **Forge** tab.

> The server must be running before you click **Run**.  
> Alternatively, click **Start Server** inside the panel to launch it automatically
> (requires `uvicorn` and the `server` package to be on the system Python path).

---

## 4 — Run the tests

```bash
# from forge/
pip install pytest
pytest tests/
```

Tests mock `bpy` so they run without Blender installed.

---

## 5 — Example commands to try

| Natural language | What Forge does |
|---|---|
| `create a red cube` | Adds a cube and sets a red material |
| `add a sphere at 2 3 0` | Adds a UV sphere at (2, 3, 0) |
| `move the last object up by 2` | Translates the last-created object on Z |
| `rotate Cube 45 degrees on Z` | Sets Cube's Z rotation to 45° |
| `make it shiny and metallic` | Sets high metallic / low roughness on last object |
| `duplicate the cube 3 times offset by 2 on X` | Creates 3 copies along X |
| `delete Sphere` | Removes the object named Sphere |

---

## Architecture

```
[Blender panel]
      │  prompt: str
      ▼
addon/client.py  ── POST /command ──►  server/main.py
                                             │
                                             ▼
                                     server/translator.py
                                             │  Claude API
                                             ▼
                                       ForgeCommand (JSON)
                                             │
                                    ◄── response ────────
      │
      ▼
addon/executor.py  ──►  bpy API  ──►  scene updated
```

Claude is instructed to respond **only** with a single JSON object. The server
validates it with Pydantic before returning it to the addon. The executor maps
it to `bpy` calls inside Blender.
