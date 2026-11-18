"""Український текст інтерфейсу. Аркуші розуміють англійські й українські слова."""

T = {
    "app_name": "Calculon",
    # menus
    "menu_file": "&Файл",
    "menu_edit": "&Редагування",
    "menu_view": "&Вигляд",
    "menu_help": "&Довідка",
    "new_sheet": "Новий аркуш",
    "new_directory": "Нова тека",
    "open_directory": "Показати теку аркушів",
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
    "insert_total": 'Вставити "разом"',
    "insert_reference": "Вставити посилання на рядок",
    # слова, які вставляють два пункти вище
    "word_total": "разом",
    "word_prev": "попередній",
    "word_line": "рядок",
    "find": "Знайти аркуш",
    "find_in_sheet": "Знайти в аркуші",
    "find_next": "Знайти наступне",
    "find_previous": "Знайти попереднє",
    "find_placeholder": "Знайти в цьому аркуші",
    "find_count": "{n} з {total}",
    "find_none": "Немає збігів",
    "find_close": "Закрити (Esc)",
    "theme": "Оформлення",
    "theme_mode": "Режим",
    "theme_dark": "Темна",
    "theme_light": "Світла",
    "theme_system": "Як у системі",
    "colours": "Тема",
    "colours_ember": "Ember",
    "colours_glacier": "Glacier",
    "language": "Мова",
    "zoom_in": "Більший текст",
    "zoom_out": "Менший текст",
    "zoom_reset": "Звичайний розмір тексту",
    "toggle_sidebar": "Показати бічну панель",
    "focus_mode": "Режим фокусування",
    "always_on_top": "Завжди поверх інших вікон",
    "toggle_line_numbers": "Номери рядків",
    "toggle_spelling": "Перевіряти правопис",
    "help_sheet": "Аркуш довідки",
    "shortcuts": "Комбінації клавіш",
    "shortcuts_action": "Дія",
    "shortcuts_keys": "Клавіші",
    "shortcuts_sidebar": "Бічна панель",
    "shortcuts_open": "Відкрити вибраний аркуш",
    "shortcuts_editor": "Редагування",
    "delete_line_start": "Видалити до початку рядка",
    "delete_line_end": "Видалити до кінця рядка",
    "reference_answer": "Вставити посилання на відповідь",
    "double_click_answer": "Подвійне клацання по відповіді",
    "shortcuts_autocomplete": "Автодоповнення",
    "shortcuts_insert": "Вставити підказку",
    "shortcuts_dismiss": "Закрити список",
    "shortcuts_vim": "Режим Vim",
    "vim_move": "Рух",
    "vim_count": "Повторити кілька разів",
    "vim_insert": "Почати введення в режимі Insert",
    "vim_operators": "Видалити, змінити, скопіювати, далі рух",
    "vim_whole": "Цілий рядок, один символ, до кінця рядка",
    "vim_paste": "Вставити, з'єднати рядки",
    "vim_replace": "Замінити символи на наступний введений",
    "vim_switch_case": "Змінити великі літери на малі й навпаки",
    "vim_undo": "Скасувати, повторити",
    "vim_select": "Виділити символи, цілі рядки",
    "vim_selection": "Змінити виділене, поміняти його кінці",
    "vim_search": "Пошук, наступний, попередній",
    "vim_spell_next": "Наступне, попереднє слово з помилкою",
    "vim_spell_suggest": "Варіанти написання",
    "vim_spell_add": "Додати до словника, ігнорувати",
    "vim_scroll_line": "Прокрутити на рядок",
    "vim_scroll_half": "Прокрутити на пів екрана",
    "vim_scroll_page": "Прокрутити на екран",
    "vim_normal": "Назад у режим Normal",
    "vim_panes": "Перейти до списку аркушів, аркуша чи відповідей",
    "vim_list_move": "Рух у списку аркушів і відповідях",
    "vim_list_enter": "Відкрити аркуш чи теку, скопіювати відповідь",
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
    "show_in_directory": "Показати у файловому менеджері",
    "restore": "Відновити",
    "delete_forever": "Видалити назавжди",
    "empty_trash": "Очистити кошик",
    "confirm_delete": 'Видалити "{name}" назавжди? Це не можна скасувати.',
    "confirm_empty": "Видалити все з кошика назавжди? Це не можна скасувати.",
    "untitled": "Без назви",
    "directory": "Нова тека",
    "no_results": "Аркушів не знайдено",
    # editor
    "read_only_help": (
        'Аркуш довідки лише для читання. Щоб спробувати приклад, виберіть "Новий аркуш" '
        'у меню "Файл".'
    ),
    "read_only_trash": "Відновіть аркуш із кошика, щоб його редагувати.",
    "copied": "Скопійовано {text}",
    "spell_add": "Додати до словника",
    "spell_ignore": "Ігнорувати",
    "spell_none": "Немає варіантів",
    "total": "Разом: {text}",
    "total_tip": (
        "Клацніть, щоб скопіювати суму аркуша. Проміжний підсумок замінює свої рядки в сумі."
    ),
    "external_change": 'Calculon перечитав файл "{name}" після змін на диску.',
    "save_conflict": "Не вдалось записати в початковий файл. Збережіть копію зі своїми змінами.",
    "save_copy": "Зберегти копію",
    "recovered_sheet": "Копія {name}",
    "trash_preview_failed": 'Не вдалося відкрити "{name}" із кошика.\n\n{error}',
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
    "vim_mode": "Режим Vim",
    "hint_vim_mode": (
        "Режими Normal, Insert і Visual, як у Vim. Клавіші є в меню Довідка → Комбінації клавіш."
    ),
    "section_format": "Формат",
    "section_decimals": "Знаки після коми",
    "section_source": "Джерело",
    "section_json": "Що має повертати власне джерело",
    "hint_sheets_dir": (
        "Calculon зберігає тут кожен аркуш як файл .txt. Цю теку можна синхронізувати "
        "або зробити її резервну копію."
    ),
    "hint_dollar": "Яку валюту означає знак $ без уточнення.",
    "hint_decimals": (
        "Задайте найбільшу кількість знаків після коми. Для грошей є окреме налаштування."
    ),
    "hint_rates_url": (
        "Залиште поле порожнім, щоб брати курси спершу з open.er-api.com, потім із Frankfurter."
    ),
    "tab_general": "Загальні",
    "tab_numbers": "Числа",
    "tab_rates": "Курси валют",
    "tab_appearance": "Вигляд",
    "tab_spelling": "Правопис",
    "tab_vim": "Vim",
    "sheets_dir": "Тека аркушів:",
    "directory_blocked": "Calculon не може створити теку {directory} або записати в неї. {error}.",
    "directory_blocked_windows": (
        'Це може блокувати "Контрольований доступ до папок" у Безпеці Windows. '
        "Дозвольте там Calculon або виберіть іншу теку."
    ),
    "directory_pick_another": "Виберіть іншу теку.",
    "directory_question": "Де Calculon зберігатиме ваші аркуші?",
    "directory_use": "Використати цю теку",
    "browse": "Огляд…",
    "font_size": "Розмір тексту:",
    "ligatures": "Лігатури шрифту",
    "spell_check": "Підкреслювати слова з помилками",
    "spell_lang_en": "англійська",
    "spell_lang_uk": "українська",
    "hint_spell_ok": "Мови: {languages}. Словники Hunspell із системи.",
    "hint_spell_missing": "Немає словника для мов: {languages}. Щоб додати: {command}",
    "hint_spell_linux": "Потрібен Hunspell. Щоб встановити: {command}",
    "hint_spell_macos": (
        "Потрібен Hunspell: виконайте brew install hunspell і покладіть файли словників "
        ".aff і .dic у ~/Library/Spelling. Кроки є в README."
    ),
    "hint_spell_macos_dicts": (
        "Немає словника для мов: {languages}. Щоб додати, покладіть файли .aff і .dic "
        "у ~/Library/Spelling. Кроки є в README."
    ),
    "hint_spell_ok_windows": "Мови: {languages}. Перевірка правопису Windows.",
    "hint_spell_windows": "У цій Windows немає перевірки правопису.",
    "hint_spell_windows_missing": (
        "Немає словника для мов: {languages}. Додайте мову в Параметрах Windows, у розділі "
        "Час і мова > Мова та регіон."
    ),
    "number_style": "Формат чисел:",
    "hint_number_style": "Цей формат діє для чисел, які ви вводите, і для відповідей.",
    "invalid number": ("Запишіть число як {sample}. Групуйте цифри по три або пишіть їх разом."),
    "use YYYY-MM-DD for numeric dates": (
        "Записуйте дати цифрами як РРРР-ММ-ДД, наприклад 2026-11-18."
    ),
    "no such date": "Такої дати не існує.",
    "no such time": "Такого часу не існує.",
    "Use ‘to’ between the dates to calculate a date range.": (
        'Поставте "до" між датами, щоб знайти тривалість.'
    ),
    "internal calculation error": "Внутрішня помилка обчислення.",
    "could not calculate this line": "Не вдалося обчислити цей рядок.",
    "number too large": "Число завелике.",
    "@{0} needs a date": "Укажіть дату після @{0}.",
    "no @{0} above": "Вище немає @{0}.",
    "{0} has no value": 'Змінна "{0}" не має значення.',
    "{0} is not defined": 'Задайте значення змінної "{0}" перед тим, як її використати.',
    "expected {0}": "Введіть тут {0}.",
    "unexpected {0}": 'Неочікуваний запис "{0}".',
    "unexpected @": "Неочікуваний знак @.",
    "unexpected text": "Неочікуваний текст у виразі.",
    "empty": "Порожній вираз.",
    "expected a value": "Тут потрібне значення.",
    "expected a number": "Тут потрібне число.",
    "number expected": "Тут потрібне число.",
    "percent expected": "Тут потрібне число у відсотках.",
    "unknown suffix": "Невідомий суфікс числа.",
    "unit": "Тут потрібна одиниця виміру.",
    "a unit on its own": "Укажіть значення для одиниці виміру.",
    "per what": 'Укажіть одиницю виміру після "за".',
    "a what": "Укажіть одиницю виміру для ставки.",
    "after what": "Укажіть початкову дату.",
    "from what": "Укажіть початкову дату.",
    "through what": "Укажіть кінцеву дату.",
    "expected dates": "Тут потрібні дати.",
    "no previous answer": "Вище немає відповіді.",
    "no such line": "Такого рядка не існує.",
    "one argument expected": "Передайте функції один аргумент.",
    "rates need quantities": "Для ставки потрібні числові значення.",
    "not a rate": "Тут потрібна ставка або курс.",
    "rate doesn't cancel": "Одиниці виміру ставки не скорочуються.",
    "cast to what": "Укажіть нову одиницю виміру.",
    "convert to what": "Укажіть, у що перевести значення.",
    "only times move between time zones": "Між часовими поясами можна переводити лише час.",
    "rate must be a number": "Курс має бути числом.",
    "rate must be positive": "Курс має бути більшим за нуль.",
    "rate doesn't match": "Курс не відповідає вказаним валютам.",
    "no exchange rate for {0}": "Немає курсу для {0}.",
    "functions need numbers": "Передайте функції число.",
    "angle expected": "Тут потрібен кут.",
    "plain number expected": "Тут потрібне число без одиниць виміру.",
    "factorial needs a whole number up to 1000": (
        "Для факторіала потрібне ціле число від 0 до 1000."
    ),
    "can't take that root of these units": "Не можна добути такий корінь із цих одиниць виміру.",
    "invalid function argument": "Неприпустимий аргумент функції.",
    "result is not a number": "Результат не є числом.",
    "places must be a number": "Кількість знаків має бути числом.",
    "places must be between -20 and 20": "Кількість знаків має бути від −20 до 20.",
    "nothing to average": "Немає значень для обчислення середнього.",
    "need at least two values": "Потрібні щонайменше два значення.",
    "division by zero": "Ділення на нуль.",
    "not a duration": "Тут потрібна тривалість.",
    "incompatible units": "Несумісні одиниці виміру.",
    "can't add incompatible units": "Не можна додати значення з несумісними одиницями виміру.",
    "exponent must be a plain number": "Показник степеня має бути числом без одиниць виміру.",
    "unit powers must be whole numbers": "Степені одиниць виміру мають бути цілими числами.",
    "can't take a fractional power of a negative number": (
        "Не можна піднести від'ємне число до дробового степеня."
    ),
    "can't calculate that power": "Не вдалося піднести число до цього степеня.",
    "can't do that with a date": "Цю дію не можна виконати з датою.",
    "can't convert a date to a unit": "Дату не можна перевести в одиниці виміру.",
    "can't add those": "Ці значення не можна додати.",
    "number_date_notice": (
        "Calculon використовує формат чисел із налаштувань. Розділяйте елементи списків "
        "і аргументи функцій крапкою з комою. Пишіть дати як 2026-11-18 або 18 листопада "
        "2026. Перепишіть дати в інших числових форматах. Для ділення ставте пробіли навколо /, "
        "як у 18 / 11 / 2026. Якщо в старих аркушах є інші формати, виправте їх вручну."
    ),
    "dismiss_notice": "Закрити",
    "time_format": "Формат часу:",
    "time_12h": "12-годинний (3:45pm)",
    "time_24h": "24-годинний (15:45)",
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
    "update_checking": "Перевірка оновлень…",
    "update_none": "У вас найновіша версія Calculon",
    "update_newer": "<a href='{url}'>Calculon {version} доступний на GitHub</a>",
    "update_failed": "Не вдалося перевірити оновлення",
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
