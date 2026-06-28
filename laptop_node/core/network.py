import socket
import time
import os
import sys


class SecureTunnel:
    def __init__(self, port=53317):
        self.port = port
        self.local_ip = self._get_local_ip

    
    def _get_local_ip():
        """
        Bypasses local routing to find actual LAN IP address.
        """
        my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            my_socket.connect(('10.255.255.255', 1))
            ip = my_socket.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            my_socket.close()
        return ip
    

    def send_payload(self, target_ip, encrypted_payload):
        # sourcery skip: extract-duplicate-method
        """
        Encrypts data using AES-GCM and pushes it directly to the target node.
        """
        try:

            # print(f"[DEBUG] Opening TCP Socket to {target_ip}:{PORT}")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #Opening an outbound TCP socket connection
            client_socket.settimeout(5) #Not hanging forever if the target drops.

            print(f"Connecting directly to target node at {target_ip}:{self.port}...")
            client_socket.connect((target_ip, self.port)) #Connecting to the target's IP and the agreed upon port number

            print("[DEBUG] Socket Connected! Pushing Bytes")

            print(f"[DEBUG] Sending {len(encrypted_payload)} bytes over TCP.")
            client_socket.sendall(encrypted_payload) # Streaming raw bytes

            receipt = client_socket.recv(1024).decode('utf-8')

            if receipt == "DESYNC":
                print("\n[DESYNC!!] Android rejected the AES Key, Keys out of synchronization")
                print("Initiating Handshake protocol again")
                time.sleep(3)
                os.execl(sys.executable, sys.executable, *sys.argv)

            elif receipt == "OK":
                print("Successfully sent payload to android")

            else:
                print(f"Payload sent, however, unknown receipt encountered: {receipt}")

        except ConnectionRefusedError:
            print("[DESYNC] Client refused to connect! Android closed the door.")
            print("Android might be requesting new E2EE keys.")
            time.sleep(3)
            os.execl(sys.executable, sys.executable, *sys.argv)

        except Exception as e:
            print(f"Failed to send data to target: {e}")
        finally:
            client_socket.close()

    def recieve_payload(self):
        pass
        # TODO