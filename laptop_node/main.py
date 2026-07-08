import time
import threading
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from network.api_client import CloudAPI  # noqa: E402
from os_tools.clipboard import ClipboardManager  # noqa: E402
from network.ws_listener import CloudListener  # noqa: E402


# def init_db():
#     """
#     Creates the local SQLite database to store clipboard history.
#     """
#     conn = sqlite3.connect('clipboard_history.db')
#     cursor = conn.cursor()
#     cursor.execute('''
#                    CREATE TABLE IF NOT EXISTS clipboard_history (
#                    id INTEGER PRIMARY KEY AUTOINCREMENT,
#                    content TEXT NOT NULL,
#                    source_device TEXT NOT NULL,
#                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
#                    ''')
#     conn.commit()
#     conn.close()

# def save_to_db(content, source_device):
#     """
#     Saves a new clipboard item into the database
#     """
#     try:
#         conn = sqlite3.connect('clipboard_history.db')
#         cursor = conn.cursor()
#         cursor.execute('''
#                        INSERT INTO clipboard_history (content, source_device)
#                        VALUES (?, ?)
#                        ''', (content, source_device))
#         conn.commit()
#         conn.close()
#         print(f"Logged New Item from {source_device}")
#     except Exception as e:
#         print(f"Database Error: {e}")

def main():

    print("-----Starting a OmniSync Cloud Node-----")

    clipboard = ClipboardManager()
    api_client = CloudAPI()
    ws_listener = CloudListener(clipboard)

    threading.Thread(target=ws_listener.start, daemon=True).start()

    print("---Connected to Cloud. Monitoring Clipboard")

    while True:
        try:
            new_text = clipboard.get_new_text()

            if new_text:
                print(f"\n[LAPTOP] Copied new text: {new_text}")

                api_client.send_clipboard_data(new_text)

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"[LAPTOP] Error: {e}")

        time.sleep(2)

if __name__ == "__main__":
    main()