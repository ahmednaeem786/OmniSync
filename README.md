# OmniSync

OmniSync syncs clipboard text between devices (Android ↔ Windows) via an HTTP endpoint + WebSocket relay.

## Project layout
- server.py — FastAPI server (HTTP POST + WebSocket broadcast)
- laptop_node/ — Windows client
  - main.py
  - os_tools/clipboard.py
- network/ — client helpers (api_client.py, ws_listener.py)
- android_node/ — Android app project

## Requirements
- Python 3.9+
- Install: python-dotenv, requests, websocket-client, pyperclip, fastapi, uvicorn

## Environment
Create g:\Python Projects\OmniSync\.env:
SERVER_URL="http://localhost:8000"
WS_URL="ws://localhost:8000/ws"
API_KEY="YourApiKeyHere"

## Setup (Windows)
PowerShell:
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install python-dotenv requests websocket-client pyperclip fastapi uvicorn

## Run server
py -m uvicorn server:app --reload --host 0.0.0.0 --port 8000

## Run laptop client
From project root:
py -m laptop_node.main
