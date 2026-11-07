"""Note Taker plugin for lxmf-cli.

Save and manage messages as notes in a local SQLite database, with support
for comments.

The message/conversation views intentionally mirror the corresponding code in
lxmf-cli. Conversation indices are assigned through the main client's API.
"""

import os
import shutil
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
try:
    from colorama import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = BLUE = WHITE = ""
    class Style:
        BRIGHT = RESET_ALL = ""


class Plugin:
    def __init__(self, client):
        self.client = client
        self.commands = ["note"]
        self.description = "Save messages as notes and attach comments."

        os.makedirs(self.client.storage_path, exist_ok=True)

        # Shared plugin database; tables are namespaced for future plugins.
        self.database_path = os.path.join(self.client.storage_path, "plugins.db")
        self._initialize_database()

        # Snapshot of the last message view, used by `note save N`.
        self.last_displayed_messages = []
        # Snapshot of the last note list, used by `note del N` / `note comment N`.
        self.last_displayed_note_ids = []
        # Snapshot of the last comment list, used by `note comment del N`.
        self.last_displayed_comment_ids = []
        self.last_inbound_message = self._find_last_inbound_message()

    # ------------------------------------------------------------------
    # Client output helpers
    # ------------------------------------------------------------------
    def _output(self, kind, message):
        """Display a message using the client's 
        output method or print as fallback.
        """
        method = getattr(self.client, f"_print_{kind}", None)
        if callable(method):
            method(str(message))
        else:
            print(message)


    def _color(self, message, color):
        """Display a message with a custom color, 
        unlike standard output methods.
        """
        method = getattr(self.client, "_print_color", None)
        if callable(method):
            try:
                method(str(message), color)
                return
            except Exception:
                pass
        print(message)


    @staticmethod
    def _normalize_hash(hash_str):
        """Normalize a hash by removing separators 
        and brackets and converting to lowercase.
        """
        return (
            str(hash_str or "")
            .replace(":", "")
            .replace(" ", "")
            .replace("<", "")
            .replace(">", "")
            .lower()
        )


    def _message_contact_hash(self, message):
        """Return the contact hash based on the message direction."""
        if message.get("direction") == "outbound":
            return message.get("destination_hash", "")
        return message.get("source_hash", "")


    def _contact_display(self, hash_str):
        """Return the short contact display using the client formatter 
        when available.
        """
        method = getattr(self.client, "format_contact_display_short", None)
        if callable(method):
            try:
                return method(hash_str)
            except Exception:
                pass
        return str(hash_str or "unknown")


    def _copy_messages(self):
        """Return copies of messages, using the client lock when available.
        Copy each message dictionary to avoid modifying the original data.
        Fall back to an unlocked copy if the client has no messages_lock.
        """
        lock = getattr(self.client, "messages_lock", None)
        
        if lock is None:
            messages = getattr(self.client, "messages", [])
            return [dict(message) for message in messages]
            
        with lock:
            messages = self.client.messages
            return [dict(message) for message in messages]


    # ------------------------------------------------------------------
    # Message display helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _format_time_ago(timestamp, mobile=False):
        """Format a message timestamp for the conversation list."""
        time_diff = max(0, time.time() - (timestamp or 0))

        if time_diff < 60:
            return "now" if mobile else "just now"
        if time_diff < 3600:
            return f"{int(time_diff / 60)}m ago"
        if time_diff < 86400:
            return f"{int(time_diff / 3600)}h ago"
        return f"{int(time_diff / 86400)}d ago"


    def show_message_list_with_users(self):
        """Adapted copy of lxmf-cli's show_message_list_with_users().
        called by the 'note msg list' command.
        """
        messages_copy = self._copy_messages()
        
        if not messages_copy:
            self.last_displayed_messages = []
            print("\nNo messages yet\n")
            return []

        try:
            width = min(shutil.get_terminal_size().columns, 90)
            is_mobile = width < 70
        except Exception:
            width = 90
            is_mobile = False

        user_data = {}
        for msg in messages_copy:
            if msg.get("direction") == "outbound":
                hash_key = msg.get("destination_hash", "unknown")
            else:
                hash_key = msg.get("source_hash", "unknown")

            if hash_key == "unknown" or not hash_key:
                continue

            clean_hash = self._normalize_hash(hash_key)
            
            if clean_hash not in user_data:
                conv_index = self.client.assign_conversation_index(hash_key)
                user_data[clean_hash] = {
                    "sent": 0,
                    "received": 0,
                    "last_message_time": 0,
                    "index": conv_index,
                    "display_hash": hash_key,
                }

            if msg.get("direction") == "outbound":
                user_data[clean_hash]["sent"] += 1
            else:
                user_data[clean_hash]["received"] += 1

            timestamp = msg.get("timestamp", 0) or 0
            if timestamp > user_data[clean_hash]["last_message_time"]:
                user_data[clean_hash]["last_message_time"] = timestamp

        sorted_users = sorted(user_data.items(), key=lambda item: item[1]["index"])
        
        print(f"\n{'─' * width}")
        self._color("MESSAGE CONVERSATIONS", Fore.CYAN + Style.BRIGHT)
        print(f"{'─' * width}")

        if is_mobile:
            for clean_hash, data in sorted_users:
                contact_display = self._contact_display(data["display_hash"])
                time_str = self._format_time_ago(
                    data["last_message_time"], mobile=True
                )
                self._color(f"\n[{data['index']}] {contact_display}", Fore.CYAN)
                print(f"    ↑{data['sent']} ↓{data['received']} • {time_str}")
        else:
            print(f"\n{'#':<5} {'Contact':<35} {'Sent':<6} {'Recv':<6} {'Last':<12}")
            print(f"{'─' * 5} {'─' * 35} {'─' * 6} {'─' * 6} {'─' * 12}")
            for clean_hash, data in sorted_users:
                contact_display = self._contact_display(data["display_hash"])
                if len(contact_display) > 33:
                    contact_display = contact_display[:30] + "..."
                time_str = self._format_time_ago(
                    data["last_message_time"]
                )
                print(
                    f"{data['index']:<5} {contact_display:<35} {data['sent']:<6} "
                    f"{data['received']:<6} {time_str:<12}"
                )

        print(f"{'─' * width}")
        self._color(
            "💡 Tip: 'note msg user <N>' | "
            "'note msg [count]'",
            Fore.YELLOW
        )
        print()
        
        return sorted_users
        

    def show_messages(self, limit=10, filter_hash=None):
        """Adapted copy of lxmf-cli's show_messages(),        
        Display recent messages or messages from a specific contact.
        Keep a snapshot of displayed messages for `note save N`.
        """
        messages_copy = self._copy_messages()
        
        if not messages_copy:
            self.last_displayed_messages = []
            print("\nNo messages yet\n")
            return []

        try:
            width = min(shutil.get_terminal_size().columns, 80)
        except Exception:
            width = 80

        if filter_hash:
            clean_filter = self._normalize_hash(filter_hash)
            filtered_messages = []
            
            for msg in messages_copy:
                clean_msg_hash = self._normalize_hash(
                    self._message_contact_hash(msg)
                )
                if clean_msg_hash == clean_filter:
                    filtered_messages.append(msg)
            messages_copy = filtered_messages
            
            if not messages_copy:
                print(
                    f"\nNo messages with {self._contact_display(filter_hash)}\n"
                )
                self.last_displayed_messages = []
                return []

        if filter_hash:
            contact_display = self._contact_display(filter_hash)
            print(f"\n{'─' * width}")
            
            if len(contact_display) > width - 10:
                contact_display = contact_display[:width - 13] + "..."
            self._color(
                f"CHAT: {contact_display.upper()}",
                Fore.CYAN + Style.BRIGHT
            )
            print(f"{'─' * width}")
            
            display_messages = messages_copy
            
        else:
            display_messages = messages_copy[-limit:]
            print(f"\n{'─' * width}")
            self._color(
                f"RECENT MESSAGES ({len(display_messages)})",
                Fore.CYAN + Style.BRIGHT
            )
            print(f"{'─' * width}")

        # Keep a snapshot of the displayed messages so `note save N`
        # can identify the correct message by its displayed position,
        # independently of subsequent changes to the original messages.
        self.last_displayed_messages = [
            dict(message) for message in display_messages
        ]

        for idx, msg in enumerate(display_messages, 1):			
            try:
                ts = datetime.fromtimestamp(
                    msg["timestamp"]
                ).strftime("%Y-%m-%d %H:%M:%S")               
                direction = (
                    "→" if msg.get("direction") == "outbound" else "←"
                )
                
                contact_hash = self._message_contact_hash(msg)
                contact = self._contact_display(contact_hash)
                
                if filter_hash:
                    print(f"\n[{idx}] {ts} {direction}")
                    if msg.get("title"):
                        print(f"Title: {msg['title']}")
                    print(f"\n{msg.get('content', '')}\n")
                    print(f"{'─' * width}")
                else:
                    print(f"\n[{idx}] {ts} {direction} {contact}")
                    if msg.get("title"):
                        print(f"    Title: {msg['title']}")
                    content = str(msg.get("content", ""))
                    print(
                        f"    {content[:100]}..." 
                        if len(content) > 100 
                        else f"    {content}"
                    )
            
            except Exception as exc:
                print(f"\n[{idx}] [Error displaying message: {exc}]")

        print(f"\n{'─' * width}")
        if filter_hash:
            self._color(
                "💡 Tip: 'note save <N>' to save a message",
                Fore.YELLOW
            )
        else:
            self._color(
                "💡 Tip: 'note msg list' or 'note msg user <N>'",
                Fore.YELLOW
            )
        print()       
        return self.last_displayed_messages


    # ------------------------------------------------------------------
    # Note storage
    # ------------------------------------------------------------------
    @contextmanager
    def _db(self):
        """Manage SQLite connections, row formatting, foreign keys 
        and transactions.
        """
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


    def _initialize_database(self):
        """Create the notes and comments tables if they do not exist."""
        with self._db() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS note_taker_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    saved_at REAL NOT NULL,
                    message_timestamp REAL,
                    direction TEXT NOT NULL,
                    source_hash TEXT,
                    destination_hash TEXT,
                    display_name TEXT,
                    title TEXT,
                    content TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS note_taker_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    text TEXT NOT NULL,
                    FOREIGN KEY(note_id) 
                        REFERENCES note_taker_notes(id) 
                        ON DELETE CASCADE
                )
                """
            )


    def _find_last_inbound_message(self):
        """Retrieve the most recent inbound message from the 
        existing message history, or return None if no message is found.
        """
        for message in reversed(self._copy_messages()):
            if message.get("direction") == "inbound":
                return dict(message)
        return None
        
        
    def on_message(self, message, msg_data):
        """Update last_inbound_message whenever 
        a new inbound message is received.
        """
        # The core invokes this before appending the inbound message to history.
        if msg_data and msg_data.get("direction") == "inbound":
            self.last_inbound_message = dict(msg_data)
        return False


    def _save_message_as_note(self, message):
        """Save a message as a note in the database."""
        if not message:
            self._output("error", "No message available to save.")
            return

        direction = message.get("direction")
        with self._db() as connection:
            cursor = connection.execute(
                """
                INSERT INTO note_taker_notes
                    (saved_at, message_timestamp, direction, source_hash,
                     destination_hash, display_name, title, content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    message.get("timestamp"),
                    direction,
                    message.get("source_hash"),
                    message.get("destination_hash"),
                    message.get("display_name"),
                    message.get("title") or "",
                    str(message.get("content", "")),
                ),
            )
            note_id = cursor.lastrowid
        self._output("success", f"Message saved as note #{note_id}.")


    def _list_notes(self):
        """Display all saved notes with their associated comment counts."""
        with self._db() as connection:
            rows = connection.execute(
                """
                SELECT n.id, n.saved_at, n.message_timestamp, n.direction,
                       n.display_name, n.source_hash, n.destination_hash,
                       n.title, n.content, COUNT(c.id) AS comment_count
                FROM note_taker_notes AS n
                LEFT JOIN note_taker_comments AS c ON c.note_id = n.id
                GROUP BY n.id
                ORDER BY n.id DESC
                """
            ).fetchall()

        self.last_displayed_note_ids = [row["id"] for row in rows]
        
        if not rows:
            self.client._print_error(
                "\nNo notes saved yet. Use 'note save N' or 'note save last'.\n"
            )
            return
            
        print("\n" + "─" * 80)
        self.client._print_color("NOTES", Fore.CYAN + Style.BRIGHT)
        print("─" * 80)
        
        for index, row in enumerate(rows, 1):
            timestamp = row["message_timestamp"] or row["saved_at"]
            try:
                time_text = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
            except (TypeError, ValueError, OSError):
                time_text = "unknown time"
                
            contact_hash = (
                row["destination_hash"]
                if row["direction"] == "outbound" 
                else row["source_hash"]
            )
            
            contact = (
                row["display_name"] 
                or (
                    self._contact_display(contact_hash) 
                    if contact_hash 
                    else "unknown"
                )
            )
            
            title = f" — {row['title']}" if row["title"] else ""
            content = str(row["content"]).replace("\n", " ")
            
            if len(content) > 100:
                content = content[:100] + "..."
                
            colored_contact = (
                f"{Fore.CYAN}{Style.BRIGHT}{contact}"
                f"{Style.RESET_ALL}"
            )              
            colored_content = (
                f"{Fore.GREEN}{content}"
                f"{Style.RESET_ALL}"
            )          
            colored_comments = (
                f"{Fore.YELLOW}Comments: {row['comment_count']}"
                f"{Style.RESET_ALL}"
            )
            
            print(
                f"[{index}] {time_text} | " 
                f"{colored_contact}{title} | {colored_content}"
            )
            print(
                f"    Note ID: {row['id']} · "
                f"{colored_comments}"
            )
            
        print(f"\n{'─' * 80}")
        self._color("💡 Tip: 'note comment N' to view comments", Fore.YELLOW)
        print()


    def _resolve_note_id(self, index):
        """Resolve a displayed note number to its database ID."""
        if not self.last_displayed_note_ids:
            self._output(
                "error", "Run 'note list' first to establish note numbering."
            )
            return None  
                      
        if index < 1 or index > len(self.last_displayed_note_ids):
            self._output(
                "error", 
                f"Note number must be between 1 and "
                f"{len(self.last_displayed_note_ids)}."
            )
            return None
            
        return self.last_displayed_note_ids[index - 1]


    def _delete_note(self, index):
        """Delete a saved note using its displayed list number."""
        note_id = self._resolve_note_id(index)      
        if note_id is None:
            return
            
        with self._db() as connection:
            cursor = connection.execute(
                "DELETE FROM note_taker_notes WHERE id = ?",
                (note_id,)
            )
        if cursor.rowcount:
            self._output(
                "success", 
                f"Deleted note #{index} (database ID {note_id})."
            )
        else:
            self._output(
                "error", 
                "That note has already been deleted. "
                "Run 'note list' to refresh the list."
            )


    def _show_comments(self, note_index):
        """Display comments for a saved note."""
        note_id = self._resolve_note_id(note_index)
        if note_id is None:
            return

        with self._db() as connection:
            note_exists = connection.execute(
                "SELECT 1 FROM note_taker_notes WHERE id = ?", (note_id,)
            ).fetchone()                      
            if not note_exists:
                self._output(
                    "error", 
                    "That note has already been deleted. " 
                    "Run 'note list' to refresh the list."
                )
                self.last_displayed_comment_ids = []
                return

            comments = connection.execute(
                """
                SELECT id, created_at, text
                FROM note_taker_comments
                WHERE note_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (note_id,),
            ).fetchall()

        self.last_displayed_comment_ids = [row["id"] for row in comments]
        if not comments:
            self._output("warning", f"No comments for note #{note_index}.")
            return
            
        print("─" * 80)
        self._color(
            f"COMMENTS FOR NOTE #{note_index}",
            Fore.CYAN + Style.BRIGHT
        )
        print("─" * 80)
        
        for index, comment in enumerate(comments, 1):
            try:
                time_text = datetime.fromtimestamp(
                    comment["created_at"]
                ).strftime("%Y-%m-%d %H:%M")
            except (TypeError, ValueError, OSError):
                time_text = "unknown time"
            print(f"[{index}] {time_text}")
            print(f"    {comment['text']}")
        
        print(f"\n{'─' * 80}")       
        self._color(
            "💡 Tip: 'note comment del N' to delete a comment",
            Fore.YELLOW
        )
        print()    

    def _delete_comment(self, index):
        """Delete a comment using its displayed list number."""		
        if not self.last_displayed_comment_ids:
            self._output(
                "error", 
                "Run 'note comment N' first to display the comments."
            )
            return           
        if index < 1 or index > len(self.last_displayed_comment_ids):
            self._output(
                "error", 
                f"Comment number must be between 1 and " 
                f"{len(self.last_displayed_comment_ids)}."
            )
            return

        comment_id = self.last_displayed_comment_ids[index - 1]       
        with self._db() as connection:
            cursor = connection.execute(
                "DELETE FROM note_taker_comments WHERE id = ?", (comment_id,)
            )

        if cursor.rowcount:
            self.last_displayed_comment_ids.pop(index - 1)
            self._output("success", f"Deleted comment #{index}.")
        else:
            self._output(
                "error", 
                "That comment has already been deleted. "
                "Run 'note comment N' to refresh the list."
            )
            self.last_displayed_comment_ids = []


    def _add_comment(self, index, comment_text):
		
        note_id = self._resolve_note_id(index)
        if note_id is None:
            return
        if not comment_text.strip():
            self._output(
                "error", 
                "Comment text cannot be empty. "
                "Usage: note comment N Text of comment"
            )
            return
            
        with self._db() as connection:
            exists = connection.execute(
                "SELECT 1 FROM note_taker_notes WHERE id = ?", (note_id,)
            ).fetchone()
            if not exists:
                self._output(
                    "error", 
                    "That note has already been deleted. "
                    "Run 'note list' to refresh the list."
                )
                return
                
            connection.execute(
                """
                INSERT INTO note_taker_comments 
                    (note_id, created_at, text)
                VALUES (?, ?, ?)
                """,
                (note_id, time.time(), comment_text.strip()),
            )
        self._output("success", f"Comment added to note #{index}.")

    # ------------------------------------------------------------------
    # Command parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _positive_int(value):
        """Return a positive integer or None 
        if the value is invalid.
        """
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None


    def handle_command(self, cmd, parts):
        """Dispatch Note Taker commands to focused handlers."""
        # lxmf-cli currently parses input with cmd_line.split(maxsplit=2).
        # Expand the remainder so subcommands and numeric arguments are parsed
        # consistently whether the caller split all words or only twice.
        if len(parts) >= 3:
            parts = list(parts[:2]) + str(parts[2]).split() + list(parts[3:])

        if len(parts) < 2:
            self._print_help()
            return

        subcommand = parts[1].lower()
        args = parts[2:]
        handlers = {
            "msg": lambda: self._handle_msg_command(args),
            "save": lambda: self._handle_save_command(args),
            "list": self._handle_list_command,
            "del": lambda: self._handle_del_command(args),
            "comment": lambda: self._handle_comment_command(args),
        }

        handler = handlers.get(subcommand)
        if handler is None:
            self._print_help()
            return

        handler()

    def _handle_list_command(self):
        """Keep a uniform command structure   
        and allow future extensions.
        """
        #Handle 'note list'.
        self._list_notes()
        
    def _handle_del_command(self, args):
        """Validate arguments and handle the note deletion command."""
        if not args:
            self._output("error", "Usage: note del N")
            return

        index = self._positive_int(args[0])
        if index is None:
            self._output("error", "Note number must be a positive integer.")
            return
        
        # Handle 'note del N'
        self._delete_note(index)


    def _handle_comment_command(self, args):
        """Handle comment listing, addition, 
        and deletion commands.
        """          
        if args and args[0].lower() == "del":
            if len(args) != 2:
                self._output(
                    "error", 
                    "Usage: note comment del N"
                )
                return

            comment_index = self._positive_int(args[1])
            if comment_index is None:
                self._output(
                    "error", 
                    "Comment number must be a positive integer."
                )
                return
            
            # Handle 'note comment del N'.   
            self._delete_comment(comment_index)
            return
       
        if not args:
            self._output("error", "Usage: note comment N [Text of comment]")
            return
        note_index = self._positive_int(args[0])
        if note_index is None:
            self._output("error", "Note number must be a positive integer.")
            return
        
        # Handle 'note comment N'
        if len(args) == 1:
            self._show_comments(note_index)
            
        # Handle 'note comment N Text of comment'
        else:
            self._add_comment(note_index, " ".join(args[1:]))


    def _handle_msg_command(self, args):
        """Handle 'note msg' commands to list conversations or 
        display messages.
        """
        # Accept both ['user', 'n'] and ['user n'] argument layouts.
        if args:
            expanded_args = []
            for arg in args:
                expanded_args.extend(str(arg).split())
            args = expanded_args

        # Handle the 'note msg list'.
        if args and args[0].lower() == "list":
            self.show_message_list_with_users()
            return

        if args and args[0].lower() == "user":
            if len(args) < 2:
                self._output(
                    "error", 
                    "Usage: note msg user N. ",
                    "Use 'note msg list' to see conversations."
                )
                return
                
            user_index = self._positive_int(args[1])           
            if user_index is None:
                self._output(
                    "error", 
                    "Conversation number must be a positive integer."
                )
                return
                
            # Handle 'note msg user N'.    
            target_hash = None
            for hash_str, conversation_index in (
                self.client.conversation_indices.items()
            ):
                if conversation_index == user_index:
                    target_hash = hash_str
                    break
            if target_hash:
                self.show_messages(limit=9999, filter_hash=target_hash)
            else:
                self._output(
                    "error", 
                    f"No conversation with index {user_index}. "
                    "Use 'note msg list' to see available conversations."
                )
            return
            
        # Handle the command 'note msg N'.
        limit = 10
        if args:
            parsed = self._positive_int(args[0])
            if parsed is None:
                self._output(
                    "warning", 
                    "Invalid number, showing last 10 messages."
                )
            else:
                limit = parsed
        self.show_messages(limit=limit)


    def _handle_save_command(self, args):
        """Validate arguments and save the 
        selected message as a note.
        """
        if not args:
            self._output("error", "Usage: note save N|last")
            return
            
        # Handle 'note save last'.                      
        if args[0].lower() == "last":
            self._save_message_as_note(self.last_inbound_message)
            return

        index = self._positive_int(args[0])
        if index is None:
            self._output(
                "error", 
                "Message number must be a positive integer or 'last'."
            )
            return
        if index > len(self.last_displayed_messages):
            self._output(
                "error", 
                "That message number is not in the last displayed message list. "
                "Run 'note msg' first."
            )
            return
        # Handle 'note save N'.
        self._save_message_as_note(self.last_displayed_messages[index - 1])


    def _print_help(self):
        """Display the Note Taker plugin help and available commands."""
        print("\nNote Taker commands:")
        print("  note msg [N]              Show the last N messages (default 10)")
        print("  note msg list             List conversations")
        print("  note msg user N           Show conversation N")
        print("  note save N|last          Save a displayed message or latest received message")
        print("  note list                 List saved notes")
        print("  note del N                Delete note N from the last note list")
        print("  note comment N [Text]     Show comments for note N, or add a comment")
        print("  note comment del N        Delete comment N from the last comment list\n")
