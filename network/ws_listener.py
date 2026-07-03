"""
Job: It is completely responsible for pulling data down from the cloud.

Rules: You give this class a reference to your ClipboardManager. 
It opens the permanent WebSocket tunnel and goes to sleep. 
When the cloud shouts a new copied text down the tunnel, this class catches it and immediately tells the ClipboardManager to paste it.
"""