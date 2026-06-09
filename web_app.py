import json
from pathlib import Path
from typing import Literal

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from tournament import (
    build_agents,
    run_single_hand_events,
    run_single_hand_events_live,
    run_tournament_events,
    run_tournament_events_live,
)


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="Ollama Poker Agents Website")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class RunRequest(BaseModel):
    run_mode: Literal["Single Hand", "Full Tournament"] = "Single Hand"
    starting_chips: int = Field(default=300, ge=100, le=5000)
    hands_per_level: int = Field(default=1, ge=1, le=10)
    max_hands: int = Field(default=12, ge=1, le=100)


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.post("/api/run")
def run_poker(request: RunRequest):
    try:
        if request.run_mode == "Single Hand":
            events = list(run_single_hand_events(starting_chips=request.starting_chips))
        else:
            events = list(
                run_tournament_events(
                    starting_chips=request.starting_chips,
                    hands_per_level=request.hands_per_level,
                    max_hands=request.max_hands,
                )
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"events": events}


@app.get("/api/models")
def ollama_models():
    agents = build_agents()
    expected_models = {
        name: getattr(agent, "model", "unknown")
        for name, agent in agents.items()
    }
    expected_personalities = {
        name: getattr(agent, "personality", "")
        for name, agent in agents.items()
    }

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        response.raise_for_status()
        data = response.json()
        installed_models = {
            model.get("name", "")
            for model in data.get("models", [])
        }
    except Exception as exc:
        return {
            "online": False,
            "error": str(exc),
            "players": [
                {
                    "name": name,
                    "model": model,
                    "personality": expected_personalities.get(name, ""),
                    "installed": False,
                }
                for name, model in expected_models.items()
            ],
        }

    return {
        "online": True,
        "players": [
            {
                "name": name,
                "model": model,
                "personality": expected_personalities.get(name, ""),
                "installed": model in installed_models,
            }
            for name, model in expected_models.items()
        ],
    }


@app.get("/api/events")
def stream_poker_events(
    run_mode: Literal["Single Hand", "Full Tournament"] = "Single Hand",
    starting_chips: int = 300,
    hands_per_level: int = 1,
    max_hands: int = 12,
):
    starting_chips = max(100, min(5000, int(starting_chips)))
    hands_per_level = max(1, min(10, int(hands_per_level)))
    max_hands = max(1, min(100, int(max_hands)))

    if run_mode == "Single Hand":
        event_iter = run_single_hand_events_live(starting_chips=starting_chips)
    else:
        event_iter = run_tournament_events_live(
            starting_chips=starting_chips,
            hands_per_level=hands_per_level,
            max_hands=max_hands,
        )

    def event_stream():
        for event in event_iter:
            yield f"data: {json.dumps(event)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run("web_app:app", host="127.0.0.1", port=8502, reload=False)
