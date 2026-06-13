package com.ahmednaeem786.omnisync


import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import com.ahmednaeem786.omnisync.ui.theme.OmniSyncTheme

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat

/*
This is the main window for the android app.
When the app is first run, it pops up to ask the user to allow system notifications.
After getting the permission, it starts the background service using the startForegroundService()
function.
 */
class MainActivity : ComponentActivity() {
//    Our MainActivity class inherits from the main class i.e. ComponentActivity
    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        if (isGranted) {
            startBackgroundService()
        }
    }
//    uses the activity result API by basically first indicating the kernel that it's going to ask
//    the user for something, then uses the RequestPermission() contract to tell the OS what we are
//    going to ask the user for so Android then pops up the Allow/Deny system box.
//    Lastly, there's a lambda function which checks if the permission to allow notifications is
//    granted, then it calls the function startBackgroundService() to further start the service.

    override fun onCreate(savedInstanceState: Bundle?) {

        super.onCreate(savedInstanceState)
        /*Calling the parent class's constructor as we have inherited from ComponentActivity. The
        parent class's constructor will do the necessary background steps like allocating memory and
        integrating with the OS's window manager.
        */

        enableEdgeToEdge()
        /*
        Design function by android to remove the black bars and make the app go full screen i.e.
        blend behind the status bar and the navigation bar.
         */

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) {
                startBackgroundService()
                /*
                If we are dealing with a android OS version i.e. android 13 or higher then we need
                to ask the user for permission to post notifications but before directly asking
                the user for permission of posting notifications, it checks if user might have
                already given permission, if not then triggers the requestPermissionLauncher.launch()
                which then pops up the Allow/Deny notification dialog box.
                 */
            } else {
                requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        } else {
            startBackgroundService()
        }

        setContent {
            /*
            'OmniSyncTheme' applies the app's colors to the UI (Light/Dark Modes) and Scaffold is
            the framework to build the building. It automatically manages the UI element like top
            app bars, floating buttons and the padding
             */
            OmniSyncTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    Greeting(
                        name = "Android",
                        modifier = Modifier.padding(innerPadding)
                    )
                }
            }
        }
    }

    private fun startBackgroundService() {
        val serviceIntent = Intent(this, OmniSyncService::class.java)
        /*
        A Intent is basically asking the OS to turn on something or execute some action. 'this' tells
        that the sender is this current class i.e. 'MainActivity' and 'OmniSyncService::class.java'
        tells that who the recipient is which in this case is 'OmniSyncService.kt' and it asks the OS
        to wake it up.
         */

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            /*
            For phones with less than android 8, we could directly use the startService() command
            to start background tasks but after 8.0 we need to start a foreground service and can't
            start silent background services (If startService() is used apps would run silently and
            could drain the user's battery without him/her knowing)
             */
            startForegroundService(serviceIntent)
            /*
            This restricts by displaying a notification to let the user know the service is
            running.
             */
        } else {
            startService(serviceIntent)
        }
    }

}

@Composable
fun Greeting(name: String, modifier: Modifier = Modifier) {
    Text(
        text = "🫨 OmniSync Background Service Active!" +
                "\nYou can swipe the app away, background tunnel will remain open." +
                "\nSee you on the other side ;)",
        modifier = modifier
        /*
        Text function simply takes the string stored in the text variable and renders it onto the
        screen. modifier argument contains the instructions on how to render the text (e.g. padding,
        colors etc).
         */
    )
}

@Preview(showBackground = true)
@Composable
fun GreetingPreview() {
    OmniSyncTheme {
        Greeting("Android")
    }
}
/*
Dummy function to test how things look. Calls the original Greeting function and allow to preview
the changes live.
 */