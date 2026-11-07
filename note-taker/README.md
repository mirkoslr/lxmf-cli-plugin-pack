# Note Taker

The Note Taker is a plugin for [LXMF-CLI](https://github.com/fr33n0w/lxmf-cli) that lets you save and manage messages as personal notes.

It allows users to browse recent messages and conversations, save individual messages, organize saved notes, and add comments for additional context.

The plugin stores notes and comments locally in an SQLite database named `plugin.db` in the LXMF-CLI storage directory.

## Installation

Install the plugin according to the official [LXMF-CLI plugin management documentation](https://github.com/fr33n0w/lxmf-cli#plugin-management).

Copy `note_taker.py` into the `lxmf_client_storage/plugins/` directory used by your LXMF-CLI installation, then follow the official instructions to enable or reload it.

## Commands

Use `note help` inside LXMF-CLI to display the available commands.

### `note msg [count]`

Display recent messages from the message history.

```text
note msg
note msg 5
note msg 20
```

The command displays the last 10 messages by default. You can specify a different number to display more or fewer messages.

Each displayed message receives an index that can be used to save it as a note.

### `note msg list`

Display the available conversations with their assigned numbers.

```text
note msg list
```

Use this command to identify the conversation you want to browse.

### `note msg user <N>`

Display messages belonging to a specific conversation.

```text
note msg user 1
note msg user 3
```

Replace `<N>` with the conversation number shown by `note msg list`.

### `note save <N>`

Save a message from the currently displayed message list as a note.

```text
note msg 10
note save 3
```

In this example, the plugin displays the last 10 messages and saves the third message in the displayed list.

The message content and available metadata are stored in the database.

### `note save last`

Save the most recent inbound message as a note.

```text
note save last
```

This command is useful when you want to save the latest received message without browsing the message history.

### `note list`

Display all saved notes.

```text
note list
```

Notes are displayed with their assigned numbers, saved message information, and comment counts when available.

The displayed note numbers can be used by other commands to select a note.

### `note del <N>`

Delete a saved note.

```text
note del 2
```

Replace `<N>` with the note number shown by `note list`.

Deleting a note also deletes its associated comments.

### `note comment <N>`

Display the comments associated with a saved note.

```text
note comment 2
```

The command displays the comments for the selected note, numbered in the order they are shown.

### `note comment <N> <text>`

Add a comment to a saved note.

```text
note comment 2 Important information for later reference
```

The comment can contain multiple words and is stored together with its creation timestamp.

### `note comment del <N>`

Delete a comment from the currently displayed comment list.

```text
note comment 2
note comment del 1
```

First display the comments for a note using `note comment <N>`. Then use the displayed comment number to delete the selected comment.

### `note help`

Display the built-in command summary.

```text
note help
```

## Data storage

The plugin stores notes and comments in an SQLite database named `plugin.db` inside the LXMF-CLI storage directory.

The database contains two tables:

- `note_taker_notes` — stores saved notes, including message content, timestamps, direction, contact information, and other available metadata.
- `note_taker_comments` — stores comments associated with saved notes, including their creation timestamps.

Each comment references its parent note through a foreign key. When a note is deleted, its associated comments are automatically deleted through SQLite's `ON DELETE CASCADE` mechanism.

The database is managed locally by the plugin using Python's `sqlite3` module.

Keep a backup of `plugin.db` if you want to preserve your saved notes and comments when moving or reinstalling the LXMF-CLI storage directory.

## Limitations

- Notes and comments are stored locally and are not synchronized between LXMF-CLI installations.
- `note save <N>` refers to the currently displayed message list. Display the messages again before selecting a different message.
- `note save last` saves the most recent inbound message, not the most recent outbound message.
- Note and comment numbers refer to their current displayed lists. Run the corresponding list or display command again to refresh the numbering.
- Deleting a note permanently removes its associated comments.

## Project status

This plugin is part of the [LXMF-CLI Plugin Pack](../README.md).
