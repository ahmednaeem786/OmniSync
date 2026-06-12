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

        fun generateKeyPair(): KeyPair {
            val keyPairGenerator = KeyPairGenerator.getInstance("EC")
            val ecSpec = ECGenParameterSpec("secp384r1")
            keyPairGenerator.initialize(ecSpec)
            return keyPairGenerator.generateKeyPair()
        }

        fun getPublicKeyString(keyPair: KeyPair): String {
            return Base64.encodeToString(keyPair.public.encoded, Base64.NO_WRAP)
        }

        private fun loadPublicKey(base64Key: String): java.security.PublicKey {
            val keyBytes = Base64.decode(base64Key, Base64.DEFAULT)
            val spec = X509EncodedKeySpec(keyBytes)
            val keyFactory = KeyFactory.getInstance("EC")
            return keyFactory.generatePublic(spec)
        }

        fun deriveSharedKey(privateKey: PrivateKey, targetPublicKeyStr: String): ByteArray {
            val targetPubKey = loadPublicKey(targetPublicKeyStr)

            val keyAgreement = KeyAgreement.getInstance("ECDH")
            keyAgreement.init(privateKey)
            keyAgreement.doPhase(targetPubKey, true)
            val sharedSecret = keyAgreement.generateSecret()

            val digest = MessageDigest.getInstance("SHA-256")
            return digest.digest(sharedSecret)
        }

        fun decryptPayload(aesKeyBytes: ByteArray, rawPacket: ByteArray): String? {
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
                null
            }
        }
    }
}