
# Kaomoji Plugin for LXMF-CLI

A lightweight plugin for browsing and sending Kaomoji using simple text shortcodes.

Kaomoji automatically replaces text-based shortcodes with their corresponding Unicode characters before messages are sent through LXMF-CLI.

## Features

- **21 standard Kaomoji:** A curated collection of text-based expressions.
- **Simple shortcodes:** Uses `%` as the shortcode delimiter.
- **Case-insensitive:** Shortcodes work regardless of capitalization.
- **Multiple replacements:** Supports multiple Kaomoji in a single message.
- **Unknown shortcode handling:** Unrecognized shortcodes are left unchanged.
- **Message integration:** Automatically processes message content.
- **Kaomoji picker:** Displays all available Kaomoji and their shortcodes.

## Available Kaomoji

| Kaomoji | Shortcode | Name |
|---|---|---|
| (^_^) | `%smile` | smile |
| (≧◡≦) | `%happy` | happy |
| ≧▽≦ | `%laugh` | laugh |
| (╥﹏╥) | `%cry` | cry |
| (｡•́︿•̀｡) | `%sad` | sad |
| (♥‿♥) | `%love` | love |
| (づ￣ ³￣)づ | `%hug` | hug |
| (⊙_⊙) | `%shock` | shock |
| (ಠ益ಠ) | `%angry` | angry |
| (－‸ლ) | `%facepalm` | facepalm |
| ¯\_(ツ)_/¯ | `%shrug` | shrug |
| (・_・ヾ | `%confused` | confused |
| ಠ_ಠ | `%nope` | nope |
| (╯°□°)╯︵ ┻━┻ | `%tableflip` | tableflip |
| (=^･ω･^=) | `%cat` | cat |
| ʕ•ᴥ•ʔ | `%bear` | bear |
| ( ´ ▽ `)ﾉ | `%hello` | hello |
| ٩(◕‿◕)۶ | `%party` | party |
| (｡•̀ᴗ-)✧ | `%wink` | wink |
| (◍•ᴗ•◍) | `%cute` | cute |
| ( •̀ᴗ•́ )و | `%thumbsup` | thumbsup |

## Usage

Kaomoji shortcodes can be used directly in messages. The plugin automatically replaces recognized shortcodes with their corresponding Unicode Kaomoji before the message is sent.

**Example:**

```text
s alice Hey %smile, how are you? %happy
```

The recipient receives:

```text
Hey (^_^), how are you? (≧◡≦)
```

Multiple Kaomoji can be used in the same message.

Shortcodes are case-insensitive, so `%smile`, `%SMILE`, and `%Smile` all produce the same result.

Unknown shortcodes are left unchanged.

### Browse Available Kaomoji

Type the following command to display the Kaomoji picker:

```text
kamoji
```

The picker displays all 21 available Kaomoji, their shortcodes, and their names.

## Implementation

Kaomoji integrates with LXMF-CLI through the existing `client.send_message()` API.

When the plugin is initialized, it:

1. Stores the currently installed `client.send_message()` method.
2. Installs a wrapper around the existing method.
3. Replaces recognized Kaomoji shortcodes in message content and titles.
4. Passes the processed message to the previously installed method.

The plugin does not handle message transport, addressing, or delivery. It only transforms text before passing it to the existing LXMF-CLI messaging functionality.

### Compatibility with Other Plugins

Kaomoji uses `%` as its shortcode delimiter, while the Emoji plugin uses `$`. This allows both plugins to process their respective shortcodes without conflicting over the delimiters.

The wrapper approach also allows Kaomoji to work alongside other plugins that wrap `client.send_message()`, provided their wrappers are installed and chained correctly.

## Plugin Reloading

LXMF-CLI manages plugin loading and reloading. Testing confirmed that unloading a plugin through the Plugin Manager does not remove its wrapper from `client.send_message()`.

As a result, previously installed wrappers remain active even after their corresponding plugins have been unloaded.

When plugins are loaded again, new wrappers may be added on top of existing ones.

This may result in:

- Multiple wrapper layers being retained after repeated reloads.
- Old plugin instances remaining referenced by previously installed wrappers.
- Unloaded plugins continuing to process messages through their previously installed wrappers.

This is a plugin lifecycle management issue in LXMF-CLI, rather than a limitation of Kaomoji's shortcode replacement logic.

**Recommended usage:** Start LXMF-CLI normally and load the plugins once. If you need to reload plugins, restarting LXMF-CLI provides a clean starting point.

## Design Principles

Kaomoji follows a few simple principles:

- **Lightweight:** No database, external dependencies, or additional services.
- **Focused:** Only transforms message content and titles.
- **Compatible:** Uses the existing LXMF-CLI `client.send_message()` API.
- **Composable:** Uses `%` as a dedicated shortcode delimiter, allowing it to coexist with other text-processing plugins such as Emoji.

## License

See the repository license for details.
