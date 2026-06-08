import os
import time
import socket
import requests
from dotenv import load_dotenv
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

load_dotenv()

SYNC_CHANNEL = os.getenv("OMNISYNC_CHANNEL", "omnisync-default-fallback-channel")
SIGNALING_SERVER = os.getenv("SIGNALING_SERVER", "https://dweet.cc")

MY_ROLE = "laptop"
TARGET_ROLE = "ipad"

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
    """Generates an ephemeral X25519 Elliptic Curve keypair."""
    private_key = ec.generate_private_key(ec.SECP384R1())
    public_key = private_key.public_key()

    public_bytes = public_key.public_bytes(
        encoding = serialization.Encoding.PEM,
        format = serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_key, public_bytes.decode('utf-8')

def broadcast_presence(local_ip, public_key):
    """
    Sends the IP and Public Key to the signaling server
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
        print(f"Failed to broadcast presence: {e}")

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
    print(f"Ready to establish direct secure socket to {target_ip}")

if __name__ == "__main__":
    main()