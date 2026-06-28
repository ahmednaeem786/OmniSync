import pyperclip




class ClipboardManager:
    def __init__(self):
        self.recent_clipboard = pyperclip.paste()

    
    def get_new_text(self):
        """
        Checks the clipboard. If there's new text, it returns it.
        If the text hasn't changed then it returns None.
        """
        current_text = pyperclip.paste()

        if current_text not in [self.recent_clipboard, ""]:
            self.recent_clipboard = current_text
            return current_text

        return None
    

    def write_from_android(self, text):
        """
        Paste text from Android into Windows.
        Critically, it updates 'last_seen_text', so we don't accidentally send it back.
        """
        self.recent_clipboard = text
        pyperclip.copy(text)
        print(f"[CLIPBOARD] Pasted from Android: {text}")

        