import os
import time
import socket
import requests
from dotenv import load_dotenv
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

load_dotenv()

SYNC_CHANNEL = os.getenv("OMNISYNC_CHANNEL", "omnisync-default-fallback-channel")
SIGNALING_SERVER = os.getenv("SIGNALING_SERVER", "https://dweet.cc")
MY_ROLE = "laptop"
TARGET_ROLE = "ipad"
PORT = 53317

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
    aes_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'omnisync-key-derivation',
    ).derive(shared_secret)

    return aes_key

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
        except Exception as e:
            print(f"Tunnel Error: {e}")
        finally:
            conn.close()

def main():

    print("-----Starting a OmniSync Node-----")
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

    start_p2p_listener(aes_key) #Listening for the iPad to send things

if __name__ == "__main__":
    main()