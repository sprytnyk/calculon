// Made by scripts/build_site.py from Calculon's engine. Don't edit by hand.
window.CALCULON = {
 "en": {
  "rates_date": "10 November 2026",
  "ui": {
   "menus": [
    "File",
    "Edit",
    "View",
    "Help"
   ],
   "sheets": "Sheets",
   "help": "Help",
   "trash": "Trash",
   "toggle_sidebar": "Sidebar (Ctrl+\\)",
   "menu": [
    [
     [
      "Undo",
      "Ctrl+Z",
      "undo"
     ],
     [
      "Redo",
      "Ctrl+Shift+Z",
      "redo"
     ]
    ],
    [
     [
      "Cut",
      "Ctrl+X",
      "cut"
     ],
     [
      "Copy",
      "Ctrl+C",
      "copy"
     ],
     [
      "Paste",
      "Ctrl+V",
      "paste"
     ],
     [
      "Select All",
      "Ctrl+A",
      "select_all"
     ]
    ],
    [
     [
      "Comment Line",
      "Ctrl+/",
      "comment"
     ],
     [
      "Copy Line Result",
      "Ctrl+Shift+C",
      "copy_result"
     ],
     [
      "Insert Line Reference",
      "Ctrl+L",
      "insert_reference"
     ]
    ]
   ],
   "spell_add": "Add to Dictionary",
   "spell_ignore": "Ignore"
  },
  "icon_groups": {
   "colours": "violet",
   "comment": "neutral",
   "copy": "violet",
   "copy_result": "green",
   "cut": "violet",
   "directory": "amber",
   "help": "blue",
   "insert_reference": "blue",
   "language": "green",
   "numbers": "amber",
   "open_directory": "amber",
   "paste": "violet",
   "pin": "rose",
   "rates": "green",
   "redo": "teal",
   "select_all": "violet",
   "sheet": "blue",
   "shortcuts": "indigo",
   "sidebar": "neutral",
   "spell_add": "green",
   "spell_ignore": "neutral",
   "trash": "red",
   "undo": "teal"
  },
  "sidebar": [
   [
    "Trips",
    [
     "hero"
    ]
   ],
   [
    "Home",
    [
     "spelling"
    ]
   ]
  ],
  "sheets": {
   "hero": {
    "name": "Weekend in Lviv",
    "lines": [
     {
      "text": "# Weekend in Lviv",
      "spans": [
       [
        0,
        17,
        "heading"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "Train: 2 × 850 UAH",
      "spans": [
       [
        0,
        7,
        "label"
       ],
       [
        7,
        8,
        "number"
       ],
       [
        9,
        10,
        "operator"
       ],
       [
        11,
        14,
        "number"
       ],
       [
        15,
        18,
        "unit"
       ]
      ],
      "answer": "₴1,700.00",
      "total": false,
      "status": "Total: ₴1,700.00"
     },
     {
      "text": "Hotel: 2 nights × 1,900 UAH",
      "spans": [
       [
        0,
        7,
        "label"
       ],
       [
        7,
        8,
        "number"
       ],
       [
        9,
        15,
        "unit"
       ],
       [
        16,
        17,
        "operator"
       ],
       [
        18,
        23,
        "number"
       ],
       [
        24,
        27,
        "unit"
       ]
      ],
      "answer": "₴3,800.00",
      "total": false,
      "status": "Total: ₴5,500.00"
     },
     {
      "text": "Coffee and cake: 4 × 180 UAH",
      "spans": [
       [
        0,
        17,
        "label"
       ],
       [
        17,
        18,
        "number"
       ],
       [
        19,
        20,
        "operator"
       ],
       [
        21,
        24,
        "number"
       ],
       [
        25,
        28,
        "unit"
       ]
      ],
      "answer": "₴720.00",
      "total": false,
      "status": "Total: ₴6,220.00"
     },
     {
      "text": "Museum 2 × 250 UAH",
      "spans": [
       [
        7,
        8,
        "number"
       ],
       [
        9,
        10,
        "operator"
       ],
       [
        11,
        14,
        "number"
       ],
       [
        15,
        18,
        "unit"
       ]
      ],
      "answer": "₴500.00",
      "total": false,
      "status": "Total: ₴6,720.00"
     },
     {
      "text": "total in EUR",
      "spans": [
       [
        0,
        5,
        "keyword"
       ],
       [
        6,
        8,
        "keyword"
       ],
       [
        9,
        12,
        "unit"
       ]
      ],
      "answer": "€131.99",
      "total": true,
      "status": "Total: €263.98"
     }
    ],
    "total": "Total: €263.98"
   },
   "basics": {
    "name": "Moving budget",
    "lines": [
     {
      "text": "# Moving budget",
      "spans": [
       [
        0,
        15,
        "heading"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "rent = $1,450",
      "spans": [
       [
        0,
        4,
        "variable"
       ],
       [
        7,
        8,
        "unit"
       ],
       [
        8,
        13,
        "number"
       ]
      ],
      "answer": "$1,450.00",
      "total": false,
      "status": "Total: $1,450.00"
     },
     {
      "text": "deposit = rent × 2",
      "spans": [
       [
        0,
        7,
        "variable"
       ],
       [
        10,
        14,
        "variable"
       ],
       [
        15,
        16,
        "operator"
       ],
       [
        17,
        18,
        "number"
       ]
      ],
      "answer": "$2,900.00",
      "total": false,
      "status": "Total: $4,350.00"
     },
     {
      "text": "Movers: $380 for the truck + $45 tip",
      "spans": [
       [
        0,
        8,
        "label"
       ],
       [
        8,
        9,
        "unit"
       ],
       [
        9,
        12,
        "number"
       ],
       [
        27,
        28,
        "operator"
       ],
       [
        29,
        30,
        "unit"
       ],
       [
        30,
        32,
        "number"
       ]
      ],
      "answer": "$425.00",
      "total": false,
      "status": "Total: $4,775.00"
     },
     {
      "text": "Sofa $1,200 - 15%",
      "spans": [
       [
        5,
        6,
        "unit"
       ],
       [
        6,
        11,
        "number"
       ],
       [
        12,
        13,
        "operator"
       ],
       [
        14,
        16,
        "number"
       ],
       [
        16,
        17,
        "operator"
       ]
      ],
      "answer": "$1,020.00",
      "total": false,
      "status": "Total: $5,795.00"
     },
     {
      "text": "total",
      "spans": [
       [
        0,
        5,
        "keyword"
       ]
      ],
      "answer": "$5,795.00",
      "total": true,
      "status": "Total: $11,590.00"
     }
    ],
    "total": "Total: $11,590.00"
   },
   "money": {
    "name": "Shopping in London",
    "lines": [
     {
      "text": "# Shopping in London",
      "spans": [
       [
        0,
        20,
        "heading"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "Jacket: £89 in USD",
      "spans": [
       [
        0,
        8,
        "label"
       ],
       [
        8,
        9,
        "unit"
       ],
       [
        9,
        11,
        "number"
       ],
       [
        12,
        14,
        "keyword"
       ],
       [
        15,
        18,
        "unit"
       ]
      ],
      "answer": "$119.51",
      "total": false,
      "status": "Total: $119.51"
     },
     {
      "text": "Coffee £4.50 × 6 in EUR",
      "spans": [
       [
        7,
        8,
        "unit"
       ],
       [
        8,
        12,
        "number"
       ],
       [
        13,
        14,
        "operator"
       ],
       [
        15,
        16,
        "number"
       ],
       [
        17,
        19,
        "keyword"
       ],
       [
        20,
        23,
        "unit"
       ]
      ],
      "answer": "€32.36",
      "total": false,
      "status": "Total: €139.02"
     },
     {
      "text": "20% off $80",
      "spans": [
       [
        0,
        2,
        "number"
       ],
       [
        2,
        3,
        "operator"
       ],
       [
        4,
        7,
        "keyword"
       ],
       [
        8,
        9,
        "unit"
       ],
       [
        9,
        11,
        "number"
       ]
      ],
      "answer": "$64.00",
      "total": false,
      "status": "Total: $219.77"
     },
     {
      "text": "Run: 10 km in miles",
      "spans": [
       [
        0,
        5,
        "label"
       ],
       [
        5,
        7,
        "number"
       ],
       [
        8,
        10,
        "unit"
       ],
       [
        11,
        13,
        "keyword"
       ],
       [
        14,
        19,
        "unit"
       ]
      ],
      "answer": "6.214 mi",
      "total": false,
      "status": "Total: $219.77"
     },
     {
      "text": "Oven 180 °C in °F",
      "spans": [
       [
        5,
        8,
        "number"
       ],
       [
        9,
        11,
        "unit"
       ],
       [
        12,
        14,
        "keyword"
       ],
       [
        15,
        17,
        "unit"
       ]
      ],
      "answer": "356 °F",
      "total": false,
      "status": "Total: $219.77"
     },
     {
      "text": "1.5 TB at 25 MB/s in hours",
      "spans": [
       [
        0,
        3,
        "number"
       ],
       [
        4,
        6,
        "unit"
       ],
       [
        7,
        9,
        "keyword"
       ],
       [
        10,
        12,
        "number"
       ],
       [
        13,
        15,
        "unit"
       ],
       [
        15,
        16,
        "operator"
       ],
       [
        16,
        17,
        "unit"
       ],
       [
        18,
        20,
        "keyword"
       ],
       [
        21,
        26,
        "unit"
       ]
      ],
      "answer": "16.667 hours",
      "total": false,
      "status": "Total: $219.77"
     }
    ],
    "total": "Total: $219.77"
   },
   "dates": {
    "name": "Portugal trip",
    "lines": [
     {
      "text": "# Portugal trip",
      "spans": [
       [
        0,
        15,
        "heading"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "@from 2026-11-14",
      "spans": [
       [
        0,
        5,
        "keyword"
       ],
       [
        6,
        16,
        "number"
       ]
      ],
      "answer": "14 November",
      "total": false,
      "status": ""
     },
     {
      "text": "Lisbon: 3 days",
      "spans": [
       [
        0,
        8,
        "label"
       ],
       [
        8,
        9,
        "number"
       ],
       [
        10,
        14,
        "unit"
       ]
      ],
      "answer": "17 November",
      "total": false,
      "status": ""
     },
     {
      "text": "Porto: 2 days",
      "spans": [
       [
        0,
        7,
        "label"
       ],
       [
        7,
        8,
        "number"
       ],
       [
        9,
        13,
        "unit"
       ]
      ],
      "answer": "19 November",
      "total": false,
      "status": ""
     },
     {
      "text": "// the flight home is on 18 November",
      "spans": [
       [
        0,
        36,
        "comment"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "@to 2026-11-18",
      "spans": [
       [
        0,
        3,
        "keyword"
       ],
       [
        4,
        14,
        "number"
       ]
      ],
      "answer": "1 day over",
      "total": false,
      "status": "Total: -1 day"
     },
     {
      "text": "2026-11-14 + 3 weeks",
      "spans": [
       [
        0,
        10,
        "number"
       ],
       [
        11,
        12,
        "operator"
       ],
       [
        13,
        14,
        "number"
       ],
       [
        15,
        20,
        "unit"
       ]
      ],
      "answer": "5 December",
      "total": false,
      "status": "Total: -1 day"
     },
     {
      "text": "days between 2026-11-14 and 2026-12-25",
      "spans": [
       [
        0,
        4,
        "unit"
       ],
       [
        5,
        12,
        "keyword"
       ],
       [
        13,
        23,
        "number"
       ],
       [
        24,
        27,
        "keyword"
       ],
       [
        28,
        38,
        "number"
       ]
      ],
      "answer": "41 days",
      "total": false,
      "status": "Total: 40 days"
     }
    ],
    "total": "Total: 40 days"
   },
   "spelling": {
    "name": "Ремонт кухні",
    "lines": [
     {
      "text": "# Ремонт кухні",
      "spans": [
       [
        0,
        14,
        "heading"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "Плитка: 650 грн × 12",
      "spans": [
       [
        0,
        8,
        "label"
       ],
       [
        8,
        11,
        "number"
       ],
       [
        12,
        15,
        "unit"
       ],
       [
        16,
        17,
        "operator"
       ],
       [
        18,
        20,
        "number"
       ]
      ],
      "answer": "₴7,800.00",
      "total": false,
      "status": "Total: ₴7,800.00"
     },
     {
      "text": "Шпаклівкаа: 4 × 380 грн",
      "spans": [
       [
        0,
        12,
        "label"
       ],
       [
        12,
        13,
        "number"
       ],
       [
        14,
        15,
        "operator"
       ],
       [
        16,
        19,
        "number"
       ],
       [
        20,
        23,
        "unit"
       ]
      ],
      "answer": "₴1,520.00",
      "total": false,
      "status": "Total: ₴9,320.00"
     },
     {
      "text": "Робота 15,000 грн",
      "spans": [
       [
        7,
        13,
        "number"
       ],
       [
        14,
        17,
        "unit"
       ]
      ],
      "answer": "₴15,000.00",
      "total": false,
      "status": "Total: ₴24,320.00"
     },
     {
      "text": "Кухонні меблі 48,000 грн − 10%",
      "spans": [
       [
        14,
        20,
        "number"
       ],
       [
        21,
        24,
        "unit"
       ],
       [
        25,
        26,
        "operator"
       ],
       [
        27,
        29,
        "number"
       ],
       [
        29,
        30,
        "operator"
       ]
      ],
      "answer": "₴43,200.00",
      "total": false,
      "status": "Total: ₴67,520.00"
     },
     {
      "text": "разом",
      "spans": [
       [
        0,
        5,
        "keyword"
       ]
      ],
      "answer": "₴67,520.00",
      "total": true,
      "status": "Total: ₴135,040.00"
     }
    ],
    "total": "Total: ₴135,040.00",
    "misspelled": {
     "line": 2,
     "start": 0,
     "end": 10
    },
    "suggestions": [
     "Шпаклівка",
     "Шпаклівкам",
     "Шпаклівках",
     "Шпаклівка а",
     "Шпаківка"
    ]
   }
  }
 },
 "uk": {
  "rates_date": "10 листопада 2026",
  "ui": {
   "menus": [
    "Файл",
    "Редагування",
    "Вигляд",
    "Довідка"
   ],
   "sheets": "Аркуші",
   "help": "Довідка",
   "trash": "Кошик",
   "toggle_sidebar": "Бічна панель (Ctrl+\\)",
   "menu": [
    [
     [
      "Скасувати",
      "Ctrl+Z",
      "undo"
     ],
     [
      "Повторити",
      "Ctrl+Shift+Z",
      "redo"
     ]
    ],
    [
     [
      "Вирізати",
      "Ctrl+X",
      "cut"
     ],
     [
      "Копіювати",
      "Ctrl+C",
      "copy"
     ],
     [
      "Вставити",
      "Ctrl+V",
      "paste"
     ],
     [
      "Виділити все",
      "Ctrl+A",
      "select_all"
     ]
    ],
    [
     [
      "Закоментувати рядок",
      "Ctrl+/",
      "comment"
     ],
     [
      "Копіювати результат рядка",
      "Ctrl+Shift+C",
      "copy_result"
     ],
     [
      "Вставити посилання на рядок",
      "Ctrl+L",
      "insert_reference"
     ]
    ]
   ],
   "spell_add": "Додати до словника",
   "spell_ignore": "Ігнорувати"
  },
  "icon_groups": {
   "colours": "violet",
   "comment": "neutral",
   "copy": "violet",
   "copy_result": "green",
   "cut": "violet",
   "directory": "amber",
   "help": "blue",
   "insert_reference": "blue",
   "language": "green",
   "numbers": "amber",
   "open_directory": "amber",
   "paste": "violet",
   "pin": "rose",
   "rates": "green",
   "redo": "teal",
   "select_all": "violet",
   "sheet": "blue",
   "shortcuts": "indigo",
   "sidebar": "neutral",
   "spell_add": "green",
   "spell_ignore": "neutral",
   "trash": "red",
   "undo": "teal"
  },
  "sidebar": [
   [
    "Подорожі",
    [
     "hero"
    ]
   ],
   [
    "Дім",
    [
     "spelling"
    ]
   ]
  ],
  "sheets": {
   "hero": {
    "name": "Вихідні у Львові",
    "lines": [
     {
      "text": "# Вихідні у Львові",
      "spans": [
       [
        0,
        18,
        "heading"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "Потяг: 2 × 850 грн",
      "spans": [
       [
        0,
        7,
        "label"
       ],
       [
        7,
        8,
        "number"
       ],
       [
        9,
        10,
        "operator"
       ],
       [
        11,
        14,
        "number"
       ],
       [
        15,
        18,
        "unit"
       ]
      ],
      "answer": "1,700.00 ₴",
      "total": false,
      "status": "Разом: 1,700.00 ₴"
     },
     {
      "text": "Готель: 2 × 1,900 грн",
      "spans": [
       [
        0,
        8,
        "label"
       ],
       [
        8,
        9,
        "number"
       ],
       [
        10,
        11,
        "operator"
       ],
       [
        12,
        17,
        "number"
       ],
       [
        18,
        21,
        "unit"
       ]
      ],
      "answer": "3,800.00 ₴",
      "total": false,
      "status": "Разом: 5,500.00 ₴"
     },
     {
      "text": "Кава з тістечком: 4 × 180 грн",
      "spans": [
       [
        0,
        18,
        "label"
       ],
       [
        18,
        19,
        "number"
       ],
       [
        20,
        21,
        "operator"
       ],
       [
        22,
        25,
        "number"
       ],
       [
        26,
        29,
        "unit"
       ]
      ],
      "answer": "720.00 ₴",
      "total": false,
      "status": "Разом: 6,220.00 ₴"
     },
     {
      "text": "Музей 2 × 250 грн",
      "spans": [
       [
        6,
        7,
        "number"
       ],
       [
        8,
        9,
        "operator"
       ],
       [
        10,
        13,
        "number"
       ],
       [
        14,
        17,
        "unit"
       ]
      ],
      "answer": "500.00 ₴",
      "total": false,
      "status": "Разом: 6,720.00 ₴"
     },
     {
      "text": "разом у EUR",
      "spans": [
       [
        0,
        5,
        "keyword"
       ],
       [
        6,
        7,
        "keyword"
       ],
       [
        8,
        11,
        "unit"
       ]
      ],
      "answer": "131.99 €",
      "total": true,
      "status": "Разом: 263.98 €"
     }
    ],
    "total": "Разом: 263.98 €"
   },
   "basics": {
    "name": "Переїзд",
    "lines": [
     {
      "text": "# Переїзд",
      "spans": [
       [
        0,
        9,
        "heading"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "оренда = 1,450 $",
      "spans": [
       [
        0,
        6,
        "variable"
       ],
       [
        9,
        14,
        "number"
       ],
       [
        15,
        16,
        "unit"
       ]
      ],
      "answer": "1,450.00 $",
      "total": false,
      "status": "Разом: 1,450.00 $"
     },
     {
      "text": "застава = оренда × 2",
      "spans": [
       [
        0,
        7,
        "variable"
       ],
       [
        10,
        16,
        "variable"
       ],
       [
        17,
        18,
        "operator"
       ],
       [
        19,
        20,
        "number"
       ]
      ],
      "answer": "2,900.00 $",
      "total": false,
      "status": "Разом: 4,350.00 $"
     },
     {
      "text": "Вантажники: 380 $ за машину + 45 $ на чай",
      "spans": [
       [
        0,
        12,
        "label"
       ],
       [
        12,
        15,
        "number"
       ],
       [
        16,
        17,
        "unit"
       ],
       [
        28,
        29,
        "operator"
       ],
       [
        30,
        32,
        "number"
       ],
       [
        33,
        34,
        "unit"
       ]
      ],
      "answer": "425.00 $",
      "total": false,
      "status": "Разом: 4,775.00 $"
     },
     {
      "text": "Диван 1,200 $ − 15%",
      "spans": [
       [
        6,
        11,
        "number"
       ],
       [
        12,
        13,
        "unit"
       ],
       [
        14,
        15,
        "operator"
       ],
       [
        16,
        18,
        "number"
       ],
       [
        18,
        19,
        "operator"
       ]
      ],
      "answer": "1,020.00 $",
      "total": false,
      "status": "Разом: 5,795.00 $"
     },
     {
      "text": "разом",
      "spans": [
       [
        0,
        5,
        "keyword"
       ]
      ],
      "answer": "5,795.00 $",
      "total": true,
      "status": "Разом: 11,590.00 $"
     }
    ],
    "total": "Разом: 11,590.00 $"
   },
   "money": {
    "name": "Покупки в Лондоні",
    "lines": [
     {
      "text": "# Покупки в Лондоні",
      "spans": [
       [
        0,
        19,
        "heading"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "Куртка: 89 £ у USD",
      "spans": [
       [
        0,
        8,
        "label"
       ],
       [
        8,
        10,
        "number"
       ],
       [
        11,
        12,
        "unit"
       ],
       [
        13,
        14,
        "keyword"
       ],
       [
        15,
        18,
        "unit"
       ]
      ],
      "answer": "119.51 $",
      "total": false,
      "status": "Разом: 119.51 $"
     },
     {
      "text": "Кава 4.50 £ × 6 у EUR",
      "spans": [
       [
        5,
        9,
        "number"
       ],
       [
        10,
        11,
        "unit"
       ],
       [
        12,
        13,
        "operator"
       ],
       [
        14,
        15,
        "number"
       ],
       [
        16,
        17,
        "keyword"
       ],
       [
        18,
        21,
        "unit"
       ]
      ],
      "answer": "32.36 €",
      "total": false,
      "status": "Разом: 139.02 €"
     },
     {
      "text": "20% знижки від 80 $",
      "spans": [
       [
        0,
        2,
        "number"
       ],
       [
        2,
        3,
        "operator"
       ],
       [
        4,
        14,
        "keyword"
       ],
       [
        15,
        17,
        "number"
       ],
       [
        18,
        19,
        "unit"
       ]
      ],
      "answer": "64.00 $",
      "total": false,
      "status": "Разом: 219.77 $"
     },
     {
      "text": "Пробіжка: 10 км у милях",
      "spans": [
       [
        0,
        10,
        "label"
       ],
       [
        10,
        12,
        "number"
       ],
       [
        13,
        15,
        "unit"
       ],
       [
        16,
        17,
        "keyword"
       ],
       [
        18,
        23,
        "unit"
       ]
      ],
      "answer": "6.214 милі",
      "total": false,
      "status": "Разом: 219.77 $"
     },
     {
      "text": "Духовка 180 °C у °F",
      "spans": [
       [
        8,
        11,
        "number"
       ],
       [
        12,
        14,
        "unit"
       ],
       [
        15,
        16,
        "keyword"
       ],
       [
        17,
        19,
        "unit"
       ]
      ],
      "answer": "356 °F",
      "total": false,
      "status": "Разом: 219.77 $"
     },
     {
      "text": "1.5 ТБ при 25 МБ/с у годинах",
      "spans": [
       [
        0,
        3,
        "number"
       ],
       [
        4,
        6,
        "unit"
       ],
       [
        7,
        10,
        "keyword"
       ],
       [
        11,
        13,
        "number"
       ],
       [
        14,
        16,
        "unit"
       ],
       [
        16,
        17,
        "operator"
       ],
       [
        17,
        18,
        "unit"
       ],
       [
        19,
        20,
        "keyword"
       ],
       [
        21,
        28,
        "unit"
       ]
      ],
      "answer": "16.667 години",
      "total": false,
      "status": "Разом: 219.77 $"
     }
    ],
    "total": "Разом: 219.77 $"
   },
   "dates": {
    "name": "Поїздка до Португалії",
    "lines": [
     {
      "text": "# Поїздка до Португалії",
      "spans": [
       [
        0,
        23,
        "heading"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "@від 2026-11-14",
      "spans": [
       [
        0,
        4,
        "keyword"
       ],
       [
        5,
        15,
        "number"
       ]
      ],
      "answer": "14 листопада",
      "total": false,
      "status": ""
     },
     {
      "text": "Лісабон: 3 дні",
      "spans": [
       [
        0,
        9,
        "label"
       ],
       [
        9,
        10,
        "number"
       ],
       [
        11,
        14,
        "unit"
       ]
      ],
      "answer": "17 листопада",
      "total": false,
      "status": ""
     },
     {
      "text": "Порту: 2 дні",
      "spans": [
       [
        0,
        7,
        "label"
       ],
       [
        7,
        8,
        "number"
       ],
       [
        9,
        12,
        "unit"
       ]
      ],
      "answer": "19 листопада",
      "total": false,
      "status": ""
     },
     {
      "text": "// літак додому 18 листопада",
      "spans": [
       [
        0,
        28,
        "comment"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "@до 2026-11-18",
      "spans": [
       [
        0,
        3,
        "keyword"
       ],
       [
        4,
        14,
        "number"
       ]
      ],
      "answer": "перевищено: 1 день",
      "total": false,
      "status": "Разом: -1 день"
     },
     {
      "text": "2026-11-14 + 3 тижні",
      "spans": [
       [
        0,
        10,
        "number"
       ],
       [
        11,
        12,
        "operator"
       ],
       [
        13,
        14,
        "number"
       ],
       [
        15,
        20,
        "unit"
       ]
      ],
      "answer": "5 грудня",
      "total": false,
      "status": "Разом: -1 день"
     },
     {
      "text": "днів між 2026-11-14 і 2026-12-25",
      "spans": [
       [
        0,
        4,
        "unit"
       ],
       [
        5,
        8,
        "keyword"
       ],
       [
        9,
        19,
        "number"
       ],
       [
        20,
        21,
        "keyword"
       ],
       [
        22,
        32,
        "number"
       ]
      ],
      "answer": "41 день",
      "total": false,
      "status": "Разом: 40 днів"
     }
    ],
    "total": "Разом: 40 днів"
   },
   "spelling": {
    "name": "Ремонт кухні",
    "lines": [
     {
      "text": "# Ремонт кухні",
      "spans": [
       [
        0,
        14,
        "heading"
       ]
      ],
      "answer": "",
      "total": false,
      "status": ""
     },
     {
      "text": "Плитка: 650 грн × 12",
      "spans": [
       [
        0,
        8,
        "label"
       ],
       [
        8,
        11,
        "number"
       ],
       [
        12,
        15,
        "unit"
       ],
       [
        16,
        17,
        "operator"
       ],
       [
        18,
        20,
        "number"
       ]
      ],
      "answer": "7,800.00 ₴",
      "total": false,
      "status": "Разом: 7,800.00 ₴"
     },
     {
      "text": "Шпаклівкаа: 4 × 380 грн",
      "spans": [
       [
        0,
        12,
        "label"
       ],
       [
        12,
        13,
        "number"
       ],
       [
        14,
        15,
        "operator"
       ],
       [
        16,
        19,
        "number"
       ],
       [
        20,
        23,
        "unit"
       ]
      ],
      "answer": "1,520.00 ₴",
      "total": false,
      "status": "Разом: 9,320.00 ₴"
     },
     {
      "text": "Робота 15,000 грн",
      "spans": [
       [
        7,
        13,
        "number"
       ],
       [
        14,
        17,
        "unit"
       ]
      ],
      "answer": "15,000.00 ₴",
      "total": false,
      "status": "Разом: 24,320.00 ₴"
     },
     {
      "text": "Кухонні меблі 48,000 грн − 10%",
      "spans": [
       [
        14,
        20,
        "number"
       ],
       [
        21,
        24,
        "unit"
       ],
       [
        25,
        26,
        "operator"
       ],
       [
        27,
        29,
        "number"
       ],
       [
        29,
        30,
        "operator"
       ]
      ],
      "answer": "43,200.00 ₴",
      "total": false,
      "status": "Разом: 67,520.00 ₴"
     },
     {
      "text": "разом",
      "spans": [
       [
        0,
        5,
        "keyword"
       ]
      ],
      "answer": "67,520.00 ₴",
      "total": true,
      "status": "Разом: 135,040.00 ₴"
     }
    ],
    "total": "Разом: 135,040.00 ₴",
    "misspelled": {
     "line": 2,
     "start": 0,
     "end": 10
    },
    "suggestions": [
     "Шпаклівка",
     "Шпаклівкам",
     "Шпаклівках",
     "Шпаклівка а",
     "Шпаківка"
    ]
   }
  }
 }
};
