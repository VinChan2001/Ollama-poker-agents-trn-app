# Ollama Poker Agents

A local Texas Hold'em simulator where five Ollama-backed AI agents play hands and tournaments on a retro pixel-art web table. The app runs fully on your machine and calls local Ollama models through `localhost:11434`.

## What It Does

- Runs a single poker hand in the website. Tournament code is still available for CLI/local experiments.
- Streams game events live into a FastAPI-powered website.
- Shows each local model, stack size, cards, betting action, and reasoning dialogue.
- Uses five agent personalities mapped to local Ollama models.
- Includes a pixel-table UI with animated seats, hover agent dossiers, event feed, and retro background music.

## How It Works

Each agent is backed by a local Ollama model. On every decision, the agent receives a structured prompt with its private cards, the community cards, pot size, call amount, stack sizes, and a strategic hint computed from the hand evaluator. The model returns a JSON action (`fold`, `check`, `call`, `bet`, or `raise`) with a natural-language reason. The FastAPI backend streams these events over SSE to the browser frontend.

## Prerequisites

- **Python 3.10+**
- **Ollama** — install from [ollama.com](https://ollama.com) and make sure the CLI is on your PATH.

## Agents and Models

| Agent | Model | Personality |
| --- | --- | --- |
| Vin | `llama3.1:8b` | Table bully — loud, fearless, applies pressure, occasional bluffs |
| Sam | `qwen2.5:7b` | Math grinder — tight, pot-odds focused, snap-calls when price is right |
| Kai | `mistral:7b` | Smooth casino pro — calm, balanced, mixes value bets and traps |
| Pap | `gemma2:9b` | Chaos merchant — plays weird hands, loves flops, unpredictable |
| Nik | `deepseek-r1:8b` | Silent assassin — patient, waits for leverage, attacks weakness |

You can change the model mapping in `tournament.py`.

## Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Start Ollama in a separate terminal if it is not already running:

```bash
ollama serve
```

Pull the expected models if you do not already have them:

```bash
ollama pull llama3.1:8b
ollama pull qwen2.5:7b
ollama pull mistral:7b
ollama pull gemma2:9b
ollama pull deepseek-r1:8b
```

Verify they are available:

```bash
ollama list
```

## Run The Website

```bash
python web_app.py
```

Open in your browser:

```text
http://127.0.0.1:8502
```

If the browser has cached old static files, hard refresh with `Cmd+Shift+R`.

## Controls

- **Single Hand** — runs one streamed hand.
- **Full Tournament** — disabled in the website; clicking it shows the laptop takeoff warning and keeps Single Hand selected.
- **Reveal Cards** — shows hole cards as they become available.
- **Music Off** — click once to start the retro loop. Browsers require a user gesture before audio can play.
- Hover or focus an agent card to see its personality dossier.

## CLI Mode

Run a tournament in the terminal:

```bash
python main.py
```

Run a single hand in the terminal:

```bash
python single_hand.py
```

## Project Structure

```text
agents/          Ollama and fallback agent interfaces
poker/           Texas Hold'em engine, game state, cards, and hand evaluation
web/             Static frontend assets (HTML, CSS, JS)
main.py          CLI tournament entry point
single_hand.py   CLI single-hand entry point
tournament.py    Agent setup, blind levels, and event orchestration
web_app.py       FastAPI app and SSE event stream
```

## Notes

This is for local simulation and study only. It uses virtual chips and does not involve real-money gambling. Response speed depends on your hardware — models with GPU acceleration will act significantly faster than CPU-only inference.
