# Minimal Flask app

A single-route Flask app that displays “Hello from **MeomoLab**” at `/`.

## Install

From this folder, create and activate a virtual environment, then install the pinned dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

```bash
flask --app app run
```

Open <http://127.0.0.1:5000/> in your browser. Stop the server with `Ctrl+C`.
