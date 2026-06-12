import os
import time
import socket
import requests
import threading
import pyperclip
import sqlite3
import base64
import urllib.parse
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

    my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Asks OS to provide a raw network portal so the script can communicate over a network
    # socket.AF_INET basically specifies the address faimily i.e. either IPv4 or IPv6
    # since here it's only written simply as AF_INET, it defaults to IPv4, if wanted IPv6 then could've basically
    # added it as AF_INET6

    # socket.SOCK_DGRAM specifies that it's a datagram socket i.e. used for UDP communication, meaning we are going
    # to be using the UDP protocol. Used UDP since TCP requires a three-way handshake to establish connection and in case
    # there is no target, TCP would just hang and wait whereas UDP in this case is a connectionless fire and forget protocol so
    # it doesn't really care if the destination exists or not it just prepares the packet to leave the script.
    try:
        my_socket.connect(('10.255.255.255', 1))
        # tells the socket to connect to the given target IP using the given target port i.e. '1' in this case
        # 10.255.255.255 is a basically unroutable, fake IP address and no data is actually send over our network. Basically, when this
        # line executes, the OS looks at its internal routing table and the OS says if the program wants to send a UDP packet i.e. a datagram
        # 10.255.255.255 which of the network cards it should use could be Wi-Fi or ethernet etc so then OS select the active network card
        # i.e. the one which could have a network access and assigns the socket a local origin point
        ip = my_socket.getsockname()[0]
        # Built-in function which checks the socket and returns a *tuple* containing the source configuration i.e.
        # (local_ip, local_port) so since we only care about the local IP we take the first element of the tuple using [0]
    except Exception:
        ip = '127.0.0.1'
        # Safety net i.e. in case windows has no network access like maybe on a airplane then the OS routing table
        # might panic since no active network cards to choose from. This except block catches this error and falls back to 127.0.0.1
        # which is basically the loopback address a.k.a localhost like the computer itself. (example like when we used to run websites locally during development on a laptop itself)
    finally:
        my_socket.close()
        # If we DON'T close the socket we risk having a resource leak, plus it would also free up resources.
    return ip

def generate_keypair():
    """
    Generates an ephemeral SECP384R1 Elliptic Curve keypair.
    Handles the asymmetric cryptography engine i.e. creates a matching pair of cryptographic
    keys one of which is a private key and other one is a public key. 
    """

    private_key = ec.generate_private_key(ec.SECP384R1())
    # Calls the cryptography's library elliptic curve (ec) module to generate a new private key
    # also defines the mathematical shape of the curve we are using i.e. SECP384R1 in out case and in it's title '384' means 384-bit key size 

    public_key = private_key.public_key()
    # Simply uses the elliptic curve multiplication with the private key we just generated and multiplies it by a starting point
    # on the curve, which eventually calculate a coordinate point (x,y) on the curve.
    # With this operation, anyone who has the public key coordinate can easily verify it belongs to our chosen curve, however, they
    # can't reverse-engineer it i.e. figure out the private key with it. Hence we will be sending only the public key over dweet.cc

    # Export as raw DER bytes (no newlines/headers) and compress to Base64
    public_bytes = public_key.public_bytes(
        encoding = serialization.Encoding.DER,
        format = serialization.PublicFormat.SubjectPublicKeyInfo
    )
    # The public key object i.e. in this case is the EllipticCurvePublicKey is a live Python object and issue with that
    # is that we can't send a Python memory object across the internet we need to convert it into a flat stream of data bytes.
    # Hence in the code above we use DER (Distinguished Encoding Rules) which is a strict binary format hence deleting all the human-readable stuff
    # that includes the headers, footers, newlines etc and only encodes key coordinates into pure, compact, raw binary bytes.
    # Secondly, the format used is a standard cryptographic layout structure and ensures that whichever system reads these raw bytes like for e.g.
    # in our case it's the Android phone running Kotlin it will know how to parse the mathematics to rebuild the key object.
    # Note: the SubjectPublicKeyInfo (SPKI) basically tells python to package only two things i.e. actual math of public key, a tag that identifies the algorithm used in our case it's SECP384R1 EC
    
    return private_key, base64.b64encode(public_bytes).decode('utf-8')
    # Finally, we just return a a tuple containing the private key and also the other part i.e. base64.b64encode(public_bytes).decode('utf-8')
    # encodes raw binary bytes and translates them into clean alphanumeric characters since raw binary bytes have messy unprintable character looking
    # like weird symbols and if we directly send them to dweet.cc then it would probably mix up the data or reject it
    # finally, .decode('utf-8') converts these raw bytes into a text string so it can be placed in a JSON package.

def broadcast_presence(local_ip, public_key):
    """
    Sends the IP and Public Key via URL Parameters instead of a JSON body.
    """
    # Safely URL-encodes the Base64 characters (+, /, =) so Dweet doesn't choke
    encoded_params = urllib.parse.urlencode({"ip": local_ip, "public_key": public_key})
    # Before this, we just compressed out cryptographic key into a Base64 string, however, web browsers and server
    # which in our case would be Dweet.cc uses those exact same characters as structural rules for URLS. For e.g. ? means 'start of data',
    # & means 'next item' and so on. If we just gave it the stock Base64 key we have into the URL it's gonna misinterpret the public key and breaking it.
    # so to solve that issue we use the built-in python translator and converts the characters into hexadecimal web codes hence outputting a safe string for the URL.

    url = f"{SIGNALING_SERVER}/dweet/for/{SYNC_CHANNEL}-{MY_ROLE}?{encoded_params}"
    
    print(f"Broadcasting presence to Dweet.cc...")

    try:
        requests.get(url, timeout=10)
        # Fires the network call over the url we have finally generated. Executes a GET request usually POST is used but
        # dweet server's were causing a fuss hence utilized GET and then the server accepts our data.
        # there is a timeout of 10 seconds i.e. if server doesn't respond in 10 secodns then it gives up and moves on
    except Exception as e:
        print(f"Broadcast failed: {e}")
        # in the case if the 10-second timeout is met, then it throws a error and here the error is simply output.

def listen_for_target():
    """
    Polls the server wating for the other device to come online.
    """

    url = f"{SIGNALING_SERVER}/get/latest/dweet/for/{SYNC_CHANNEL}-{TARGET_ROLE}"
    # The link ha schanged here i.e. now we're looking for a message in dweet's inbox by the TARGET_ROLE i.e.
    # in our case 'android'

    print(f"Listening for {TARGET_ROLE}...")

    while True:
        try:
            response = requests.get(url, timeout=10)
            # Pings the url we have and then check that if the response given is OK i.e. a 200 status code
            #  this means the android phone has broadcasted then and if not then it might return a 404 Not Found error

            if response.status_code == 200:
                data = response.json()
                if "with" in data and len(data["with"]) > 0:
                    content = data["with"][0]["content"]
                    # If the android successfully broadcast, then the server sends the data as a giant block of text, the code i.e. 'response.json()' converts that text into a python dictionary
                    # further on we use slicing to look for the 'with' keyword and then in that we look for the 'content' keyword since dweet wraps data in layers.

                    print(f"Found the [TARGET_ROLE] with IP: {content['ip']}")
                    return content["ip"], content["public_key"]
                # The moment the script finds the data, the return statement kills the infinite while True loop and passes the android's IP
                # and public key that is given in the data to the main script so it can start deriving shared key
        except Exception:
            pass
        time.sleep(3)

def derive_shared_key(private_key, target_public_key_b64):
    """
    Combines private key + target's public key to derive shared secret key.
    """
    # Decode the Base64 string from Android back into raw bytes
    target_bytes = base64.b64decode(target_public_key_b64)
    # This above reverses the the decoded raw string so it can be turned back into raw unreadable binary bytes since android did the same and
    # had basically converted it into a alphanumeric string making it possible to send over dweet

    peer_public_key = serialization.load_der_public_key(target_bytes)
    # This takes the decoded output which are the raw binary bytes and mathematically rebuilds the Android phone's public coordinate point on the secp384r1 curve
    # this would allow the python script to have the exact public location of the phone.

    # Performing Diffie-Hellman Key Exchange
    shared_secret = private_key.exchange(ec.ECDH(), peer_public_key)
    # this calles the elliptic curve diffi-hellman algorithm by ec.ECDH() and then private_key.exchange(...) basically takes the laptop's private key and multiplies it with the
    # android's public key which would have the coordinate point we would have gotten from Dweet.
    
    # Note: Since the math of the elliptic curve is accomodating, the order of operations doesn't really matter because the laptop
    # would calculate Laptop_Private x Android_Public whereas the Android would calculate Android_Private x Laptop_Public hence this is basically cross-functional and both calculations would result
    # in the same final number. This final number will be the shared_secret

    # However, there is a slight issue that the current shared_secret is not friendly for AES as AES demands a 256-bit string and Curve points can have predictable leading zeros or
    # could also have mathematical biases hence making it easy to guess and obviously impacting privacy eventually.

    # Match Android's native JCA SHA-256 derivation exactly
    digest = hashes.Hash(hashes.SHA256())
    # This above initializes a cryptographic hashing function.

    digest.update(shared_secret)
    # We give the hashing function the shared_secret we currently have

    aes_key = digest.finalize()
    # The hashing function then processes the curve data and outputs a pefect random 256-bit key.

    # Since NOW FINALLY both the laptop and the android put the exact same shared_secret into the exact same SHA-256 hashing function they both give out the EXACT SAME 256-bit AES key.

    return aes_key

def decrypt_incoming_payload(aes_key, raw_packet):
    """
    Seperates the 12-byte nonce from the ciphertext and decrypts it.
    """
    try:
        aesgcm = AESGCM(aes_key)
        # loads the 256 byte shared secret generated in diffi-hellman into the AES engine

        nonce = raw_packet[:12]
        # the Nonce (Number used ONCE) is basically kinda like a 12-byte unique string added to the math to ensure that every ecnryption is unique.
        # here we strip out the first 12 characters by slicing as the Nonce is always stored at the start.

        ciphertext = raw_packet[12:] #The rest is the encrypted data

        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None) #Decrypting the data
        # the nonce key and the rest of the ciphertext is given to the decrypt function. It checks if the data
        # was tampered with and if so the SHA fingerprint won't match and put out a exception.

        return decrypted_bytes.decode('utf-8') # Converts the raw bytes to standard text string so can be pasted into the windows clipboard
    except Exception as e:
        print(f"Decryption Failed :( The packet may be corrupted: {e}")
        return None

def start_p2p_listener(aes_key):
    """
    Opens a secure, local network socket port to listen for incoming data from Android
    """
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Again we are creating a socket using IPv4, however, this time we are using SOCK_STREAM which basically tells the OS to use TCP instead of UDP. This create
    # a two-way connection between both the devices. 

    # Re-using the port if script restarts quickly
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # The SO_REUSEADDR basically tells the OS that if the port was recently used then it forcefully takes it over and re-uses it immidiately without waiting.

    server.bind(('0.0.0.0', PORT))
    server.listen(1)
    # The first line is a special wildcard that basically tells the laptop to listen for traffic on each and every network card we have be 
    # it Wi-Fi or Ethernet etc. on the port 53317 as that's defined as a constant.

    # server.listen(1) basically turns the socket into a listening server where it allows a queue of 1 device to wait in line if the server is
    # busy processing another connection.

    print(f"Direct secure tunnel listening on port {PORT}...")

    while True:
        conn, addr = server.accept()
        # This is a block function i.e. it freezes the script and goes to sleep basically the second the android node connects on port 53317 then the script wakes up again
        # 'conn' contains a new dedicated socket object to talk to the android connection
        # 'addr' contains the android's ip address so it knows who is on the other end (android node).
        try:
            # Sockets recieve raw bytes, reading upto 4096 bytes
            encrypted_data = conn.recv(4096)
            # It reads the incoming data stream from the android phone, there is a temporary limit set of 4096 bytes at a time (roughly 600-800 words).

            if encrypted_data:
                print(f"Recieved encrypted payload from {addr[0]}")

                plaintext = decrypt_incoming_payload(aes_key, encrypted_data)
                # If the data actually arrives we give to decrypt_incoming_payload with the aes key we have

                if plaintext:
                    print(f"Decrypted Payload: '{plaintext}'")
                    save_to_db(plaintext, "android")
                    # If decryption is successful, then we log in SQLite by the save_to_db(,) function and also adds a android tag to mark where it came from

                    pyperclip.copy(plaintext)
                    # This then copies the decrypted plain text we have onto the windows system clipboard

                    print("Successfully updated local clipboard with the new data!")
        except Exception as e:
            print(f"Tunnel Error: {e}")
        finally:
            conn.close()
            # Since TCP connectios take up system memory it's important to clos the connection once the data is recieved and copied to the clipboard. Furthermore
            # the flow will then cycle back to the top and wait at server.accept() to wait for the next time we copy something on our phone.

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
    # The script saves the content currently on the windows clipboard in the variable
    # this is done since else the script would be assuming whatever was last on the clipboard is new content and send it to the phone as soon as the script starts fresh even. 
    while True:
        try:
            current_content = pyperclip.paste()
            # every time the loop goes it grabs a fresh copy of the windows clipboard

            # If clipboard has text, and it's diffrent than the last thing we checked
            if current_content and current_content != last_clipboard_content:
                # it checks if the clipboard isn't empty and also that the last clipboard content isn't the same as the current one

                print(f"\n New Clipboard text detected: '{current_content[:20]}'")
                save_to_db(current_content, "laptop")
                # saves the clipboard content into the data and tags it with 'laptop' to indicate it was copied off the laptop's clipboard

                send_secure_payload(target_ip, aes_key, current_content)
                # triggers the outgoing network function to encrypt the clipboard's current content and send it to the android phone

                last_clipboard_content = current_content
                # overwriting the previously saved content with current one so the loop goes on ;)
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

    # This basically build a new thread that is assigns a seperate task to the processor to tell 
    # it to give the new task it's own memory space and processor time. It tells the new thread to run the start_p2p_listener function and then
    # the args argument basically contains the argument that are to be passed tothe function itself and deaomon = True basically closes this thread as soon as the main script closes.
    listener_thread.start()
    
    monitor_clipboard_and_send(target_ip, aes_key)

if __name__ == "__main__":
    main()