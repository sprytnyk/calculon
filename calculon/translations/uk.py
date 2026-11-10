"""Український текст інтерфейсу. Аркуші розуміють англійські й українські слова."""

T = {
    "app_name": "Calculon",
    # menus
    "menu_file": "&Файл",
    "menu_edit": "&Редагування",
    "menu_view": "&Вигляд",
    "menu_help": "&Довідка",
    "new_sheet": "Новий аркуш",
    "new_folder": "Нова тека",
    "open_folder": "Показати теку аркушів",
    "settings": "Налаштування…",
    "quit": "Вийти",
    "undo": "Скасувати",
    "redo": "Повторити",
    "cut": "Вирізати",
    "copy": "Копіювати",
    "paste": "Вставити",
    "select_all": "Виділити все",
    "toggle_comment": "Закоментувати рядок",
    "copy_result": "Копіювати результат рядка",
    "copy_with_results": "Копіювати аркуш із результатами",
    "find": "Знайти аркуш",
    "find_in_sheet": "Знайти в аркуші",
    "find_next": "Знайти наступне",
    "find_previous": "Знайти попереднє",
    "find_placeholder": "Знайти в цьому аркуші",
    "find_count": "{n} з {total}",
    "find_none": "Немає збігів",
    "find_close": "Закрити (Esc)",
    "theme": "Тема",
    "theme_dark": "Темна",
    "theme_light": "Світла",
    "theme_system": "Як у системі",
    "language": "Мова",
    "zoom_in": "Більший текст",
    "zoom_out": "Менший текст",
    "zoom_reset": "Звичайний розмір тексту",
    "toggle_sidebar": "Показати бічну панель",
    "toggle_line_numbers": "Номери рядків",
    "help_sheet": "Аркуш довідки",
    "shortcuts": "Комбінації клавіш",
    "shortcuts_action": "Дія",
    "shortcuts_keys": "Клавіші",
    "shortcuts_sidebar": "Бічна панель",
    "shortcuts_open": "Відкрити вибраний аркуш",
    "shortcuts_editor": "Редагування",
    "delete_line_start": "Видалити до початку рядка",
    "delete_line_end": "Видалити до кінця рядка",
    "shortcuts_autocomplete": "Автодоповнення",
    "shortcuts_insert": "Вставити підказку",
    "shortcuts_dismiss": "Закрити список",
    "refresh_rates": "Оновити курси валют",
    "about": "Про Calculon",
    # автодоповнення: що це за слово
    "kind_variable": "змінна",
    "kind_function": "функція",
    "kind_currency": "валюта",
    "kind_unit": "одиниця",
    "kind_keyword": "слово",
    # sidebar
    "search": "Пошук аркушів",
    "pinned": "Закріплені",
    "sheets": "Аркуші",
    "help": "Довідка",
    "trash": "Кошик",
    "rename": "Перейменувати",
    "pin": "Закріпити",
    "unpin": "Відкріпити",
    "move_to_trash": "У кошик",
    "show_in_folder": "Показати у файловому менеджері",
    "restore": "Відновити",
    "delete_forever": "Видалити назавжди",
    "empty_trash": "Очистити кошик",
    "confirm_delete": "Видалити «{name}» назавжди? Це не можна скасувати.",
    "confirm_empty": "Видалити все з кошика назавжди? Це не можна скасувати.",
    "untitled": "Без назви",
    "folder": "Нова тека",
    "no_results": "Аркушів не знайдено",
    # editor
    "read_only_help": (
        "Аркуш довідки лише для читання. Щоб спробувати, створіть аркуш через Файл → Новий аркуш."
    ),
    "read_only_trash": "Цей аркуш у кошику. Відновіть його, щоб редагувати.",
    "copied": "Скопійовано {text}",
    "total": "Разом: {text}",
    "external_change": "Файл «{name}» змінився на диску, тож Calculon його перезавантажив.",
    # rates status
    "rates_updating": "Оновлення курсів…",
    "rates_ok": "Курси: {when} · {source}",
    "rates_error": "Курси офлайн ({error}) · від {when}",
    "rates_never": "курсів ще немає",
    "rates_bundled": "вбудований знімок",
    "rates_tip": "Натисніть, щоб оновити курси валют",
    # settings dialog
    "settings_title": "Налаштування",
    "cancel": "Скасувати",
    "save": "Зберегти",
    "section_sheets": "Аркуші",
    "section_appearance": "Вигляд",
    "section_format": "Формат",
    "section_decimals": "Знаки після коми",
    "section_source": "Джерело",
    "section_json": "Що має повертати власне джерело",
    "hint_sheets_dir": (
        "Кожен аркуш тут це звичайний файл .txt, тож синхронізація й резервні копії "
        "працюють без налаштувань."
    ),
    "hint_dollar": "Яку валюту означає знак $ без уточнення.",
    "hint_decimals": "Результати показують до стількох знаків; для грошей окреме налаштування.",
    "hint_rates_url": (
        "Залиште порожнім, щоб брати курси з open.er-api.com, а запасним буде Frankfurter."
    ),
    "tab_general": "Загальні",
    "tab_numbers": "Числа",
    "tab_rates": "Курси валют",
    "sheets_dir": "Тека аркушів:",
    "browse": "Огляд…",
    "font_size": "Розмір тексту:",
    "ligatures": "Лігатури шрифту",
    "number_style": "Формат чисел:",
    "number_style_auto": "Як у мові інтерфейсу",
    "date_order": "Дати на кшталт 01/02/2026:",
    "dmy": "Спершу день (1 лютого)",
    "mdy": "Спершу місяць (2 січня)",
    "dollar": "$ означає:",
    "max_decimals": "Знаків після коми (до):",
    "money_decimals": "Знаків після коми для грошей:",
    "rates_url": "Власна адреса курсів:",
    "rates_url_placeholder": "Залиште порожнім для open.er-api.com, потім Frankfurter (ЄЦБ)",
    "rates_help": (
        "Calculon завантажує курси раз на день і зберігає останні для роботи офлайн.\n\n"
        "Власна адреса має повертати JSON такого вигляду:\n\n"
        '{"base": "USD", "rates": {"EUR": 0.92, "UAH": 41.3, "GBP": 0.79}}\n\n'
        '• base: валюта, відносно якої задано курси (також підходить "base_code"; '
        "типово USD).\n"
        "• rates: скільки одиниць кожної валюти дають за одну одиницю base.\n"
        '• Необов\'язково: "time_last_update_unix" (секунди) або "date" (РРРР-ММ-ДД), '
        "щоб показати, коли курси оновлено.\n\n"
        "Відповіді open.er-api.com і Frankfurter уже мають такий вигляд, тож "
        "власний сервер Frankfurter працює одразу."
    ),
    "test_url": "Перевірити",
    "test_ok": "Працює: {count} валют, база {base}.",
    "test_fail": "Не працює: {error}",
    "restart_note": "Мова змінюється одразу.",
    # about
    "about_text": (
        "<h2>Calculon {version}</h2>"
        "<p>Блокнот, що рахує, поки ви пишете.</p>"
        "<p>Курси валют: open.er-api.com, Frankfurter (ЄЦБ).<br>"
        "Шрифт: Fira Code (SIL Open Font License).<br>"
        "Іконки: Phosphor Icons (MIT License).<br>"
        "Іконка програми: Calculon, з seeklogo.com;<br>"
        "персонаж © Matt Groening / Comedy Central.</p>"
        "<p><a href='https://sprytnyk.dev'>sprytnyk.dev</a> · Ліцензія MIT</p>"
    ),
}
