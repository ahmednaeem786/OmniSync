package com.ahmednaeem786.omnisync

class Config {

    companion object {
        private const val LAPTOP_IP = "192.168.100.30"

        const val SERVER_URL = "http://$LAPTOP_IP:8000"
        const val WS_URL = "ws://$LAPTOP_IP:8000/ws"
    }
}