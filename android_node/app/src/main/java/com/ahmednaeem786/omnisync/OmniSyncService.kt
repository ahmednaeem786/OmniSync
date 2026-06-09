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

        val notification = createNotification()
        startForeground(1, notification)

        aesKey = ByteArray(32) {0.toByte() }

        if (!isRunning) {
            isRunning = true
            startTcpListener()
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