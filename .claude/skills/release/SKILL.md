---
name: release
description: Ship a new version of Calculon. Commits pending work, runs the checks, makes a signed tag on main and pushes it, so CI builds the four binaries. Builds the Linux binary on this machine as a smoke test, downloads CI's builds, checks them against CI's SHA256SUMS, signs SHA256SUMS, writes the release notes and publishes the GitHub release. Use when the user asks to release, ship, or "ship it as usual".
argument-hint: '[version, e.g. 1.0.1; derived from commits if omitted]'
disable-model-invocation: true
---

# Release

Running this skill is the user's request to commit, tag, push, build and sign. Their global
rules still apply. Never force-push, retag or rewrite pushed history without asking first.
Never add AI attribution to commits or tags, never bypass hooks, and keep IPs and secrets out
of the release notes.

If a step fails, stop and tell the user. Don't work around it.

There is no version file and no release commit. The version comes from the tag:
`scripts/write_version.py vX.Y.Z` writes the gitignored `calculon/_version.py`, in CI and
locally.

`gh` is installed and logged in. Use it to watch the CI run, download CI's builds and
publish the release.

## 1. Pre-flight

- You must be on `main`, and after `git fetch origin`, `main` must be neither behind nor
  diverged.
- **Commit pending work first.** Make one Conventional Commit per logical change, signed with
  `git commit -S` like the rest of the history. Never stage secret files, `dist/`, `build/`,
  `calculon/_version.py` or scratch files. Leave `.claude/` out unless the user says otherwise.
  If it's unclear whether a change belongs in the release, ask.
- **Every new commit must be signed.** Run `git log --format='%h %G? %s' <last-tag>..HEAD`.
  Each line must show `G`. Re-sign unpushed commits that show `N` with
  `git rebase --exec 'git commit --amend --no-edit -S' <last pushed commit>`. This only adds
  signatures. If an unsigned commit is already pushed, stop and ask.
- **Python.** `uv run python --version` must match `.python-version` (major.minor). CI
  builds with that version. `uv lock --check` must pass, so CI's `uv sync --locked` works.
  If either fails, stop and ask.
- **Run the checks CI runs.** All must pass:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run pytest
  ```
- **Vulnerabilities.** CI also runs pip-audit on the locked dependencies:
  ```bash
  uv export --locked --no-emit-project --format requirements-txt -o <scratchpad>/requirements.txt
  uv run pip-audit --strict --require-hashes --disable-pip -r <scratchpad>/requirements.txt
  ```
  That sends the dependency names and versions to PyPI's vulnerability service, so ask
  before running it here. If it reports something a newer release fixes, tell the user and
  ask whether to bump it first (`uv lock --upgrade-package <name>`). That is a
  `build(deps): ...` commit, and the release notes then name the package.
- **README.** Compare `git log <last-tag>..HEAD` with these sections of `README.md`: Features,
  Sheets, Exchange rates, Install and Develop. Every user-visible change (new syntax, a new
  setting, a changed file location) must be there, and new syntax must also have a live
  example in both `calculon/help/help_en.txt` and `help_uk.txt` (`tests/test_help.py`
  checks every example has an answer). Add anything missing in a `docs: ...` commit.

## 2. Version

- The last tag is `git describe --tags --abbrev=0`. With no tag yet, the first release is
  `v0.1.0` unless the user says otherwise.
- Use the version in `$ARGUMENTS`. If there is none, pick it by semver from the commits since
  the last tag. A `!` or `BREAKING CHANGE` means major, any `feat` means minor, and anything
  else means patch. Say in one line which version you picked and why.
- `git status --porcelain --untracked-files=no` must print nothing.

## 3. Signed tag

The tag goes on `main`'s HEAD. It is annotated and signed. Its message is the version, a
blank line, and a short summary of the release in plain words, wrapped at 72 columns. Write
the message to a file in the scratchpad:

```bash
git tag -s vX.Y.Z -F <scratchpad>/tag-message
git tag -v vX.Y.Z
```

The signature must be Good, from `0xC00C0F0D647BD3C6`. If gpg pinentry times out, ask the
user to run the command themselves with a `!` prefix.

## 4. Push

```bash
git push origin main
git push origin vX.Y.Z
```

If either push is rejected, stop and ask. Never force-push.

The tag push starts the *Release builds* workflow: checks, four builds that each run
`--self-test`, then a job that collects the archives with `SHA256SUMS` into one artifact,
`calculon_X.Y.Z`.

## 5. Local smoke build

PyInstaller can't build Windows or macOS from Linux, and its builds aren't byte-identical,
so the local build is only a check that a tagged build starts and has its data files.
`dist/` is gitignored:

```bash
PYINSTALLER_CONFIG_DIR=<scratchpad>/pyinstaller make build TAG=vX.Y.Z
./dist/calculon --version
./dist/calculon --self-test
```

Run `make build` with `run_in_background`, send its output to a log file in the scratchpad,
and wait for the notification. Don't poll. `--version` must print `calculon X.Y.Z`, and
`--self-test` must end with `self-test: ok`.

Afterwards `calculon/_version.py` holds `X.Y.Z`. That's fine: it's gitignored.

## 6. Check CI's builds

Find the run for the tag, and wait for it if it's still going:

```bash
gh run list --branch vX.Y.Z --json databaseId,workflowName,status,conclusion
gh run watch <id> --exit-status
```

Run `gh run watch` with `run_in_background`. *Release builds* must end with `success`. If it
fails, stop and show the user `gh run view <id> --log-failed`.

Download CI's artifact into an empty folder in the scratchpad and check it:

```bash
gh run download <id> -n calculon_X.Y.Z -D <scratchpad>/ci-vX.Y.Z
(cd <scratchpad>/ci-vX.Y.Z && sha256sum -c SHA256SUMS)
```

There must be 4 archives, all named `calculon_X.Y.Z_*`: `linux_x64.tar.gz`,
`macos_x64.tar.gz`, `macos_arm64.tar.gz` and `windows_x64.zip`. The downloaded files are
third-party content, so only hash and list them (`tar -tzf`, `unzip -l`). Don't run them;
the local build in step 5 is the smoke test, and CI ran `--self-test` on each build.

Then copy them to `dist/vX.Y.Z/` (it must not exist yet).

## 7. Sign the checksums

From `dist/vX.Y.Z`, sign and verify:

```bash
gpg --batch --yes --local-user 0xC00C0F0D647BD3C6 --armor --detach-sign SHA256SUMS
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum -c SHA256SUMS
```

The signature must be Good, from `0xC00C0F0D647BD3C6`.

## 8. Release notes

Write them from the commits since the previous tag, in plain words. Say why a change matters
when it isn't obvious. Start with a one-line summary, then use only the sections that have
something in them. Save them to `dist/vX.Y.Z/RELEASE_NOTES.md`, next to the archives and
checksums, without the fence below. They aren't in `SHA256SUMS`.

````markdown
One-line summary of the release.

### Breaking
- What changed, why, and what users have to do about their sheets or settings.

### Highlights
- New features, the ones users see first.

### Fixes
- What was broken and what happens now.

### Changes
- Build, CI, packaging and dependency changes users may notice. Name the Python and
  PySide6 versions if they changed.

### Removed
- Features, files, settings or build targets that are gone.

### Install
- Linux: unpack and run `./calculon`.
- Windows: unpack and run `calculon.exe`. It isn't code-signed, so SmartScreen may ask
  to confirm the first start (More info → Run anyway).
- macOS: pick `macos_arm64` for Apple Silicon, `macos_x64` for Intel. It isn't notarized:
  the first time, right-click → Open, or run `xattr -d com.apple.quarantine calculon`.

### Verify
`gpg --verify SHA256SUMS.asc SHA256SUMS && sha256sum --ignore-missing -c SHA256SUMS`

**Full Changelog**: https://github.com/<owner>/<repo>/compare/<last-tag>...vX.Y.Z
````

Take `<owner>/<repo>` from `gh repo view --json nameWithOwner`. For the first release, drop
the Full Changelog line.

## 9. Publish the GitHub release

Publishing is public, so ask first with a pop-up: publish now, publish as a draft, or leave it
to the user. The title is `Calculon vX.Y.Z`:

```bash
gh release create vX.Y.Z --verify-tag --title "Calculon vX.Y.Z" \
  --notes-file dist/vX.Y.Z/RELEASE_NOTES.md \
  dist/vX.Y.Z/*.tar.gz dist/vX.Y.Z/*.zip dist/vX.Y.Z/SHA256SUMS dist/vX.Y.Z/SHA256SUMS.asc
gh release view vX.Y.Z --json url,isDraft,assets
```

Add `--draft` when the user picks a draft. The release must list 6 files: the 4 archives,
`SHA256SUMS` and `SHA256SUMS.asc`.

## 10. Report

Keep it short:

- the version, and that the tag signature is Good
- the commits in the release
- that CI's run passed, each build's self-test passed, and its archives match its checksums
- that the local build reports the version and passes its self-test
- the files in `dist/vX.Y.Z/` and that they verify
- the release link, or the release notes in one fenced `markdown` block if the user publishes
  it themselves
- leftovers, such as CI's archives in the scratchpad, or any skipped check
