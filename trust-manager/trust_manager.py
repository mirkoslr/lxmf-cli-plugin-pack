"""
Trust Manager plugin for LXMF-CLI.

Maintains local trust classifications (trusted, known, unverified),
contact aliases, and notes associated with LXMF destination hashes.

Data is stored in ``trust_manager.json`` inside the client's storage
directory, loaded at initialization, and persisted on updates using
an atomic file replacement.

The plugin integrates through LXMF-CLI's plugin interface and public
contact-resolution APIs. It does not modify the native blacklist,
intercept messages, or initiate network lookups.

Trust levels are user-defined metadata: they do not verify identities,
guarantee message safety, or enforce access control.
"""

import json
import os
import re
import time

class Plugin:
    
    # Available trust levels for classifying contacts.
    LEVELS = ("trusted", "known", "unverified")

    def __init__(self, client):
        self.client = client
        self.commands = ["trust"]
        self.description = "Local contact trust classifications"
        self.data_path = os.path.join(
            self.client.storage_path,
            "trust_manager.json",
        )

        self.contacts = {}
        self._load()

        self.client._print_success(
            "Trust Manager loaded. Use 'trust help'."
        )
        
    def on_message(self, message, msg_data):
        """Observe messages without intercepting normal processing."""
        return False
        
    def handle_command(self, cmd, parts):
        """Dispatch Trust Manager commands to small, focused handlers."""
        if len(parts) < 2:
            self._help()
            return

        action = parts[1].lower()
        remainder = parts[2].strip() if len(parts) > 2 else ""
        
        handlers = {
            "help": lambda: self._help(),
            "list": lambda: self._handle_list_command(remainder),
            "show": lambda: self._handle_show_command(action, remainder),
            "set": lambda: self._handle_set_command(remainder),
            "note": lambda: self._handle_note_command(remainder),
            "alias": lambda: self._handle_alias_command(remainder),
            "remove": lambda: self._handle_remove_command(remainder),
            "stats": lambda: self._show_stats(),
        }
        
        handler = handlers.get(action)
        
        if handler is None:
            self._help()
            return
            
        handler()
       
       
    @staticmethod
    def _normalize_hash(value):
        """Normalize a destination hash to lowercase hexadecimal,
        independently of the client resolver."""
        value = str(value).strip()
        value = value.replace(":", "").replace(" ", "")
        value = value.replace("<", "").replace(">", "")
        value = value.lower()

        if not re.fullmatch(r"[0-9a-f]{32}", value):
            return None

        return value


    def _load(self):
        """Load and validate trust records from the JSON file 
        into self.contacts."""
        try:
            if not os.path.exists(self.data_path):
                return

            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                self.client._print_error(
                    "Invalid trust data format; starting empty."
                )
                return

            for key, entry in data.items():
                normalized = self._normalize_hash(key)

                if (
                    normalized
                    and isinstance(entry, dict)
                    and entry.get("level") in self.LEVELS
                ):
                    self.contacts[normalized] = {
                        "level": entry["level"],
                        "note": str(entry.get("note", "")),
                        "alias": str(entry.get("alias", "")).strip(),
                        "updated_at": entry.get("updated_at", 0),
                    }

        except (OSError, json.JSONDecodeError) as exc:
            self.client._print_error(f"[Trust] Could not load data: {exc}")


    def _save(self):
        """Save trust data to the JSON file using a temporary file
        to protect the original from corruption."""
        temp_path = self.data_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(
                    self.contacts,
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            os.replace(temp_path, self.data_path)
            return True

        except OSError as exc:
            self.client._print_error(f"[Trust] Could not save data: {exc}")
            
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass

            return False


    def _resolve(self, target):
        """Resolve a name to a hash by searching the Trust Manager JSON first,
        then delegating to the LXMF-CLI API if no match is found.
        If the target is already a hash, return its normalized form.
        Return None if resolution fails.
        """
        target = str(target).strip()
        if not target:
            return None

        # Check whether the target is already a valid hash.
        normalized = self._normalize_hash(target)
        if normalized:
            return normalized

        target_folded = target.casefold()

        # First consult aliases explicitly saved in the Trust Manager JSON.
        for hash_str, entry in self.contacts.items():
            if str(entry.get("alias", "")).strip().casefold() == target_folded:
                return hash_str

        # Delegate contact and peer resolution to the LXMF-CLI API.
        resolved = self.client.resolve_contact_or_hash(target)

        # Validate and normalize the hash returned by the API.
        if resolved:
            return self._normalize_hash(resolved)

        return None


    def _display_name(self, hash_str):
        """Resolve a hash to a display name.
        First checks the alias saved in the Trust Manager, then tries
        the LXMF-CLI contact nickname and announced display name.
        Returns the original hash if no name is found.
        """
        entry = self.contacts.get(hash_str, {})
        saved_alias = str(entry.get("alias", "")).strip()
        if saved_alias:
            return saved_alias

        # Prefer LXMF-CLI's known contact nickname, then its announced display
        # name. These lookups use the client's current/local data.
        for method_name in ("get_contact_name_by_hash", "get_lxmf_display_name"):
            method = getattr(self.client, method_name, None)
            if callable(method):
                try:
                    name = method(hash_str)
                    if name and str(name) != hash_str:
                        return str(name)
                except Exception:
                    pass

        return hash_str


    def _get_entry(self, target):
        """Resolve a contact name, alias or hash and return the normalized hash
        and its associated contact data from the Trust Manager dictionary.
        Returns (None, None) if resolution fails.
        """
        hash_str = self._resolve(target)

        if not hash_str:
            self.client._print_error(
                f"[Trust] Unknown contact or invalid hash: {target}"
            )

        return hash_str, self.contacts.get(hash_str)


    def _color(self, text, color_name=None, bright=False, dim=False):
        """Apply the client's Colorama colors and styles, falling back 
        to plain text."""
        fore = getattr(self.client, "Fore", None)
        style = getattr(self.client, "Style", None)
        color = getattr(fore, color_name, "") if fore and color_name else ""
        emphasis = getattr(style, "BRIGHT", "") if bright and style else ""
        subdued = getattr(style, "DIM", "") if dim and style else ""
        reset = getattr(style, "RESET_ALL", "") if style else ""
        return f"{subdued}{emphasis}{color}{text}{reset}"


    @staticmethod
    def _level_symbol(level):
        """Return the symbol associated with a trust level, 
        defaulting to ○."""
        return {
            "trusted": "★",
            "known": "◆",
            "unverified": "○",
        }.get(level, "○")


    def _level_color(self, level):
        """Return the color name associated with a trust level, 
        defaulting to LIGHTBLACK_EX."""
        return {
            "trusted": "GREEN",
            "known": "YELLOW",
            "unverified": "MAGENTA",
        }.get(level, "CYAN")


    def _show_entry(self, hash_str, entry):
        """Display a contact's hash, name, trust level, note, and last update.
        hash_str: The contact's hash.
        entry: The contact's data dictionary, or None if not recorded."""
        print(
            self._color("Contact: ", "CYAN", bright=True)
            + self._color(self._display_name(hash_str), "WHITE", bright=True)
        )
        print(self._color("Hash:    ", "CYAN", bright=True) + hash_str)

        if entry is None:
            level_text = "○ unverified (default; not explicitly recorded)"
            print("Level:   " + self._color(level_text, self._level_color("unverified")
            ))
            print(self._color("note:    ", "CYAN", bright=True) + "none")
            return

        level = entry["level"]
        level_text = f"{self._level_symbol(level)} {level}"
        print(
            self._color("Level:   ", "CYAN", bright=True)
            + self._color(
                level_text,
                self._level_color(level),
                bright=(level == "trusted"),
            )
        )
        print(
            self._color("note:    ", "CYAN", bright=True)
            + (entry.get("note") or "none")
        )

        updated_at = entry.get("updated_at")
        if updated_at:
            print(
                self._color("Updated: ", "CYAN", bright=True)
                + time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(updated_at),
                )
            )


    def _list_contacts(self, level_filter=None):
        """Display all contacts or only those matching a trust level."""
        entries = [
            (hash_str, entry)
            for hash_str, entry in self.contacts.items()
            if level_filter is None or entry["level"] == level_filter
        ]

        if not entries:
            self.client._print_warning("[Trust] No matching classifications.")
            return

        for hash_str, entry in sorted(
            entries,
            key=lambda item: (
                item[1]["level"],
                self._display_name(item[0]).lower(),
            ),
        ):
            name = self._display_name(hash_str)
            level = entry["level"]
            label = f"{self._level_symbol(level)} {level}"
            colored_label = self._color(
                label, self._level_color(level), bright=(level == "trusted")
            )
            # Pad using the plain label length, not ANSI escape-sequence length.
            padding = " " * max(1, 22 - len(label))
            colored_name = self._color(name, "WHITE", bright=True)
            print(f"{colored_label}{padding}{colored_name} [{hash_str[:12]}...]")

            if entry.get("note"):
                print(
                    "             "
                    + self._color("note: ", "CYAN", bright=True)
                    + entry["note"]
                )

        print(f"\nTotal: {len(entries)}")


    def _set_level(self, target, level):
        """Set a contact's trust level, 
        creating or updating its entry."""
        if level not in self.LEVELS:
            self.client._print_warning(
                "[Trust] Invalid level. Choose: "
                + ", ".join(self.LEVELS)
            )
            return

        hash_str = self._resolve(target)

        if not hash_str:
            self.client._print_warning(
                f"[Trust] Unknown contact or invalid hash: {target}"
            )
            return

        previous = self.contacts.get(hash_str, {})
        normalized_target = self._normalize_hash(target)
        remembered_alias = previous.get("alias", "")
        if not remembered_alias and not normalized_target:
            remembered_alias = target.strip()
        self.contacts[hash_str] = {
            "level": level,
            "note": previous.get("note", ""),
            "alias": remembered_alias,
            "updated_at": time.time(),
        }

        if self._save():
            self.client._print_success(
                f"[Trust] {self._display_name(hash_str)} "
                f"set to {level}."
            )


    def _set_note(self, target, note):
        """Set a contact's note and save the changes."""
        hash_str = self._resolve(target)

        if not hash_str:
            self.client._print_warning(
                f"[Trust] Unknown contact or invalid hash: {target}"
            )
            return

        entry = self.contacts.get(
            hash_str,
            {
                "level": "unverified",
                "note": "",
                "alias": "",
                "updated_at": 0,
            },
        )

        entry["note"] = note
        entry["updated_at"] = time.time()
        self.contacts[hash_str] = entry

        if self._save():
            self.client._print_success(
                f"[Trust] Note saved for {self._display_name(hash_str)}."
            )


    def _set_alias(self, target, alias):
        """Save a local human-readable alias for a known hash."""
        hash_str = self._normalize_hash(target)
        alias = alias.strip()
        
        if not hash_str:
            self.client._print_warning(
                "[Trust] Alias target must be a full 32-character hash."
            )
            return
        if not alias:
            self.client._print_warning("[Trust] Alias cannot be empty.")
            return

        # Avoid two contacts resolving to the same alias.
        for other_hash, entry in self.contacts.items():
            if (
                other_hash != hash_str
                and str(entry.get("alias", "")).casefold() == alias.casefold()
            ):
                self.client._print_warning(
                    f"[Trust] Alias '{alias}' is already assigned to another hash."
                )
                return

        entry = self.contacts.get(hash_str)
        
        if entry is None:
            entry = {"level": "unverified", "note": "", "alias": "", "updated_at": 0}

        entry["alias"] = alias
        entry["updated_at"] = time.time()
        self.contacts[hash_str] = entry

        if self._save():
            self.client._print_success(
                f"[Trust] Local alias '{alias}' saved for {hash_str}."
            )


    def _remove(self, target):
        """Remove a contact's trust classification and save the changes."""
        hash_str, entry = self._get_entry(target)

        if not hash_str:
            return

        if entry is None:
            self.client._print_warning(
                "[Trust] No classification exists for this contact."
            )
            return

        del self.contacts[hash_str]

        if self._save():
            self.client._print_success(
                f"[Trust] Classification removed for "
                f"{self._display_name(hash_str)}."
            )


    def _show_stats(self):
        """Display the number of contacts for each trust level."""
        counts = {level: 0 for level in self.LEVELS}

        for entry in self.contacts.values():
            level = entry.get("level")
            if level in counts:
                counts[level] += 1

        print(self._color(
            f"★ Trusted:    {counts['trusted']}",
            self._level_color("trusted"),
            bright=True,
        ))
        print(self._color(
            f"◆ Known:      {counts['known']}",
            self._level_color("known"),
        ))
        print(self._color(
            f"○ Unverified: {counts['unverified']}",
            self._level_color("unverified"),
        ))
        print(self._color(
            f"Classified:   {sum(counts.values())}",
            "WHITE",
            bright=True,
        ))


    def _help(self):
        """Display Trust Manager commands and usage instructions."""
        self.client._print_color(
            """
Trust Manager commands
----------------------
trust list
trust list trusted
trust list known
trust list unverified
trust show <contact>
trust set <contact> <trusted|known|unverified>
trust note <contact> <text>
trust alias <full-hash> <local-alias>
trust remove <contact>
trust stats
trust help

Contact can be a full hash, a saved Trust Manager alias, or a name
known to LXMF-CLI's local/in-memory contact data. The plugin does not
initiate network lookups.
""",
            self.client.Fore.WHITE,
        )


    def _handle_list_command(self, remainder):
        """Handle the list command, optionally filtering by trust level."""
        value = remainder.strip().lower()

        if not value:
            self._list_contacts()
            return

        if value in self.LEVELS:
            self._list_contacts(value)
            return

        self.client._print_warning(
            "Usage: trust list [trusted|known|unverified]"
        )


    def _handle_show_command(self, action, remainder):
        """Handle the show command for a contact by alias or hash."""
        if not remainder or len(remainder.split()) != 1:
            self.client._print_warning(
                f"Usage: trust {action} <contact>"
            )
            return

        hash_str, entry = self._get_entry(remainder)

        if hash_str:
            self._show_entry(hash_str, entry)


    def _handle_set_command(self, remainder):
        """Set the trust level for a contact."""
        fields = remainder.rsplit(maxsplit=1) 
        if len(fields) != 2:
            self.client._print_warning(
                "Usage: trust set <contact> "
                "<trusted|known|unverified>"
            )
            return
            
        contact, level = fields
        self._set_level(contact, level.lower())


    def _handle_note_command(self, remainder):
        """Handle the note command for a contact."""
        fields = remainder.split(maxsplit=1)
        if len(fields) != 2:
            self.client._print_warning(
                "Usage: trust note <contact> <text>"
            )
            return
            
        contact, note = fields
        self._set_note(contact, note)


    def _handle_alias_command(self, remainder):
        """Handle the alias command for a contact."""
        fields = remainder.split(maxsplit=1)
        if len(fields) != 2:
            self.client._print_warning(
                "Usage: trust alias <full-hash> <local-alias>"
            )
            return
            
        hash_value, local_alias = fields
        self._set_alias(hash_value, local_alias)


    def _handle_remove_command(self, remainder):
        """Handle the removal command for a contact."""
        if not remainder or len(remainder.split()) != 1:
            self.client._print_warning("Usage: trust remove <contact>")
            return
            
        self._remove(remainder)
