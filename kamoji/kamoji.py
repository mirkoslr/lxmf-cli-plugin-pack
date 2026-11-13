"""
Kaomoji Plugin for LXMF-CLI

A lightweight plugin that replaces text-based kaomoji shortcodes
with their corresponding Unicode characters before sending messages.

Features:
    - Uses '%' as the shortcode delimiter.
    - Supports multiple kaomoji in a single message.
    - Case-insensitive shortcode recognition.
    - Leaves unknown shortcodes unchanged.
    - Integrates with LXMF-CLI through the existing send_message() API.
    - Can coexist with other plugins that wrap send_message(),
      without requiring them to be installed or loaded.

The plugin does not handle message transport or delivery.
It only transforms message content before passing it to the
previously installed send_message() method.
"""
import re
import shutil

from wcwidth import wcswidth

class Plugin:
    def __init__(self, client):
        self.client = client
        self.commands = ['kamoji']
        self.description = "Browse and send Kaomoji (supports %shortcodes in messages)"
        
        # Standard Kaomoji (21)
        self.stickers = {
            # Essential faces (10)
            "smile": "(^_^)",
            "happy": "(≧◡≦)",
            "laugh": "≧▽≦",
            "cry": "(╥﹏╥)",
            "sad": "(｡•́︿•̀｡)",
            "love": "(♥‿♥)",
            "shock": "(⊙_⊙)",
            "angry": "(ಠ益ಠ)",
            "confused": "(・_・ヾ",
            "nope": "ಠ_ಠ",

            # Gestures and expressions (6)
            "hug": "(づ￣ ³￣)づ",
            "facepalm": "(－‸ლ)",
            "shrug": "¯\\_(ツ)_/¯",
            "hello": "( ´ ▽ `)ﾉ",
            "wink": "(｡•̀ᴗ-)✧",
            "thumbsup": "( •̀ᴗ•́ )و",

            # Fun and playful (5)
            "tableflip": "(╯°□°)╯︵ ┻━┻",
            "cat": "(=^･ω･^=)",
            "bear": "ʕ•ᴥ•ʔ",
            "party": "٩(◕‿◕)۶",
            "cute": "(◍•ᴗ•◍)", 
        }

        self._hook_send_message()
        # Plugin loaded notification
        self.client._print_success(
            f"Kaomoji plugin loaded! {len(self.stickers)} Kaomoji available"
        )
        

    def replace(self, match):
        """Replace a matched shortcode with its Kaomoji."""
        shortcode = match.group(1).lower()              
        return self.stickers.get(shortcode, match.group(0))


    def replace_shortcodes(self, content):
        """Replace Kaomoji shortcodes with Unicode characters."""
        pattern = r'%([a-zA-Z0-9]+)'
        
        return re.sub(pattern, self.replace, content)


    def _hook_send_message(self):
        """Hook into client's send_message to replace Kaomoji shortcodes."""
        # Store original send_message
        self._original_send_message = self.client.send_message
        
        # Create wrapper function
        def send_message_with_kaomoji(dest_hash, content, title=None, fields=None):
            if content:
                content = self.replace_shortcodes(content)
            if title:
                title = self.replace_shortcodes(title)

            return self._original_send_message(dest_hash, content, title, fields)
   
        # Replace client's send_message with our wrapper
        self.client.send_message = send_message_with_kaomoji

    
    def handle_command(self, cmd, parts):
        """Handle Kaomoji commands."""
        # Show all available Kaomoji
        self._show_kaomojis()
        
        
    def _show_kaomojis(self):
        """Display available Kaomoji."""
        print("\n" + "=" * 80)
        print(f"                 ( Kaomoji Picker - {len(self.stickers)} )")
        print("=" * 80 + "\n")

        for index, (shortcode, kaomoji) in enumerate(self.stickers.items(), start=1):
            padding = 20 - wcswidth(kaomoji)

            print(
                f" [{index:2}] {kaomoji}{' ' * max(0, padding)} "
                f"%{shortcode:<12} {shortcode}"
            )

        print("\n" + "=" * 80)
        print("💬 Use in messages:")
        print("   Type: s alice Hey %smile looking good!")
        print("   Sends: Hey (^_^) looking good!")
        print("=" * 80 + "\n")
