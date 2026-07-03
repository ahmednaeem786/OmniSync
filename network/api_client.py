import requests
import socket
import os
from dotenv import load_dotenv

load_dotenv()


"""
Job: It is completely responsible for pushing data up to the cloud.

Rules: When main.py gives it a string of text, this class packages it into a JSON envelope, 
attaches your API Key, and drops it off at the FastAPI HTTP endpoint using the requests library. 
If the internet drops, this class handles the error gracefully.
"""

class CloudAPI:
    def __init__(self):

        self.headers = {
            "Authorization": f"Bearer {os.getenv('API_KEY')}",
            "Content-Type": "application/json"
        }

        self.endpoint = f"{os.getenv('SERVER_URL')}/api/clipboard"

    def send_clipboard_data(self, text):

        payload = {
            "text": text,
            "device": socket.gethostname()
        }

        try:
            response = requests.post(self.endpoint, json=payload, headers=self.headers, timeout=5)

            if response.status_code == 200:
                print("[API Client] Successfully sent clipboard data to the cloud.")
                return True
            else:
                print(f"[API Client] Failed to send clipboard data. Status code: {response.status_code}, Response: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"[API Client] Error reaching cloud server: {e}")
            return False