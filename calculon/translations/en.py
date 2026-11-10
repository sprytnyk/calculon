"""English UI text. Sheets understand English and Ukrainian words in any language."""

T = {
    "app_name": "Calculon",
    # menus
    "menu_file": "&File",
    "menu_edit": "&Edit",
    "menu_view": "&View",
    "menu_help": "&Help",
    "new_sheet": "New Sheet",
    "new_folder": "New Folder",
    "open_folder": "Show Sheets Folder",
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
    "theme": "Theme",
    "theme_dark": "Dark",
    "theme_light": "Light",
    "theme_system": "Follow System",
    "language": "Language",
    "zoom_in": "Bigger Text",
    "zoom_out": "Smaller Text",
    "zoom_reset": "Default Text Size",
    "toggle_sidebar": "Show Sidebar",
    "toggle_line_numbers": "Line Numbers",
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
    "show_in_folder": "Show in File Manager",
    "restore": "Restore",
    "delete_forever": "Delete Forever",
    "empty_trash": "Empty Trash",
    "confirm_delete": 'Delete "{name}" for good? This can\'t be undone.',
    "confirm_empty": "Delete everything in the trash for good? This can't be undone.",
    "untitled": "Untitled",
    "folder": "New folder",
    "no_results": "No sheets found",
    # editor
    "read_only_help": (
        "The help sheet is read-only. To try things out, make a sheet with File → New Sheet."
    ),
    "read_only_trash": "This sheet is in the trash. Restore it to edit.",
    "copied": "Copied {text}",
    "total": "Total: {text}",
    "external_change": '"{name}" changed on disk, so Calculon reloaded it.',
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
    "section_sheets": "Sheets",
    "section_appearance": "Appearance",
    "section_format": "Format",
    "section_decimals": "Decimal places",
    "section_source": "Source",
    "section_json": "What a custom source must return",
    "hint_sheets_dir": (
        "Each sheet is a plain .txt file in this folder, so sync tools and backups just work."
    ),
    "hint_dollar": "Which currency a bare $ stands for.",
    "hint_decimals": "Results show up to this many; money uses its own setting.",
    "hint_rates_url": "Leave empty to use open.er-api.com, with Frankfurter as the fallback.",
    "tab_general": "General",
    "tab_numbers": "Numbers",
    "tab_rates": "Exchange Rates",
    "sheets_dir": "Sheets folder:",
    "browse": "Browse…",
    "font_size": "Text size:",
    "ligatures": "Font ligatures",
    "number_style": "Number format:",
    "number_style_auto": "Same as the language",
    "date_order": "Dates like 01/02/2026:",
    "dmy": "Day first (1 February)",
    "mdy": "Month first (January 2)",
    "dollar": "$ means:",
    "max_decimals": "Decimal places (up to):",
    "money_decimals": "Decimal places for money:",
    "rates_url": "Custom rates URL:",
    "rates_url_placeholder": "Leave empty to use open.er-api.com, then Frankfurter (ECB)",
    "rates_help": (
        "Calculon downloads rates once a day and keeps the last ones for offline use.\n\n"
        "A custom URL must return JSON like this:\n\n"
        '{"base": "USD", "rates": {"EUR": 0.92, "UAH": 41.3, "GBP": 0.79}}\n\n'
        '• base: the currency the rates are relative to ("base_code" also works; '
        "defaults to USD).\n"
        "• rates: how many units of each currency one unit of base buys.\n"
        '• Optional: "time_last_update_unix" (seconds) or "date" (YYYY-MM-DD) '
        "to show when the rates were updated.\n\n"
        "Responses from open.er-api.com and Frankfurter already have this shape, so "
        "a self-hosted Frankfurter works as is."
    ),
    "test_url": "Test URL",
    "test_ok": "Works: {count} currencies, base {base}.",
    "test_fail": "Doesn't work: {error}",
    "restart_note": "Language changes apply right away.",
    # about
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
