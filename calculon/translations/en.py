"""English UI text. Sheets understand English and Ukrainian words in any language."""

T = {
    "app_name": "Calculon",
    # menus
    "menu_file": "&File",
    "menu_edit": "&Edit",
    "menu_view": "&View",
    "menu_help": "&Help",
    "new_sheet": "New Sheet",
    "new_directory": "New Directory",
    "open_directory": "Show Sheets Directory",
    "settings": "Settings…",
    "quit": "Quit",
    "undo": "Undo",
    "redo": "Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Paste",
    "select_all": "Select All",
    "toggle_comment": "Comment Line",
    "copy_result": "Copy Line Result",
    "copy_with_results": "Copy Sheet with Results",
    "insert_total": "Insert Total",
    "insert_reference": "Insert Line Reference",
    # words the two above type into the sheet
    "word_total": "total",
    "word_prev": "prev",
    "word_line": "line",
    "find": "Find Sheet",
    "find_in_sheet": "Find in Sheet",
    "find_next": "Find Next",
    "find_previous": "Find Previous",
    "find_placeholder": "Find in this sheet",
    "find_count": "{n} of {total}",
    "find_none": "No results",
    "find_close": "Close (Esc)",
    "theme": "Appearance",
    "theme_mode": "Mode",
    "theme_dark": "Dark",
    "theme_light": "Light",
    "theme_system": "Follow System",
    "colours": "Theme",
    "colours_ember": "Ember",
    "colours_glacier": "Glacier",
    "language": "Language",
    "zoom_in": "Bigger Text",
    "zoom_out": "Smaller Text",
    "zoom_reset": "Default Text Size",
    "toggle_sidebar": "Show Sidebar",
    "focus_mode": "Focus Mode",
    "always_on_top": "Always on Top",
    "toggle_line_numbers": "Line Numbers",
    "toggle_spelling": "Check Spelling",
    "help_sheet": "Help Sheet",
    "shortcuts": "Keyboard Shortcuts",
    "shortcuts_action": "Action",
    "shortcuts_keys": "Keys",
    "shortcuts_sidebar": "Sidebar",
    "shortcuts_open": "Open the selected sheet",
    "shortcuts_editor": "Editing",
    "delete_line_start": "Delete to the start of the line",
    "delete_line_end": "Delete to the end of the line",
    "reference_answer": "Insert a reference to an answer",
    "double_click_answer": "Double-click the answer",
    "shortcuts_autocomplete": "Autocomplete",
    "shortcuts_insert": "Insert the suggestion",
    "shortcuts_dismiss": "Close the list",
    "shortcuts_vim": "Vim mode",
    "vim_move": "Move",
    "vim_count": "Repeat with a count",
    "vim_insert": "Start typing in Insert mode",
    "vim_operators": "Delete, change, copy, then a motion",
    "vim_whole": "Whole line, one character, to the line end",
    "vim_paste": "Paste, join lines",
    "vim_replace": "Replace characters with the one typed next",
    "vim_switch_case": "Switch letters between capital and small",
    "vim_undo": "Undo, redo",
    "vim_select": "Select characters, whole lines",
    "vim_selection": "Edit the selection, swap its ends",
    "vim_search": "Search, next, previous",
    "vim_sheet_history": "Go back or forward in sheet history",
    "vim_spell_next": "Next, previous misspelled word",
    "vim_spell_suggest": "Spelling suggestions",
    "vim_spell_add": "Add to dictionary, ignore",
    "vim_scroll_line": "Scroll a line",
    "vim_scroll_half": "Scroll half a screen",
    "vim_scroll_page": "Scroll a screen",
    "vim_normal": "Back to Normal mode",
    "vim_panes": "Go to the sheet list, the sheet or the answers",
    "vim_list_move": "Move through sheets or answers",
    "vim_list_enter": "Open a sheet or directory, or copy an answer",
    "vim_list_delete": "Move to Trash, delete forever, or empty Trash",
    "vim_list_restore": "Restore a sheet or directory from Trash",
    "vim_hint": "Show or hide the hint at the cursor",
    "refresh_rates": "Refresh Exchange Rates",
    "about": "About Calculon",
    # autocomplete: what kind of word a suggestion is
    "kind_variable": "variable",
    "kind_function": "function",
    "kind_currency": "currency",
    "kind_unit": "unit",
    "kind_keyword": "word",
    # sidebar
    "search": "Search sheets",
    "pinned": "Pinned",
    "sheets": "Sheets",
    "help": "Help",
    "trash": "Trash",
    "rename": "Rename",
    "pin": "Pin",
    "unpin": "Unpin",
    "move_to_trash": "Move to Trash",
    "show_in_directory": "Show in File Manager",
    "restore": "Restore",
    "delete_forever": "Delete Forever",
    "empty_trash": "Empty Trash",
    "confirm_delete": 'Delete "{name}" for good? This can\'t be undone.',
    "confirm_empty": "Delete everything in the trash for good? This can't be undone.",
    "untitled": "Untitled",
    "directory": "New directory",
    "no_results": "No sheets found",
    # editor
    "read_only_help": (
        "The help sheet is read-only. To try an example, choose New Sheet in the File menu."
    ),
    "read_only_trash": "Restore this sheet from Trash to edit it.",
    "copied": "Copied {text}",
    "spell_add": "Add to Dictionary",
    "spell_ignore": "Ignore",
    "spell_none": "No suggestions",
    "total": "Total: {text}",
    "total_tip": "Adds all results, including subtotals. Click to copy.",
    "external_change": 'Calculon reloaded "{name}" after it changed on disk.',
    "save_conflict": "Couldn't save to the original file. Save a copy to keep your edits.",
    "save_copy": "Save a copy",
    "recovered_sheet": "Recovered {name}",
    "trash_preview_failed": 'Couldn\'t open "{name}" from Trash.\n\n{error}',
    # rates status
    "rates_updating": "Updating rates…",
    "rates_ok": "Rates: {when} · {source}",
    "rates_error": "Rates offline ({error}) · using {when}",
    "rates_never": "no rates yet",
    "rates_bundled": "bundled snapshot",
    "rates_tip": "Click to refresh exchange rates",
    # settings dialog
    "settings_title": "Settings",
    "cancel": "Cancel",
    "save": "Save",
    "vim_mode": "Vim mode",
    "hint_vim_mode": (
        "Use Normal, Insert and Visual modes. Open Keyboard Shortcuts in the Help menu."
    ),
    "section_format": "Format",
    "section_decimals": "Decimal places",
    "section_source": "Source",
    "section_json": "What a custom source must return",
    "hint_sheets_dir": (
        "Calculon saves each sheet as a .txt file here. You can sync or back up this directory."
    ),
    "hint_dollar": "Which currency a bare $ stands for.",
    "hint_decimals": "Set the maximum decimal places for answers. Set money separately below.",
    "hint_rates_url": "Leave blank to try open.er-api.com first, then Frankfurter.",
    "tab_general": "General",
    "tab_numbers": "Numbers",
    "tab_rates": "Exchange Rates",
    "tab_appearance": "Appearance",
    "tab_spelling": "Spell Check",
    "tab_vim": "Vim",
    "sheets_dir": "Sheets directory:",
    "directory_blocked": "Calculon can't create or write to {directory}. {error}.",
    "directory_blocked_windows": (
        "Controlled folder access in Windows Security may be blocking it. "
        "Allow Calculon there, or pick another directory."
    ),
    "directory_pick_another": "Pick another directory.",
    "directory_question": "Where should Calculon keep your sheets?",
    "directory_use": "Use this directory",
    "browse": "Browse…",
    "font_size": "Text size:",
    "ligatures": "Font ligatures",
    "spell_check": "Underline misspelled words",
    "spell_lang_en": "English",
    "spell_lang_uk": "Ukrainian",
    "hint_spell_ok": "{languages}, with the system's Hunspell dictionaries.",
    "hint_spell_missing": "No dictionary for {languages}. To add it: {command}",
    "hint_spell_linux": "Needs Hunspell. To install it: {command}",
    "hint_spell_macos": (
        "Needs Hunspell: run brew install hunspell, then put the .aff and .dic "
        "dictionary files in ~/Library/Spelling. The README has the steps."
    ),
    "hint_spell_macos_dicts": (
        "No dictionary for {languages}. To add one, put the .aff and .dic files in "
        "~/Library/Spelling. The README has the steps."
    ),
    "hint_spell_ok_windows": "{languages}, with the Windows spell checker.",
    "hint_spell_windows": "This Windows has no spell checker.",
    "hint_spell_windows_missing": (
        "No dictionary for {languages}. Add the language in Windows Settings, under "
        "Time & language > Language & region."
    ),
    "number_style": "Number format:",
    "hint_number_style": "Use this format for numbers you type and for answers.",
    "invalid number": "Use {sample}. Group digits in threes or leave them ungrouped.",
    "use YYYY-MM-DD for numeric dates": (
        "Write numeric dates as YYYY-MM-DD, for example 2026-11-18."
    ),
    "no such time": "Enter a time like 15:30 or 3:30pm.",
    "Use ‘to’ between the dates to calculate a date range.": (
        "Put 'to' between the dates to find the time between them."
    ),
    "{0} has no value": 'Variable "{0}" has no value.',
    "{0} is not defined": 'Define "{0}" before using it.',
    "expected {0}": "Enter {0} here.",
    "per what": "Enter a unit after 'per'.",
    "a what": "Enter a unit for the rate.",
    "after what": "Enter a start date.",
    "from what": "Enter a start date.",
    "through what": "Enter an end date.",
    "cast to what": "Enter the new unit.",
    "convert to what": "Enter a unit or currency to convert to.",
    "plain number expected": "Enter a number without units.",
    "places must be between -20 and 20": "Enter a number of decimal places from -20 to 20.",
    "time_format": "Time display:",
    "time_12h": "12-hour (3:45pm)",
    "time_24h": "24-hour (15:45)",
    "dollar": "$ means:",
    "max_decimals": "Decimal places (up to):",
    "money_decimals": "Decimal places for money:",
    "rates_url": "Custom rates URL:",
    "rates_url_placeholder": "Leave empty to use open.er-api.com, then Frankfurter (ECB)",
    "rates_help": (
        "Calculon downloads rates once a day and keeps the last ones for offline use.\n\n"
        "Use a URL that returns JSON in this format.\n\n"
        '{"base": "USD", "rates": {"EUR": 0.92, "UAH": 41.3, "GBP": 0.79}}\n\n'
        '• Set "base" or "base_code" to the base currency. The default is USD.\n'
        '• In "rates", give the amount of each currency that one unit of the base buys.\n'
        '• To show the update time, add "time_last_update_unix" in seconds or "date" '
        "in YYYY-MM-DD format.\n\n"
        "open.er-api.com and Frankfurter already return this format."
    ),
    "test_url": "Test URL",
    "test_ok": "Works: {count} currencies, base {base}.",
    "test_fail": "Doesn't work: {error}",
    "restart_note": "Language changes apply right away.",
    # about
    "update_checking": "Checking for updates…",
    "update_none": "Calculon is up to date",
    "update_newer": "<a href='{url}'>Calculon {version} is available on GitHub</a>",
    "update_failed": "Couldn't check for updates",
    "about_text": (
        "<h2>Calculon {version}</h2>"
        "<p>A notepad that calculates as you type.</p>"
        "<p>Exchange rates: open.er-api.com, Frankfurter (ECB).<br>"
        "Font: Fira Code (SIL Open Font License).<br>"
        "Icons: Phosphor Icons (MIT License).<br>"
        "App icon: Calculon, from seeklogo.com;<br>"
        "character © Matt Groening / Comedy Central.</p>"
        "<p><a href='https://sprytnyk.dev'>sprytnyk.dev</a> · MIT License</p>"
    ),
}
