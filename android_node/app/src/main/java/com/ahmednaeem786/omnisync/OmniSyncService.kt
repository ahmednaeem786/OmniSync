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
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.URL
import java.net.URLEncoder

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

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
    /*
    This class inherits from Service() which is a application component that is able to perform
    long-running operations in the backg    round without a UI.
     */

    private val TAG = "OmniSyncService"
    /*
    Setting A TAG for the logcat messages helps filter in the system logs by simply searching for
    'OmniSyncService'
     */
    private val PORT = 53317
    /*
    Matches the port being used by the python script.
     */
    private val CHANNEL_ID = "OmniSyncChannel"
    /*
    Android requires notifications to be asigned to specific channels. CHANNEL_ID is the internal
    ID for that channel.
     */
    private var serverSocket: ServerSocket? = null
    /*
    Eventually holds the Android TCP socket. The '?' means it's nullable and will be null as well
    when it's not initialized (i.e. we haven't opened the socket yet).
     */
    private var isRunning = false
    /*
    Boolean switch for the background network loop to know when to shut down.
     */

    private lateinit var aesKey: ByteArray
    /*
    'lateinit' is a special kotlin keyword meaning Late initialization which tells the android compiler
    that it doesn't have the data for this right now, but will be putting data into it before trying
    to use it and that it shouldn't crash. This is specifically done since kotlin doesn't allow to
    declare a variable without immediately putting data into it (a.k.a Null Safety).
    Done since we need a variable for the 256 bit AES key and can't create the key until Dweet.cc
    handshake finishes (takes a bit of time)
     */

    override fun onCreate() {
        /*
        createNotificationChannel() registers the notification channel with the OS after allocating
        memory for the app through super.onCreate(). This is done so that when LATER the service starts
        it can post its persistent notification to stay alive.
         */
        super.onCreate()
        Log.d(TAG, "Service Created")
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        /*
        createNotification calls the helper function which build the visual notification card sitting
        in the Android dropdown menu.
        startForeground(1, notification) hands the notification to the OS so it can lock the app
        into foreground state. The '1' in this is a unique ID number for the notification card.
        We check if the service is running since onStartCommand would be called every time the app
        icon is tapped so we don't want to create multiple background threads that are trying to talk
        to Dweet.cc on the same port at the same time which would eventually cause the app to crash.
        performHandshake() starts the procedure of exchanging public keys and starting the TCP
        channel.
        START_STICKY is a system flag which if returned by onStartCommand() tells the OS to restart
        the service if it's killed by the OS.
         */
        Log.d(TAG, "Service Started")

        // Post the persistent notification
        val notification = createNotification()
        startForeground(1, notification)

//        if (!isRunning) {
//            isRunning = true
//            // INSTEAD of starting the TCP listener with a dummy key,
//            // we kick off the handshake.
//            performHandshake()
//        }

        return START_STICKY
    }

    private fun updateSystemClipboard(text: String?) {
        /*
        Handler(Looper.getMainLooper()).post hands the code block to the main thread so it can
        update the system clipboard.
        The app doesn't have the clipboard in itself, hence it asks the Android OS kernel to give
        access to the system clipboard by it's API and since getSystemService can return different
        tools like Location Manager, Bluetooth Manager etc we cast it as ClipboardManager so
        Kotlin knows what things we are allowed access to.
        The clipboard can hold text/links, images, etc. so we wrap our data in a newPLainText(,) func
        to get a ClipData object.
        The old clipboard data is then deleted and the new clipboard data is then set.
         */

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

    private fun getLocalIpAddress(): String {
        /*
        interfaces variable stores the list of physical and virtual network cards active on the
        android phone (also include localhost and 4G/5G cellular modems).
        Runs a while loop to go through each network card one by one and also runs another while
        loop to go through each of their IP addresses.
        At the core it's searching for a address that is not a loopback (like a local host) and
        is a valid IPv4 address and returns after finding such a IP address.
        '?' operator in the return statement means that if the found address is null then it
        simply returns '127.0.0.1' simply as a fallback (to avoid crashing since plugging in a null
        value into a socket would rather crash everything).

         */
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

    override fun onDestroy() {
        /*
        Calls the parent class's onDestroy() function to cleanup the memory for the service while
        killing it.
        Also finally sets the flag to false to indicate that the service is no longer running and
        close down every background thread.
        Also closes the socket if it still exists else just ignores this line due to the '?' operator.
         */
        super.onDestroy()
        isRunning = false
        serverSocket?.close()
        Log.d(TAG, "Service Destroyed")
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }
}