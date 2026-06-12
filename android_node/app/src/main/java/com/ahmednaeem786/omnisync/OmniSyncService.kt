package com.ahmednaeem786.omnisync

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import androidx.core.app.NotificationCompat
import java.io.DataInputStream
import java.net.ServerSocket
import java.net.Socket
import kotlin.concurrent.thread

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.NetworkInterface
import java.net.URL
import java.net.URLEncoder

/*
This is the main core of the Android app. It is a foreground service which is basically a special
class in android for apps that need to run continuously. The startForeground() ties the service
to a persistent notification in the status bar hence indicating the android kernel to not restrict cpu
or network access for the service.
It first connects to dweet.cc and sends its IP and key and then waits for the data to be send from
the laptop. Secondly, once the AES key is recieved, it opens port 53317 and then waits for the laptop
to send it's clipboard data.
Once the clipboard data arrives from the laptop it uses Handler(Looper.getMainLooper()).post to
go from the background network thread to the main thread just long enough to
pust the text into the system's clipboard.
 */
class OmniSyncService: Service() {

    private val TAG = "OmniSyncService"
    private val PORT = 53317
    private val CHANNEL_ID = "OmniSyncChannel"
    private var serverSocket: ServerSocket? = null
    private var isRunning = false

    private lateinit var aesKey: ByteArray

    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "Service Created")
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d(TAG, "Service Started")

        // Post the persistent notification
        val notification = createNotification()
        startForeground(1, notification)

        if (!isRunning) {
            isRunning = true
            // INSTEAD of starting the TCP listener with a dummy key,
            // we kick off the handshake.
            performHandshake()
        }

        return START_STICKY
    }

    private fun startTcpListener() {
        thread(start = true, isDaemon = true, name = "OmniSyncSocketThread") {
            try {
                serverSocket = ServerSocket(PORT)
                Log.i(TAG, "Direct secure tunnel listening on port $PORT...")

                while (isRunning) {
                    val clientSocket: Socket = serverSocket!!.accept()
                    Log.d(TAG, "Incoming payload detected from: ${clientSocket.inetAddress.hostAddress}")

                    handleIncomingConnection(clientSocket)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Socket Server Error: ${e.message}")
            }
        }
    }

    private fun handleIncomingConnection(socket: Socket) {
        thread(start = true) {
            try {
                val inputStream = DataInputStream(socket.getInputStream())
                val buffer = ByteArray(4096)
                val bytesRead = inputStream.read(buffer)

                if (bytesRead > 0) {
                    val rawPacket = buffer.copyOfRange(0, bytesRead)

                    val plaintext = CryptoHelper.decryptPayload(aesKey, rawPacket)

                    if (plaintext != null) {
                        Log.i(TAG, "Successfully Decrypted Payload: '$plaintext")
                        updateSystemClipboard(plaintext)
                    } else {
                        Log.w(TAG, "Received packet, but decryption failed.")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error handling connection: ${e.message}")
            } finally {
                socket.close()
            }
        }
    }

    private fun updateSystemClipboard(text: String) {

        Handler(Looper.getMainLooper()).post {
            try {
                val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = ClipData.newPlainText("OmniSync Data", text)
                clipboard.setPrimaryClip(clip)
                Log.d(TAG, "System clipboard successfully updated tracking token!")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to write system clipboard: ${e.message}")
            }
        }
    }

    private fun createNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("OmniSync Active")
            .setContentText("Background real-time secure clipboard link active.")
            .setSmallIcon(android.R.drawable.ic_popup_sync)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                CHANNEL_ID,
                "OmniSync Service Channel",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(serviceChannel)
        }
    }

    private fun getLocalIpAddress(): String {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val networkInterface = interfaces.nextElement()
                val addresses = networkInterface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val address = addresses.nextElement()

                    if (!address.isLoopbackAddress && address is java.net.Inet4Address) {
                        return address.hostAddress ?: "127.0.0.1"
                    }
                }
            }
        } catch (e: Exception) { e.printStackTrace() }
        return "127.0.0.1"
    }

    private fun performHandshake() {
        thread(start = true, name = "HandshakeThread") {
            try {
                Log.i(TAG, "Starting Dweet Handshake...")

                val channel = "omnisync-default-fallback-channel"

                val keyPair = CryptoHelper.generateKeyPair()
                val myPublicKeyStr = CryptoHelper.getPublicKeyString(keyPair)
                val myIp = getLocalIpAddress()

                val postUrl = URL("https://dweet.cc/dweet/for/$channel-android")
                val postConn = postUrl.openConnection() as HttpURLConnection
                // 2. Broadcast Android Presence via GET URL Parameters
                val encodedKey = URLEncoder.encode(myPublicKeyStr, "UTF-8")
                val broadcastUrl = URL("https://dweet.cc/dweet/for/$channel-android?ip=$myIp&public_key=$encodedKey")

                val broadcastConn = broadcastUrl.openConnection() as HttpURLConnection
                broadcastConn.requestMethod = "GET"
                broadcastConn.setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

                Log.d(TAG, "Broadcast sent. Server Response: ${broadcastConn.responseCode}")

                val getUrl = URL("https://dweet.cc/get/latest/dweet/for/$channel-laptop")
                var laptopPubKey: String? = null

                while (laptopPubKey == null && isRunning) {
                    val getConn = getUrl.openConnection() as HttpURLConnection
                    getConn.setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

                    if (getConn.responseCode == 200) {
                        val response = getConn.inputStream.bufferedReader().readText()
                        val json = JSONObject(response)

                        if (json.has("with")) {
                            val content = json.getJSONArray("with").getJSONObject(0).getJSONObject("content")
                            val laptopIp = content.getString("ip")
                            laptopPubKey = content.getString("public_key")
                            Log.i(TAG, "Found Laptop at IP: $laptopIp")
                        }
                    }
                    if (laptopPubKey == null) Thread.sleep(3000)
                }

                if (laptopPubKey != null) {
                    aesKey = CryptoHelper.deriveSharedKey(keyPair.private, laptopPubKey)
                    Log.i(TAG, "Success!! Phase 1 Complete. E2EE Key Locked.")

                    startTcpListener()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Handshake Error: ${e.message}")
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        serverSocket?.close()
        Log.d(TAG, "Service Destroyed")
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }
}