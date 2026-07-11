package com.ahmednaeem786.omnisync

import android.app.Service
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import com.ahmednaeem786.omnisync.network.CloudAPI
import com.ahmednaeem786.omnisync.network.CloudListener

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat


class OmniSyncService: Service() {
    private lateinit var clipboardManager: ClipboardManager
    private val cloudAPI = CloudAPI()
    private lateinit var cloudListener: CloudListener

    private var isPastingFromCloud = false

    val CHANNEL_ID = "OmniSyncChannel"

    override fun onCreate() {

        super.onCreate()
        Log.d("OmniSync", "---OmniSync Android Node Starting----")

        createNotificationChannel()

        val notification = createNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(1, notification)
        }

        clipboardManager = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager

        clipboardManager.addPrimaryClipChangedListener {
            if (isPastingFromCloud) {
                isPastingFromCloud = false
                return@addPrimaryClipChangedListener
            }

            val clipData = clipboardManager.primaryClip
            if (clipData != null && clipData.itemCount > 0) {
                val text = clipData.getItemAt(0).text?.toString()
                if (!text.isNullOrEmpty()) {
                    Log.d("OmniSync", "Text Copied!! Sending to Hub...")
                    cloudAPI.sendClip(text)
                }
            }
        }

        cloudListener = CloudListener { incomingText ->

            Handler(Looper.getMainLooper()).post {
                isPastingFromCloud = true
                val clip = ClipData.newPlainText("OmniSync", incomingText)
                clipboardManager.setPrimaryClip(clip)
                Log.d("OmniSync", "Pasted text from Laptop!")
            }
        }

        cloudListener.startListening()

    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
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
        /*
        This function runs if the service is running on a phone with > android 8.0 as it assigns
        priority to the separate notifications deciding on what action they will carry out for e.g.
        making a sound and putting out a banner or just a banner notif etc.
        Requests access to the OS's NotificationManager and then creates a notification channel and
        gives it over to the OS so it can display it properly.
         */
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

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }
}