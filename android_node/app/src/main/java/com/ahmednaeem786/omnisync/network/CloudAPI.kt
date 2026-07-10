package com.ahmednaeem786.omnisync.network

import android.util.Log
import com.ahmednaeem786.omnisync.Config
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException

class CloudAPI {

    private val client = OkHttpClient()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    fun sendClip(text: String) {
        val json = JSONObject()
        json.put("text", text)
        json.put("device", "Android_Phone")

        val body = json.toString().toRequestBody(jsonMediaType)

        val request = Request.Builder()
            .url("${Config.SERVER_URL}/api/clips")
            .post(body)
            .build()

        client.newCall(request).enqueue(object: Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e("OmniSync", "[API ERROR] Could not reach laptop: ${e.message}")
            }

            override fun onResponse(call: Call, response: Response) {
                if (response.isSuccessful) {
                    Log.d("OmniSync", "[API] Successfully uploaded to Laptop!")
                } else {
                    Log.e("OmniSync", "[API ERROR] Laptop rejected! Code: ${response.code}")
                }

                response.close()
            }
        })
    }
}