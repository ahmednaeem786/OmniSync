from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import os



class CryptoEngine:
    def __init__(self):

        self.private_key = None
        self.public_key_base64 = None
        self.aes_key = None

        self._generate_keypair()

    def _generate_keypair(self):
        """
        Generates an ephemeral SECP384R1 Elliptic Curve keypair.
        Handles the asymmetric cryptography engine i.e. creates a matching pair of cryptographic
        keys one of which is a private key and other one is a public key. 
        """

        self.private_key = ec.generate_private_key(ec.SECP384R1())

        public_key = self.private_key.public_key()

        public_bytes = public_key.public_bytes(
            encoding = serialization.Encoding.DER,
            format = serialization.PublicFormat.SubjectPublicKeyInfo
        )

        self.public_key_base64 = base64.b64encode(public_bytes).decode('utf-8')

        return self.private_key, self.public_key_base64
    
    def derive_shared_key(self, target_public_key_b64):
        """
        Combines private key + target's public key to derive shared secret key.
        """

        target_bytes = base64.b64decode(target_public_key_b64)

        peer_public_key = serialization.load_der_public_key(target_bytes)
        shared_secret = self.private_key.exchange(ec.ECDH(), peer_public_key)

        print(f"[DEBUG] Python-side Raw Shared Secret: {shared_secret.hex()}")

        digest = hashes.Hash(hashes.SHA256())

        digest.update(shared_secret)
        self.aes_key = digest.finalize()

        print(f"[DEBUG] Current AES Key: {self.aes_key.hex()}")

    def encrypt_payload(self, plaintext_data):
        """
        Encrypts data using AES-GCM.
        """
        if not self.aes_key:
            raise ValueError("AES Key not derived yet!!")
        
        try:
            aesgcm = AESGCM(self.aes_key) # Initializing AES-GCM with our shared key
            nonce = os.urandom(12) # Generating a random 12-byte nonce (Number used ONCE) for this specific message
            encrypted_payload = aesgcm.encrypt(nonce, plaintext_data.encode('utf-8'), None) # Encrypting the plaintext string
            final_packet = nonce + encrypted_payload # Packaging the nonce and the encrypted data together (reciever needs nonce to decrpyt it)

            return final_packet
        
        except Exception as e:
            raise RuntimeError(f"Encryption Failed: {e}")

    def decrypt_payload(self, crypted_payload):
        """Decrypts bytes using locally saved AES Key."""
        if not self.aes_key:
            raise ValueError("AES Key not derived yet!!")
        
        try:
            aesgcm = AESGCM(self.aes_key)
            # loads the 256 byte shared secret generated in diffi-hellman into the AES engine

            nonce = crypted_payload[:12]
            # the Nonce (Number used ONCE) is basically kinda like a 12-byte unique string added to the math to ensure that every ecnryption is unique.
            # here we strip out the first 12 characters by slicing as the Nonce is always stored at the start.

            ciphertext = crypted_payload[12:] #The rest is the encrypted data

            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None) #Decrypting the data
            # the nonce key and the rest of the ciphertext is given to the decrypt function. It checks if the data
            # was tampered with and if so the SHA fingerprint won't match and put out a exception.

            return decrypted_bytes.decode('utf-8') # Converts the raw bytes to standard text string so can be pasted into the windows clipboard
        except Exception as e:
            raise RuntimeError(f"Decryption failed (AES Key Mismatch): {e}")
