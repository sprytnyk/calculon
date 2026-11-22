# Calculon

[![Latest release](https://img.shields.io/github/v/release/sprytnyk/calculon?label=release)](https://github.com/sprytnyk/calculon/releases/latest)
[![Platforms: Linux, Windows, and macOS](https://img.shields.io/badge/platform-Linux%2C_Windows%2C_macOS-blue)](#install)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
![Made in Ukraine](https://img.shields.io/badge/made_in-Ukraine-ffd700.svg?labelColor=0057b7)
[![Linux test coverage](https://codecov.io/gh/sprytnyk/calculon/branch/main/graph/badge.svg)](https://codecov.io/gh/sprytnyk/calculon)
![AI Generated](https://img.shields.io/badge/AI-generated-orange)

A notepad that calculates as you type. Write lines with money, units and dates, and see
the answers beside each line. Try `$19 for breakfast + $22 for the Uber` to get `$41.00`.
Most sheets that use [Soulver's syntax](https://documentation.soulver.app/) work in Calculon too.

<picture>
  <source media="(prefers-color-scheme: light)" srcset="docs/demo-light.gif">
  <img src="docs/demo.gif" alt="A trip budget in Calculon with answers beside each line, shown in Glacier and Ember">
</picture>

## Features

- Mix words and maths in a line. Try `20% off $80`, `10 km in miles` or `today + 3 weeks`.
- Reuse earlier answers and name subtotals. Write `housing =` on its own to give the
  subtotal above it a name.
- The bottom bar adds results from the whole sheet, including subtotals. It adds
  money if there is any. Otherwise, it adds results with the most common kind of
  unit, or plain numbers if there are no units.
- Start a list item with `1.`, `1)` or `•`. Calculon skips the list marker. It also reads
  line references from Soulver exports, such as `[$1 000,00](line2)`.
- The results pane shortens large answers, for example to `$386.8M`. Click the answer
  to copy the full number.
- Start a trip with `@from` and add a duration for each stay or leg to see when it ends.
  Use `@to` to see how much time is left before a date. These commands are specific to
  Calculon. Soulver sets the trip's start and end in its interface.
- Convert about 160 currencies with daily exchange rates.
- Write in English or Ukrainian. The app menus and messages are available in both languages.
- Organise sheets in directories, pin the ones you use often, and restore deleted sheets
  from Trash.
- Choose Glacier or Ember, then choose light mode, dark mode or the system setting.
  Glacier is the default.
- Use Focus Mode in the View menu to hide the sidebar, menu bar and rates date. Press
  <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>F</kbd> or
  <kbd>Cmd</kbd>+<kbd>Shift</kbd>+<kbd>F</kbd> on macOS. The macOS menu bar remains at the
  top of the screen. The View menu also has Always on Top.
- Turn on Vim mode in Settings to use Normal, Insert and Visual modes. Calculon uses
  [side-vim](https://github.com/sprytnyk/side-vim). In Normal mode, press
  <kbd>Ctrl</kbd>+<kbd>O</kbd> and <kbd>Ctrl</kbd>+<kbd>I</kbd> to go back and forward
  through the sheets you opened.

> [!TIP]
> Open the Help sheet in the sidebar for worked examples. Choose Keyboard Shortcuts in the
> Help menu to see the keys, including Vim shortcuts when the mode is on.

| Action | Windows / Linux | macOS |
| --- | --- | --- |
| Open the help sheet | <kbd>F1</kbd> | <kbd>Cmd</kbd>+<kbd>Shift</kbd>+<kbd>H</kbd> |
| Open keyboard shortcuts | <kbd>Shift</kbd>+<kbd>F1</kbd> | <kbd>Cmd</kbd>+<kbd>Shift</kbd>+<kbd>K</kbd> |

In Vim mode, press `d` in the sidebar to move a sheet or directory to Trash. Select an item
you moved to Trash and press `r` to restore it or `d` to delete it permanently. To empty
Trash, select Trash itself and press `d`.

> [!CAUTION]
> Deleting an item from Trash or emptying Trash can't be undone.

## Calculon, Soulver and Numi

|            | Calculon                                | Soulver 4                             | Numi                                              |
| ---------- | --------------------------------------- | ------------------------------------- | ------------------------------------------------- |
| Platforms  | Linux, Windows, macOS                   | macOS, iPhone, iPad                   | macOS, Windows, Linux, command line               |
| Price      | Free                                    | $59 once, 60-day free trial           | Free with limits, paid licence once               |
| Setapp     | No                                      | Yes                                   | Yes                                               |
| Licence    | MIT, open source                        | Proprietary                           | Proprietary                                       |
| Languages  | English, Ukrainian, in sheets and menus | 9, in sheets too, mixed with English  | 8, docs show sheets in English only, no Ukrainian |
| Variables  | Any letters, as in `оренда = 2400`      | Words and phrases, letters not stated | No spaces or special characters                   |
| Currencies | About 160, daily rates                  | 190, stocks with a paid data plan     | Yes                                               |
| Sync       | Plain files, any tool                   | iCloud                                | iCloud with a paid licence                        |
| CLI        | No                                      | Yes                                   | Yes, without dates or variables                   |

Prices and features are from [soulver.app](https://soulver.app), the
[SoulverCore README](https://github.com/soulverteam/SoulverCore) and Numi's own site
and docs in November 2026.

## Numbers, dates and times

The default number format is `1,234.56`. The format you choose in Settings applies
to both input and answers, regardless of the interface language.

You can group digits in threes or leave them ungrouped. Formats that use spaces
accept ordinary and non-breaking spaces. You can omit the leading zero in a decimal,
as in `.5` or `,5`.
Use semicolons between list items and function arguments, as in `total of 10; 20; 30`
and `round(1234; 2)`.

Write numeric dates as `YYYY-MM-DD`, including in ranges such as
`2026-11-18 to 2026-11-20`. Add a time after a space, as in `2026-11-18 15:00`.
If a calculation looks like a date, put spaces around its operators, as in `18 / 11 / 2026`.
You can write `18 Jan 2026` or `January 18, 2026`. Leave out the year to use the current year.
Calculon shows times in 24-hour format by default. Choose 12-hour display in Settings.

Hover over a red underline or a red `!` in the results pane to see the warning.
In Vim Normal mode, press `K` to show or hide the warning at the cursor.

> [!IMPORTANT]
> Changing the number format recalculates the open sheet and keeps its text intact.
> In older sheets, you may need to update numbers, replace commas between arguments
> or list items with semicolons, and rewrite dates in formats such as `18/11/2026`.

## Install

Download the archive for your system from [Releases](https://github.com/sprytnyk/calculon/releases)
and unpack it. Calculon runs on Linux and Windows x64 and on Intel and Apple Silicon Macs.

- **Linux.** Run `./calculon`.
- **Windows.** Run `calculon.exe`.
- **macOS.** Pick `macos_arm64` for Apple Silicon or `macos_x64` for Intel, and drag
  `Calculon.app` into Applications.

> [!WARNING]
> The builds aren't code-signed or notarized, so the first start takes an extra step.
>
> - **Windows.** SmartScreen may ask you to confirm. Click More info, then Run anyway.
> - **macOS.** macOS blocks the app. Try to open it, then go to System Settings, open
>   Privacy & Security and click Open Anyway. Or run
>   `xattr -dr com.apple.quarantine /Applications/Calculon.app`.

> [!TIP]
> Use the signed checksums to verify the download.
>
> ```bash
> gpg --verify SHA256SUMS.asc SHA256SUMS && sha256sum --ignore-missing -c SHA256SUMS
> ```

## Sheets

On first start, Calculon asks where to keep your sheets and suggests
`~/Documents/Calculon`. Each sheet is a plain `.txt` file in that directory. You can pick
another directory later in Settings.

The sidebar shows directories on disk. Use your usual tools to sync,
search or back up your sheets. Calculon keeps pins and the custom sort order in
`.calculon.json` and moves deleted items to `.trash/`. It skips links and Windows
junctions such as `My Music` in Documents.

Calculon creates the directory if needed and writes a test file. If that fails, it asks
you to choose another directory. On Windows, Controlled folder access can block the
test. Allow Calculon in Windows Security or choose a directory outside Documents.

> [!WARNING]
> If Calculon can't save, it keeps your edits open. Save them before closing the window,
> switching sheets or changing the sheets directory. On Windows, Calculon retries brief
> file-access errors before reporting them.

If the file changed on disk while you were editing, choose Save a copy. Calculon saves
your edits to a new sheet in the same directory and opens it.

## Exchange rates

Calculon downloads rates once a day from [open.er-api.com](https://open.er-api.com).
If that fails, it tries [Frankfurter](https://frankfurter.dev) for European Central Bank
rates. When you're offline, Calculon uses the last rates it saved or the rates that came
with the app on first launch.
If a sheet total needs a rate Calculon doesn't have, the status bar names the currency.

To use another source, enter its URL on the Exchange Rates page in Settings. The URL
must return JSON in this format.

```json
{"base": "USD", "rates": {"EUR": 0.92, "UAH": 41.3, "GBP": 0.79}}
```

- Set `base` or `base_code` to the currency the rates use as their base. Calculon defaults to USD.
- In `rates`, give the amount of each currency that one unit of the base currency buys.
- Write currency codes as three ASCII letters, such as `EUR`. Calculon rejects a reply
  with any other code.
- To show when rates last changed, include `time_last_update_unix` in seconds or `date`
  in `YYYY-MM-DD` format. Calculon rejects a reply with a timestamp it can't read, so
  fix it or leave it out.
- Calculon follows a redirect only if it keeps the same protocol, host and port. A
  redirect from `http://` to `https://` fails, so enter the final URL.
- The reply must be 2 MB or less and arrive within 15 seconds.

You can use the URL of your own Frankfurter server.

> [!NOTE]
> Calculon goes online to get rates. When you open About, it checks GitHub for a new
> version.

## Spell check

Choose Check Spelling in the View menu or turn it on in Settings. Calculon draws a wavy line
under misspelled words. Right-click one for suggestions, Add to Dictionary or Ignore.
It skips numbers, units, currencies and variable names, and checks only the words
around them. Words you add go to `words.txt` in Calculon's settings directory, one per
line: `~/.config/sprytnyk.dev/Calculon` on Linux,
`~/Library/Application Support/sprytnyk.dev/Calculon` on macOS and
`%AppData%\sprytnyk.dev\Calculon` on Windows. If you used an older Calculon, it keeps
using your old files. On Linux, `words.txt` stays in `~/.local/share/sprytnyk.dev/Calculon`.

Calculon uses Hunspell on Linux and macOS and the built-in spell checker on Windows.
It uses your system's dictionaries for English and Ukrainian.

**Linux.** On Debian and Ubuntu:

```bash
sudo apt install libhunspell-1.7-0 hunspell-en-us hunspell-uk
```

Other Linux distributions may use different package names. Calculon looks for
dictionaries in `/usr/share/hunspell`, `/usr/share/myspell`, `~/.local/share/hunspell`
and any directory in `$DICPATH`.

**macOS.** Install Hunspell with [Homebrew](https://brew.sh), then put the dictionaries
in `~/Library/Spelling`:

```bash
brew install hunspell
mkdir -p ~/Library/Spelling && cd ~/Library/Spelling
base=https://raw.githubusercontent.com/LibreOffice/dictionaries/master
curl -LO $base/en/en_US.aff -LO $base/en/en_US.dic
curl -LO $base/uk_UA/uk_UA.aff -LO $base/uk_UA/uk_UA.dic
```

**Windows.** Calculon uses the spell checker built into Windows. Windows has a dictionary
for each language added in Settings > Time & language > Language & region. Most systems
have English already. Add Ukrainian there if you write in it.

> [!TIP]
> The Spell Check page in Settings and `calculon --self-test` show which dictionaries
> Calculon found and how to install any that are missing.

## Develop

Calculon uses PySide6. Install [uv](https://docs.astral.sh/uv/) to set up the project.
It reads the Python version from `.python-version`.

```bash
uv sync                 # install dependencies
uvx pre-commit install  # ruff and file checks before each commit
make run                # start the app
make check              # ruff and pytest
make build              # dist/calculon, or dist/Calculon.app on macOS (test version)
make icons              # remake assets/icon.png, .ico and .icns from icon-source.png
make site               # remake the website's example sheets and colours in docs/
make docs               # serve the website from docs/ at http://127.0.0.1:8000
make gif                # remake the dark and light demos and screenshots (needs ffmpeg)
```

Run `dist/calculon --self-test` to check a build. It works out every help sheet example,
which covers unit data, time zones and exchange rates, then checks the fonts, icons and Qt
translations. It also tests spell check if one is installed. On macOS, run
`dist/Calculon.app/Contents/MacOS/calculon --self-test`.

The calculator engine is in `calculon/engine/` and runs without Qt.

On each push to `main`, GitHub Actions runs the Linux test suite and updates the
coverage badge. The test log lists the 15 slowest setup, test or cleanup steps.

GitHub Pages serves the website from `docs/` on `main`. The engine generates the website's
example answers. The site test checks that those answers are up to date.

## Release

Pushing a `vX.Y.Z` tag starts the *Release builds* workflow. It runs the checks and builds
Linux x64 and Windows x64 binaries and `Calculon.app` for macOS x64 and arm64. The macOS
job installs Hunspell and checks that both dictionaries work. The Windows job tests the
built-in spell checker.

The workflow takes the version from the tag and uploads the builds with `SHA256SUMS`.
See the `release` skill in `.claude/skills/release/` for signing the tag and checksums,
writing release notes and publishing a release on GitHub.

## License

Calculon's code uses the MIT license. Fira Code uses the SIL Open Font License in
`assets/fonts/OFL.txt`. The menu and sidebar use [Phosphor Icons](https://phosphoricons.com)
under the MIT license in `assets/icons/LICENSE.txt`.

> [!IMPORTANT]
> The app icon uses the *Futurama Calculon* vector logo from seeklogo.com. It comes with
> no license grant. See `assets/ICON-LICENSE.txt` for the credit to Matt Groening and Comedy
> Central. For anything beyond personal use, use the MIT-licensed robot in
> `assets/robot-icon.svg`.
