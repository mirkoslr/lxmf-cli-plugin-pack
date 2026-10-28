# Trust Manager

The Trust Manager is a plugin for [LXMF-CLI](https://github.com/fr33n0w/lxmf-cli) that lets you maintain local classifications and information about contacts.

It supports three trust levels:

- **`trusted`** — a contact you have explicitly marked as trusted.
- **`known`** — a contact you recognize.
- **`unverified`** — a contact whose trust level has not been established.

You can also save a note and a local alias for a contact. The plugin stores this information in `trust_manager.json` in the LXMF-CLI storage directory.

> **Important:** Trust levels are personal labels only. They do not verify a contact's identity, guarantee that messages are safe, or enforce access control. The plugin does not intercept messages or initiate network lookups.

## Installation

Install the plugin according to the official [LXMF-CLI plugin management documentation](https://github.com/fr33n0w/lxmf-cli#plugin-management).

Copy `trust_manager.py` into the `lxmf_client_storage/plugins/` directory used by your LXMF-CLI installation, then follow the official instructions to enable or reload it.

## Commands

Use `trust help` inside LXMF-CLI to display the available commands.

### `trust list`

List all contacts that have a saved Trust Manager classification.

```text
trust list
```

You can filter the list by trust level:

```text
trust list trusted
trust list known
trust list unverified
```

The list displays each contact's trust level and saved note, if present.

### `trust show <contact>`

Display the contact's hash, display name, trust level, note, and last update time when available.

```text
trust show home-node
trust show 123456789abcdef0123456789abcdef0
```

The contact can be identified by a full destination hash, a saved Trust Manager alias, or a name resolvable through LXMF-CLI's local contact data. The `show` command accepts a single contact token, so use an alias without spaces.

If the contact has no saved classification, the plugin displays it as unverified by default; this does not create a saved record.

### `trust set <contact> <level>`

Set or update a contact's trust level.

```text
trust set home-node trusted
trust set work-node known
trust set abcdef0123456789abcdef0123456789 unverified
```

Valid levels are `trusted`, `known`, and `unverified`.

When a contact is specified by a name rather than a hash and has no saved alias, the plugin uses that name as the local alias. Existing notes and aliases are preserved when changing the trust level.

### `trust note <contact> <text>`

Save a note for a contact. The note can contain multiple words.

```text
trust note home-node Main contact for my home node
```

The contact argument must be a single token. A note can also be saved for a resolvable contact that does not yet have a Trust Manager record; the plugin creates an `unverified` record for it.

### `trust alias <full-hash> <local-alias>`

Assign a local alias to a full 32-character hexadecimal destination hash.

```text
trust alias 123456789abcdef0123456789abcdef0 home-node
```

The alias is stored locally and can be used in other Trust Manager commands that accept a contact name. Aliases are matched without regard to letter case, and the plugin rejects empty aliases and aliases already assigned to another contact. The alias command requires the full hash, not an existing alias.

### `trust remove <contact>`

Remove a contact's Trust Manager record, including its saved trust level, note, and alias.

```text
trust remove home-node
```

This removes only the local Trust Manager record. It does not remove the contact from LXMF-CLI or delete the contact's identity. The contact argument must be a single token.

### `trust stats`

Show the number of saved contacts in each trust level and the total number of classified contacts.

```text
trust stats
```

### `trust help`

Display the built-in command summary.

```text
trust help
```

## Data storage

The plugin stores records in `trust_manager.json` inside the LXMF-CLI storage directory. Each record is keyed by a normalized destination hash and may contain:

- `level` — the trust level.
- `note` — a user-defined note.
- `alias` — a local display alias.
- `updated_at` — the timestamp of the last update.

The plugin loads this file when initialized and saves changes locally. Keep a backup of the file if you want to preserve your classifications when moving or reinstalling the LXMF-CLI storage directory.

## Limitations

- Classifications are local to this LXMF-CLI installation and its storage data.
- Trust labels are not cryptographic verification and do not affect message delivery or permissions.
- Contact-name resolution uses LXMF-CLI's available local contact data; the plugin does not initiate network lookups.
- `trust show`, `trust note`, and `trust remove` expect the contact argument to be a single token. Use a short alias without spaces for convenient command use.

## Project status

This plugin is part of the [LXMF-CLI Plugin Pack](../README.md).
