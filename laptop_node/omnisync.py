import os
import time
import socket
import requests
import threading
import pyperclip
import sqlite3
from dotenv import load_dotenv
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from datetime import datetime

load_dotenv()

SYNC_CHANNEL = os.getenv("OMNISYNC_CHANNEL", "omnisync-default-fallback-channel")
SIGNALING_SERVER = os.getenv("SIGNALING_SERVER", "https://dweet.cc")
MY_ROLE = "laptop"
TARGET_ROLE = "android" # bubye apple, sorry you're too restrictive atp :((((( i tried my best but not worth the headache of dealing with a swift app :( cya

PORT = 53317

def init_db():
    """
    Creates the local SQLite database to store clipboard history.
    """
    conn = sqlite3.connect('clipboard_history.db')
    cursor = conn.cursor()
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS clipboard_history (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   content TEXT NOT NULL,
                   source_device TEXT NOT NULL,
                   timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
                   ''')
    conn.commit()
    conn.close()

def save_to_db(content, source_device):
    """
    Saves a new clipboard item into the database
    """
    try:
        conn = sqlite3.connect('clipboard_history.db')
        cursor = conn.cursor()
        cursor.execute('''
                       INSERT INTO clipboard_history (content, source_device)
                       VALUES (?, ?)
                       ''', (content, source_device))
        conn.commit()
        conn.close()
        print(f"Logged New Item from {source_device}")
    except Exception as e:
        print(f"Database Error: {e}")

def get_local_ip():
    """
    Bypasses local routing to find actual LAN IP address.
    """

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def generate_keypair():
    """
    Generates an ephemeral X25519 Elliptic Curve keypair.
    """

    private_key = ec.generate_private_key(ec.SECP384R1())
    public_key = private_key.public_key()

    public_bytes = public_key.public_bytes(
        encoding = serialization.Encoding.PEM,
        format = serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return private_key, public_bytes.decode('utf-8')

def broadcast_presence(local_ip, public_key):
    """
    Sends the IP and Public Key to the signaling server.
    """

    payload = {
        "ip": local_ip,
        "public_key": public_key,
        "timestamp": time.time()
    }
    url = f"{SIGNALING_SERVER}/dweet/for/{SYNC_CHANNEL}-{MY_ROLE}"
    print(f"Broadcasting presence to {url}...")

    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Broadcast failed: {e}")

def listen_for_target():
    """
    Polls the server wating for the other device to come online.
    """

    url = f"{SIGNALING_SERVER}/get/latest/dweet/for/{SYNC_CHANNEL}-{TARGET_ROLE}"
    print(f"Listening for {TARGET_ROLE}...")

    while True:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "with" in data and len(data["with"]) > 0:
                    content = data["with"][0]["content"]
                    print(f"Found the [TARGET_ROLE] with IP: {content['ip']}")
                    return content["ip"], content["public_key"]
        except Exception:
            pass
        time.sleep(3)

def derive_shared_key(private_key, target_public_key_pem):
    """
    Combines the private key + target's public key to derive a shared secret key.
    """
    
    #Converting the text public key back to a math object
    peer_public_key = serialization.load_pem_public_key(target_public_key_pem.encode('utf-8'))

    #Performing Diffie-Hellman Key Exchange
    shared_secret = private_key.exchange(ec.ECDH(), peer_public_key)

    #Running the raw secret through a Key Derivation Function (HKDF in this case) to make it a safe 256-bit key for AES
    digest = hashes.Hash(hashes.SHA256)
    digest.update(shared_secret)
    aes_key = digest.finalize()

    return aes_key

def decrypt_incoming_payload(aes_key, raw_packet):
    """
    Seperates the 12-byte nonce from the ciphertext and decrypts it.
    """
    try:
        aesgcm = AESGCM(aes_key)
        nonce = raw_packet[:12] #First 12 bytes are the nonce
        ciphertext = raw_packet[12:] #The rest is the encrypted data
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None) #Decrypting the data
        return decrypted_bytes.decode('utf-8') #Converting bytes back to a string
    except Exception as e:
        print(f"Decryption Failed :( The packet may be corrupted: {e}")
        return None

def start_p2p_listener(aes_key):
    """
    Opens a secure, local network socket port to listen for incoming data from iPad
    """
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Re-using the port if script restarts quickly
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', PORT))
    server.listen(1)
    print(f"Direct secure tunnel listening on port {PORT}...")

    while True:
        conn, addr = server.accept()
        try:
            # Sockets recieve raw bytes, reading upto 4096 bytes
            encrypted_data = conn.recv(4096)
            if encrypted_data:
                print(f"Recieved encrypted payload from {addr[0]}")

                plaintext = decrypt_incoming_payload(aes_key, encrypted_data)

                if plaintext:
                    print(f"Decrypted Payload: '{plaintext}'")
                    save_to_db(plaintext, "android")
                    pyperclip.copy(plaintext)
                    print("Successfully updated local clipboard with the new data!")
        except Exception as e:
            print(f"Tunnel Error: {e}")
        finally:
            conn.close()

def send_secure_payload(target_ip, aes_key, plaintext_data):
    """
    Encrypts data using AES-GCM and pushes it directly to the target node.
    """
    try:
        aesgcm = AESGCM(aes_key) # Initializing AES-GCM with our shared key
        nonce = os.urandom(12) # Generating a random 12-byte nonce (Number used ONCE) for this specific message
        encrypted_payload = aesgcm.encrypt(nonce, plaintext_data.encode('utf-8'), None) # Encrypting the plaintext string
        final_packet = nonce + encrypted_payload # Packaging the nonce and the encrypted data together (reciever needs nonce to decrpyt it)
        
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #Opening an outbound TCP socket connection
        client_socket.settimeout(5) #Not hanging forever if the target drops.

        print(f"Connecting directly to target node at {target_ip}:{PORT}...")
        client_socket.connect((target_ip, PORT)) #Connecting to the target's IP and the agreed upon port number

        client_socket.sendall(final_packet) # Streaming raw bytes
        print("Encrypted payload successfully transmitted!")

    except Exception as e:
        print(f"Failed to send data to target: {e}")
    finally:
        client_socket.close()

def monitor_clipboard_and_send(target_ip, aes_key):
    """
    Continuously monitors the clipboard for changes and sends new data to the target.
    """
    last_clipboard_content = pyperclip.paste()

    while True:
        try:
            current_content = pyperclip.paste()

            # If clipboard has text, and it's diffrent than the last thing we checked
            if current_content and current_content != last_clipboard_content:
                print(f"\n New Clipboard text detected: '{current_content[:20]}'")
                save_to_db(current_content, "laptop")

                send_secure_payload(target_ip, aes_key, current_content)

                last_clipboard_content = current_content
        except Exception as e:
            pass # Completely ignoring clipboard lock errors thrown by Windows sometimes #TODO:

        time.sleep(1.5) #Checking the clipboard every 1.5 seconds, can be adjusted for more or less sensitivity

def main():

    print("-----Starting a OmniSync Node-----")
    
    print("Initializing SQLite History Database...")
    init_db()

    print(f"Using Channel ID: {SYNC_CHANNEL[:8]}...")

    local_ip = get_local_ip()
    print(f"My Local IP: {local_ip}")

    print("Generating ephemeral E2EE keys!")
    private_key, public_key = generate_keypair()
    broadcast_presence(local_ip, public_key)

    target_ip, target_public_key = listen_for_target()
    print("\nSUCCESSS! Phase 1: Handshake Complete!")
    
    print("Computing shared E2EE encryption key...")
    aes_key = derive_shared_key(private_key, target_public_key)
    print("Cryptographic key successfully locked in memory.")

    listener_thread = threading.Thread(
        target=start_p2p_listener, 
        args=(aes_key,), 
        daemon=True
        )
    listener_thread.start()
    
    monitor_clipboard_and_send(target_ip, aes_key)

if __name__ == "__main__":
    main()