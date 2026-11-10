# Calculon

A notepad that calculates as you type. Write plain lines with numbers, money, units and
dates, and the answers show up in a column on the right. The syntax follows
[Soulver's](https://documentation.soulver.app/), so a sheet from one works in the other.

Runs on Linux, Windows and macOS (Intel and Apple Silicon). Built with PySide6.

![Calculon with a trip budget sheet: the lines on the left, their answers on the right](docs/screenshot.png)

## Features

- Lines mix words and maths: `$19 for breakfast + $22 for the uber`, `20% off $80`,
  `100 EUR in USD`, `10 km in miles`, `today + 3 weeks`
- Variables, totals of the lines above, and answers from earlier lines
- About 160 currencies, with rates updated daily
- English and Ukrainian, in sheets and in the interface
- Sheets in folders, with search, pins and a trash
- Dark, light or system theme

The **Help** sheet in the sidebar (F1) shows everything with live examples. Help →
Keyboard Shortcuts lists the keys.

## Sheets

Each sheet is a plain `.txt` file in `~/Documents/Calculon` (change it in Settings).
Folders are real folders, so the sheets work with any sync tool, `grep` or backups.
Calculon keeps pins and custom order in a hidden `.calculon.json` in that folder.
Deleted sheets go to `.trash/` until you empty the trash.

## Exchange rates

Calculon downloads rates once a day from [open.er-api.com](https://open.er-api.com).
If that fails, it uses [Frankfurter](https://frankfurter.dev), which publishes the
European Central Bank's rates. It keeps the last rates for offline use. A snapshot ships with the app, so currencies work on the first
start without a network.

You can point Calculon at your own source in **Settings → Exchange Rates**. The URL must
return JSON like this:

```json
{"base": "USD", "rates": {"EUR": 0.92, "UAH": 41.3, "GBP": 0.79}}
```

- `base`: the currency the rates are relative to (`base_code` also works; defaults to USD)
- `rates`: how many units of each currency one unit of `base` buys
- optional: `time_last_update_unix` (seconds) or `date` (`YYYY-MM-DD`) for the "updated" label

A self-hosted Frankfurter works as is. The only network requests Calculon makes are for
exchange rates.

## Install

Download the archive for your system from the
[releases](https://github.com/sprytnyk/calculon/releases) page and unpack it.

- **Linux.** run `./calculon`.
- **Windows.** run `calculon.exe`. The build isn't code-signed, so SmartScreen may ask
  you to confirm the first start (More info → Run anyway).
- **macOS.** pick `macos_arm64` for Apple Silicon, `macos_x64` for Intel, and drag
  `Calculon.app` into Applications. The app isn't notarized, so macOS blocks it the first
  time. Try to open it, then go to System Settings, open Privacy & Security and click Open
  Anyway. Or run `xattr -dr com.apple.quarantine /Applications/Calculon.app`.

Check a download against the signed checksums:

```bash
gpg --verify SHA256SUMS.asc SHA256SUMS && sha256sum --ignore-missing -c SHA256SUMS
```

## Develop

Needs [uv](https://docs.astral.sh/uv/). Python 3.14 is picked from `.python-version`.

```bash
uv sync                 # install dependencies
uvx pre-commit install  # ruff and file checks before each commit
make run                # start the app
make check              # ruff and pytest
make build              # dist/calculon, or dist/Calculon.app on macOS (test version)
make icons              # remake assets/icon.png, .ico and .icns from icon-source.png
```

`dist/calculon --self-test` checks that a build has everything it needs (unit data, time
zones, help sheets, fonts, rates snapshot). On macOS, run
`dist/Calculon.app/Contents/MacOS/calculon --self-test`.

The calculator engine in `calculon/engine/` has no Qt in it; `tests/test_engine.py` has
the examples from Soulver's documentation as tests.

## Release

Pushing a `vX.Y.Z` tag runs the *Release builds* workflow. It runs the checks, then
builds Linux x64 and Windows x64 binaries and a `Calculon.app` for macOS x64 and arm64.
It keeps them as a run artifact with `SHA256SUMS`. The version comes from the tag, and there is no version file. The `release`
skill in `.claude/skills/release/` does the rest: the signed tag, the signed checksums,
the release notes and the GitHub release.

## License

MIT. Fira Code is under the SIL Open Font License (`assets/fonts/OFL.txt`). The menu and
sidebar icons are [Phosphor Icons](https://phosphoricons.com) under the MIT license
(`assets/icons/LICENSE.txt`).

The app icon is **not** MIT: it is Calculon from the *Futurama Calculon* vector logo on
seeklogo.com, which comes with no license grant; the character is © Matt Groening /
Comedy Central (`assets/ICON-LICENSE.txt`). For anything beyond personal use, swap it
for `assets/robot-icon.svg`, the original robot artwork, which is MIT like the rest.
