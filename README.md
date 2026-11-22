# Raycast Script Commands

Alfred workflow that runs [Raycast script commands](https://github.com/raycast/script-commands) you already have, in a native Alfred UI panel. The scripts stay as they are.

> **Version 2 needs Alfred 6.** It is built on Alfred UI, which Alfred 5 doesn't have. On Alfred 5, use [v1.0.0](https://github.com/aliafshany/alfred-raycast-script-commands/releases/tag/v1.0.0).


## Install

Download `Raycast Script Commands.alfredworkflow` from Releases, or take `dist/Raycast Script Commands.alfredworkflow` from this repository. Double-click the file and Alfred imports it.

## Setup

Open **Configure Workflow…** and set **Script directories**. The value is a colon-separated list of folders. The default is `~/raycast-scripts`.

`examples/` in this repository has two inline commands, a clock and a public-IP check. Point **Script directories** at that folder, or copy the scripts into `~/raycast-scripts`, to try the workflow before adding your own.

Scripts should be executable and start with a shebang. The runner also accepts a shebang on a file that is not marked executable.

## Usage

| Key | Action |
| --- | --- |
| `rsc` | Open the panel: every discovered command on the left, the selected one on the right |
| type | Filter the list by title |
| ↑ ↓ | Select a command; the right side shows its mode, status and latest output |
| Return | Run the selected command; its output appears in the panel |
| Command-Return | Copy the output and close |
| Command-R | Reload the list (new scripts, fresh inline values) |

Inline commands show their latest cached value under the name. Return on one refreshes it now. Silent and compact commands show their last output line; full-output commands show everything.

Commands that declare `@raycast.argument1` are listed and marked unsupported. This version does not prompt for arguments.

## How it works

The Script Filter walks each folder in `script_dirs` and reads `# @raycast.*` headers (a `//` comment works too). It uses `title`, `mode`, `refreshTime`, `packageName`, and `icon` when the icon is an emoji.

| Mode | Return does this |
| --- | --- |
| `inline` | Shows the first non-empty line of stdout. The value is cached in `$alfred_workflow_cache` for `refreshTime` (60 seconds when the header is absent). A detached process refreshes it under a lock. Return runs that refresh in the foreground and shows the new value. |
| `silent`, `compact` | Runs the script and shows the last non-empty line. |
| `fullOutput` | Runs the script and shows all of its output. |

The panel lives in `rsc.alfredui`; its backend, `rsc.alfredui/panel`, imports `rsc.py` for discovery, caching and running.

Each run uses the script's own directory as the working directory, a 30 second timeout, and a `PATH` that includes `/opt/homebrew/bin` and `/usr/local/bin`. ANSI color sequences are stripped from the output.

`bash tools/package.sh` writes `dist/Raycast Script Commands.alfredworkflow`.

## Privacy

Alfred runs this workflow on your Mac. It reads the folders you configured and runs those scripts locally. A script reaches the network only when the script itself does. This workflow does not add its own network calls.

## Requirements

- Alfred 6 with the Powerpack (Alfred UI)
- macOS
- `/usr/bin/python3`
- Raycast script commands on disk. Raycast itself does not have to be installed.

## License

MIT. See [LICENSE](LICENSE).
