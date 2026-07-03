import os
import time
from dotenv import load_dotenv
from core.crypto import CryptoEngine
from core.signaling import DweetClient
from core.network import SecureTunnel
from core.clipboard import ClipboardManager

load_dotenv()

SYNC_CHANNEL = os.getenv("OMNISYNC_CHANNEL", "omnisync-default-fallback-channel")

SIGNALING_SERVER = os.getenv("SIGNALING_SERVER", "https://dweet.cc")

MY_ROLE = "laptop"
TARGET_ROLE = "android" # bubye apple, sorry you're too restrictive atp :((((( i tried my best but not worth the headache of dealing with a swift app :( cya

PORT = 53317

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

    print("-----Starting a OmniSync Node-----")

    crypto = CryptoEngine()
    signaler = DweetClient("omnisync-default-fallback-channel", "laptop", "android")
    network = SecureTunnel(53317)
    clipboard = ClipboardManager()

    print(f"My Local IP: {network.local_ip}")

    signaler.broadcast_presence(network.local_ip, crypto.public_key_base64)
    
    target_ip, target_public_key = signaler.listen_for_target()

    crypto.derive_shared_key(target_public_key)

    client_socket, encrypted_bytes = network.await_android_handshake()

    if not client_socket:
        raise ConnectionError("Failed to establish handshake with Android device. Restarting Handshake")

    try:
        decrypted_message = crypto.decrypt_payload(encrypted_bytes)

        if decrypted_message == "READY":
            print("Android is Perfectly Synced!")

            encrypted_ack = crypto.encrypt_payload("SYNC_ACK")
            network.reply_to_handshake(client_socket, encrypted_ack)
    except Exception as e:
        raise ValueError(f"Communication Intercepted: {e}.")

    print("\n---    TUNNEL LOCKED. MONITORING CLIPBOARD     ---")

    while True:
        try:

            new_text = clipboard.get_new_text()

            if new_text:
                print(f"New Clipboard text detected: {new_text[:15]}...")

                encrypted_data = crypto.encrypt_payload(new_text)

                network.send_payload(target_ip, encrypted_data)
        except Exception as e:
            print(f"[ERROR] Main loop crashed: {e}")
        
        time.sleep(1.5)


if __name__ == "__main__":
    main()