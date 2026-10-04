# Raycast Script Commands

Alfred workflow that runs [Raycast script commands](https://github.com/raycast/script-commands) you already have. The scripts stay as they are.


## Install

Download `Raycast Script Commands.alfredworkflow` from Releases, or take `dist/Raycast Script Commands.alfredworkflow` from this repository. Double-click the file and Alfred imports it.

## Setup

Open **Configure Workflow…** and set **Script directories**. The value is a colon-separated list of folders. The default is `~/raycast-scripts`.

`examples/` in this repository has two inline commands, a clock and a public-IP check. Point **Script directories** at that folder, or copy the scripts into `~/raycast-scripts`, to try the workflow before adding your own.

Scripts should be executable and start with a shebang. The runner also accepts a shebang on a file that is not marked executable.

## Usage

| Key | Action |
| --- | --- |
| `rsc` | List every discovered command |
| type | Filter the list by title |
| Return on an inline command | Refresh it now and reopen `rsc` |
| Return on silent or compact | Run it and show the last output line in a notification |
| Return on full output | Run it and show the output in Large Type |
| Command-C | Copy the row |

Inline rows show the latest value as the title. The subtitle shows the command name and `updated Ns ago`, `refreshing`, or `⚠` plus the error. The list refreshes about once a second while it is open, so values move without another keypress.

Commands that declare `@raycast.argument1` are listed and marked unsupported. This version does not prompt for arguments.

## How it works

The Script Filter walks each folder in `script_dirs` and reads `# @raycast.*` headers (a `//` comment works too). It uses `title`, `mode`, `refreshTime`, `packageName`, and `icon` when the icon is an emoji.

| Mode | Return does this |
| --- | --- |
| `inline` | Shows the first non-empty line of stdout. The value is cached in `$alfred_workflow_cache` for `refreshTime` (60 seconds when the header is absent). A detached process refreshes it under a lock. Return runs that refresh in the foreground and opens Alfred on `rsc` again. |
| `silent`, `compact` | Runs the script and posts the last non-empty line as a notification. |
| `fullOutput` | Runs the script and shows the output in Large Type. |

Each run uses the script's own directory as the working directory, a 30 second timeout, and a `PATH` that includes `/opt/homebrew/bin` and `/usr/local/bin`. ANSI color sequences are stripped from the output.

`bash tools/package.sh` writes `dist/Raycast Script Commands.alfredworkflow`.

## Privacy

Alfred runs this workflow on your Mac. It reads the folders you configured and runs those scripts locally. A script reaches the network only when the script itself does. This workflow does not add its own network calls.

## Requirements

- Alfred 5 with the Powerpack
- macOS
- `/usr/bin/python3`
- Raycast script commands on disk. Raycast itself does not have to be installed.

## License

MIT. See [LICENSE](LICENSE).
