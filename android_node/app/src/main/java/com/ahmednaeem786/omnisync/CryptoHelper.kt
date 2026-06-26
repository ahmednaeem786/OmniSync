package com.ahmednaeem786.omnisync

import android.util.Base64
import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

import android.util.Log

/*
This acts like the translator for both the devices i.e. the Windows-side python script
and the android-side service. It mainly uses the JCA (Java Cryptography Architecture) and generates
the same SECP384R1 elliptic curve keys and also compresses the public key into the same Base64 string
that the python script uses too.
Furthermore, it takes the laptop's public key, runs the Diffie-Hellman math and then mimics the SHA-256
hashing process to determine the exact 256 bytes AES key.
When the encrypted bytes arrive over the network, it uses the AES-GCM to seperate the Nonce, check
the authentication tag and then decrypts the ciphertext back into plain english text.
 */
class CryptoHelper {

    companion object {
//        companion object makes the functions inside the block static allowing any file in the program
//        to be able to grab them

        fun generateKeyPair(): KeyPair {
            val keyPairGenerator = KeyPairGenerator.getInstance("EC")
            val ecSpec = ECGenParameterSpec("secp384r1")
            keyPairGenerator.initialize(ecSpec)
            return keyPairGenerator.generateKeyPair()
            /*
            Gets access to the built-in math function of the android OS and gets he Elliptic Curve
            algorithm.
            Specifies the curve's shape which in this case is SECP384R1 i.e. the same as the Python
            Script.
            Gives the elliptic curve to the key pair generator so it can calculate the public and
            private keys and give out a KeyPair object so it can be used for the handshake with the
            Python Script.
             */
        }

        fun getPublicKeyString(keyPair: KeyPair): String {
            return Base64.encodeToString(keyPair.public.encoded, Base64.NO_WRAP)
            /*
            Similarly with python, this also converts the public key into a Base64 string so it can
            be sent over Dweet successfully.
             */
        }

        private fun loadPublicKey(base64Key: String): java.security.PublicKey {
            /*
            Decodes the Base64 string back into raw binary data.
            X509EncodedKeySpec is the standard for Pub Keys and by wrapping the key's Bytes inside
            this specification we tell android that the bytes represent a elliptic curve coordinate
            point and how they're structured.
            KeyFactory is used to generate the public key from the bytes using the elliptic curve.
            .generatePublic(spec) parses the bytes, verifies that it is a valid point on SECP384R1 curve
            and creates and returns a Public Key object.
             */
            val keyBytes = Base64.decode(base64Key, Base64.DEFAULT)
            val spec = X509EncodedKeySpec(keyBytes)
            val keyFactory = KeyFactory.getInstance("EC")
            return keyFactory.generatePublic(spec)
        }

        fun deriveSharedKey(privateKey: PrivateKey, targetPublicKeyStr: String): ByteArray {
            /*
            targetPubKey contains the Elliptic Curve coordinate point of the Window Laptop.
            Requests the ECDH (Elliptic Curve Diffie Hellman) algorithm from android OS.
            Loads the android's own secret number i.e. the Private Key generated earlier (in the
            KeyPair generator).
            Combines the laptop's public key with Android's private key to generate a shared secret
            and the 'true' parameter confirms that it's only a 2-party agreement and there isn't
            a third device which will put it's key in.
            .generateSecret() generates the shared secret by performing Android_Private x Laptop_Public
            and puts out the mathematical curve coordinate. This is going to be the exact same coordinate
            calculated by the Python Script.
            Passes the shared secret through a SHA-256 converter to generate a 256 bit AES key and
            again the AES key also going to be the exact same.
             */
            val targetPubKey = loadPublicKey(targetPublicKeyStr)

            val keyAgreement = KeyAgreement.getInstance("ECDH")
            keyAgreement.init(privateKey)
            keyAgreement.doPhase(targetPubKey, true)
            val sharedSecret = keyAgreement.generateSecret()

            val rawHex = sharedSecret.joinToString("") { "%02x".format(it) }
            Log.e("Crypto", "[DEBUG] Android's Raw Shared Secret: $rawHex")

            val digest = MessageDigest.getInstance("SHA-256")
            return digest.digest(sharedSecret)
        }

        fun decryptPayload(aesKeyBytes: ByteArray, rawPacket: ByteArray): String? {
            /*
            The first 12 bytes contains the unique Nonce and the other contains the cipher text.
            secretKey contains the AES key generated earlier but in a object form.
            cipher sets to use a very specific decryption technique which uses AES, GCM (Galois/Counter
            Mode (which has the authentication tag)), NoPadding (no padding with empty spaces) as this
            is the exact same specification being used in the python script.
            Gives the 12-byte nonce into the GCMParameterSpec and the '128' tells the function to
            expect the authentication tag at the end of the ciphertext to be 128 bits/16 bytes long.
            decryptedBytes checks the 16-byte auth tag and then decrypts the rest of the ciphertext or
            even if one byte was altered (hacking/interception) a exception is thrown.
            Finally the decrypted data is then converted to a string with UTF-8 encoding for the
            phone's clipboard
             */
            return try {
                val nonce = rawPacket.copyOfRange(0, 12)
                val ciphertext = rawPacket.copyOfRange(12, rawPacket.size)

                val secretKey = SecretKeySpec(aesKeyBytes, "AES")
                val cipher = Cipher.getInstance("AES/GCM/NoPadding")

                val spec = GCMParameterSpec(128, nonce)
                cipher.init(Cipher.DECRYPT_MODE, secretKey, spec)

                val decryptedBytes = cipher.doFinal(ciphertext)
                String(decryptedBytes, Charsets.UTF_8)

            } catch (e: Exception) {
                e.printStackTrace()
                throw e
            }
        }
    }
}
