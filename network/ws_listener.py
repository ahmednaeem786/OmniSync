import json
import os
import socket
from pathlib import Path


import websocket
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

"""
Job: It is completely responsible for pulling data down from the cloud.

Rules: You give this class a reference to your ClipboardManager. 
It opens the permanent WebSocket tunnel and goes to sleep. 
When the cloud shouts a new copied text down the tunnel, this class catches it and immediately tells the ClipboardManager to paste it.
"""

class CloudListener:
    
    def __init__(self, clipboard_manager):
        self.clipboard = clipboard_manager
        self.headers = [f"Authorization: Bearer {os.getenv('API_KEY')}"]

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            text = data.get("text")
            device = data.get("device")

            if text and device != socket.gethostname():
                print(f"\n[WEBSOCKET] Recieved live clipboard data from the cloud: {text}")
                self.clipboard.write_from_android(text)
        
        except Exception as e:
            print(f"[WEBSOCKET] Error processing message: {e}")

    def _on_error(self, ws, error):
        print(f"[WEBSOCKET] Tunnel Error: {error}")

    def start(self):

        print(f"Opening secure WebSocket tunnel to {os.getenv('WS_URL')}")

        ws = websocket.WebSocketApp(
            os.getenv('WS_URL'),
            header=self.headers,
            on_message=self._on_message,
            on_error=self._on_error
        )

        ws.run_forever()