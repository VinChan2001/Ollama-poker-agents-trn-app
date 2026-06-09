# Ollama Poker Agents

A local Texas Hold'em simulator where five Ollama-backed AI agents play hands and tournaments on a retro pixel-art web table. The app runs fully on your machine and calls local Ollama models through `localhost:11434`.

## What It Does

- Runs a single poker hand or a full escalating-blind tournament.
- Streams game events live into a FastAPI-powered website.
- Shows each local model, stack size, cards, betting action, and reasoning dialogue.
- Uses five agent personalities mapped to local Ollama models.
- Includes a black pixel-table UI with animated seats, hover agent dossiers, event feed, and retro background music.

## Local Models

The default agents expect these local Ollama models:

| Agent | Model |
| --- | --- |
| Vin | `llama3.1:8b` |
| Sam | `qwen2.5:7b` |
| Kai | `mistral:7b` |
| Pap | `gemma2:9b` |
| Nik | `deepseek-r1:8b` |

You can change the model mapping in `tournament.py`.

## Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Start Ollama in another terminal if it is not already running:

```bash
ollama serve
```

Make sure the expected models are installed locally:

```bash
ollama list
```

Pull any missing model, for example:

```bash
ollama pull qwen2.5:7b
```

## Run The Website

From this repo:

```bash
python web_app.py
```

Open:

```text
http://127.0.0.1:8502
```

If the browser has cached old static files, hard refresh with `Cmd+Shift+R`.

## Controls

- `Single Hand`: runs one streamed hand.
- `Full Tournament`: runs tournament mode until one player wins or the max hand limit is hit.
- `Reveal Cards`: shows hole cards as they are available.
- `Music Off`: click once to start the retro loop. Browsers require a user gesture before audio can play.
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
web/             Static frontend assets
main.py          CLI tournament entry point
single_hand.py   CLI single-hand entry point
tournament.py    Agent setup and tournament/event orchestration
web_app.py       FastAPI app and SSE event stream
```

## Notes

This is for local simulation and study only. It uses virtual chips and does not involve real-money gambling.
