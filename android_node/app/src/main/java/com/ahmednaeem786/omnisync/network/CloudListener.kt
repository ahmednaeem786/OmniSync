package com.ahmednaeem786.omnisync.network

import android.util.Log
import com.ahmednaeem786.omnisync.Config
import okhttp3.*
import org.json.JSONObject


class CloudListener(private val onTextRecieved: (String) -> Unit) {
    private val client = OkHttpClient()

    private val API_KEY = "SuperSecretAPIKey"

    fun startListening() {
        Log.d("OmniSync", "Opening WebSocket tunnel to ${Config.WS_URL}")

        val request = Request.Builder()
            .url(Config.WS_URL)
            .addHeader("Authorization", "Bearer $API_KEY")
            .build()

        client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d("OmniSync", "[WEBSOCKET] Successfully connected to Laptop!")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    val incomingText = json.optString("text", "")
                    val device = json.optString("device", "")

                    if (incomingText.isNotEmpty() && device != "Android_Phone") {
                        Log.d("OmniSync", "[CLOUD] Received live data: ${incomingText}")

                        onTextRecieved(incomingText)
                    }
                } catch (e: Exception) {
                    Log.e("OmniSync", "[WARNING] Ignored bad message: ${e.message}")
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("OmniSync", "[WebSocket ALARM] Tunnel Disconnected: ${t.message}")
            }
        })
    }
}