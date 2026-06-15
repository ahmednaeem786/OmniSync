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
    /*
    This class inherits from Service() which is a application component that is able to perform
    long-running operations in the background without a UI.
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

        if (!isRunning) {
            isRunning = true
            // INSTEAD of starting the TCP listener with a dummy key,
            // we kick off the handshake.
            performHandshake()
        }

        return START_STICKY
    }

    private fun startTcpListener() {
        /*
        Creates a new background thread to listen for incoming TCP connections.
        ServerSocket(PORT) requests the Android OS to reserve port number 53317 and routing any
        incoming network traffic on that port directly to this application.
        It runs a infinite polling (while) loop which runs endlessly as long as the service is alive
        and this only ends when the service is closed off.
        .accept() is a blocking function which means the background thread would freeze and then
        sleep until a connection is made and the point at which the python script sends secure payload
        and connects to the phone's IP address this thread would wake up again and creates a dedicated
        clientSocket to catch the incoming bytes.
        The double exclamation mark '!!' indicates that the socket isn't null and forces it to compile.
        After a successful connection, the socket is then passed to a further function so it can then
        decrypt the data so that this current listening thread can loop back to the .accept() function
        and go to sleep (else if we would've done the decryption right here then server would've been
        still busy and might miss new clipboard text coming in).
         */
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
        /*
        This function recieves the live socket from startTcpListener() function. It creates a new
        thread so we can accomodate another clipboard message while keeping the server free.
        socket.getInputStream() starts the connection coming from the Window laptop. Sockets read a
        portion of data each time and in this case it read around 4 KiloBytes/4096 Bytes at once.
        rawPacket contains the exactly sized encrypted package as the portion can hold 4096 bytes but
        if the payload (recieved data) is only 45 bytes then the remaining 4051 bytes would be just
        empty zeroes and if the AES decrypter is fed empty zeroes, then it would crash.
        This rawPacket is then handed over to the CryptoHelper's function i.e. decryptPayload which
        seperates the Nonce, check the authentication tag and then decrypts the ciphertext back into
        plain text.
         */
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

    private fun performHandshake() {
        /*
        This function first asks the internal functions from CryptoHelper to generate a key pair and
        from the elliptic curve and then also formats it as a Base64 String. It then also stores our
        local IP address.
        URLEncoder.encode(,) then translates the public key into a UTF-8 format so it's safe to send
        over the web and later on is appended with the IP into the URL.
        broadcastConn contains the procedure to send the URL onto the dweet server with a GET request
        method and also spoofs by setting the user-agent to Mozilla/5.0....
        After broadcast is sent over Dweet server the phone then switches into a listening mode
        where it monitors the '-laptop' channel and then enters a while loop until the laptopPubKey
        is found.
        If the Dweet server returns a 200 OK status then the program reads the text and parses the
        text received in JSON to extract the IP address and public key, however, if the Dweet server
        hasn't returned the text yet, the thread goes to sleep for 3 seconds to avoid getting a IP ban.
        Then the laptop's public key and the phone's private key is fed into the Diffie-Hellman
        procedure to determine the exactly same 256-bit AES key as the python script.
        After determining the AES key, it triggers startTcpListener() to start syncing clipboards.
         */
        thread(start = true, name = "HandshakeThread") {
            try {
                Log.i(TAG, "Starting Dweet Handshake...")
                val channel = "omnisync-default-fallback-channel"

                val keyPair = CryptoHelper.generateKeyPair()
                val myPublicKeyStr = CryptoHelper.getPublicKeyString(keyPair)
                val myIp = getLocalIpAddress()

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