import re

COLOR_ALIASES = {
    "синий": "Синий",
    "чёрный": "Чёрный",
    "черный": "Чёрный",
    "белый": "Белый",
    "зелёный": "Зелёный",
    "зеленый": "Зелёный",
    "розовый": "Розовый",
    "фиолетовый": "Фиолетовый",
    "красный": "Красный",
    "жёлтый": "Жёлтый",
    "желтый": "Жёлтый",
    "золотой": "Золотой",
    "графитовый": "Графитовый",
    "серебристый": "Серебристый",
    "титановый": "Титановый",
    "титан": "Титановый",
    "natural titanium": "Титановый Natural",
    "blue titanium": "Титановый Синий",
    "white titanium": "Титановый Белый",
    "black titanium": "Титановый Чёрный",
    "deep purple": "Тёмно-фиолетовый",
    "midnight": "Midnight",
    "starlight": "Starlight",
    "space black": "Space Black",
    "silver": "Серебристый",
    "space gray": "Space Gray",
    "pink": "Розовый",
    "alpine green": "Alpine Green",
    "sierra blue": "Sierra Blue",
    "pacific blue": "Pacific Blue",
    "starlight": "Starlight",
    "midnight": "Midnight",
    "green": "Зелёный",
    "pink": "Розовый",
    "blue": "Синий",
    "black": "Чёрный",
    "white": "Белый",
    "yellow": "Жёлтый",
    "red": "Красный",
    "purple": "Фиолетовый",
}

MEMORY_PATTERNS = [
    r"(\d+)\s*(GB|Gb|ГБ|гб)",
    r"(\d+)\s*(TB|Tb|ТБ|тб)",
]

IPHONE_SPECS = {
    "iPhone 17 Pro Max": {
        "Диагональ": '6,9"',
        "Разрешение": "2868 × 1320 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц, Always-On",
        "Процессор": "Apple A19 Pro",
        "Основная камера": "48 Мп (тройная: Wide + Ultra Wide + Telephoto)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 17 Pro": {
        "Диагональ": '6,3"',
        "Разрешение": "2622 × 1206 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц, Always-On",
        "Процессор": "Apple A19 Pro",
        "Основная камера": "48 Мп (тройная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 17": {
        "Диагональ": '6,3"',
        "Разрешение": "2622 × 1206 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц",
        "Процессор": "Apple A19",
        "Основная камера": "48 Мп (двойная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 17 Air": {
        "Диагональ": '6,6"',
        "Разрешение": "2796 × 1290 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Процессор": "Apple A19",
        "Основная камера": "48 Мп",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM",
        "Разъём": "USB-C",
    },
    "iPhone 17e": {
        "Диагональ": '6,1"',
        "Разрешение": "2556 × 1179 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Процессор": "Apple A18",
        "Основная камера": "48 Мп",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM",
        "Разъём": "USB-C",
    },
    "iPhone 16 Pro Max": {
        "Диагональ": '6,9"',
        "Разрешение": "2868 × 1320 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц, Always-On",
        "Процессор": "Apple A18 Pro",
        "Основная камера": "48 Мп (тройная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 16 Pro": {
        "Диагональ": '6,3"',
        "Разрешение": "2622 × 1206 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц, Always-On",
        "Процессор": "Apple A18 Pro",
        "Основная камера": "48 Мп (тройная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 16 Plus": {
        "Диагональ": '6,7"',
        "Разрешение": "2796 × 1290 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Процессор": "Apple A18",
        "Основная камера": "48 Мп (двойная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 16": {
        "Диагональ": '6,1"',
        "Разрешение": "2556 × 1179 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Процессор": "Apple A18",
        "Основная камера": "48 Мп (двойная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 15 Pro Max": {
        "Диагональ": '6,7"',
        "Разрешение": "2796 × 1290 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц, Always-On",
        "Процессор": "Apple A17 Pro",
        "Основная камера": "48 Мп (тройная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 15 Pro": {
        "Диагональ": '6,1"',
        "Разрешение": "2556 × 1179 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц, Always-On",
        "Процессор": "Apple A17 Pro",
        "Основная камера": "48 Мп (тройная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 15 Plus": {
        "Диагональ": '6,7"',
        "Разрешение": "2796 × 1290 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Процессор": "Apple A16 Bionic",
        "Основная камера": "48 Мп (двойная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 15": {
        "Диагональ": '6,1"',
        "Разрешение": "2556 × 1179 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Процессор": "Apple A16 Bionic",
        "Основная камера": "48 Мп (двойная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "USB-C",
    },
    "iPhone 14 Pro Max": {
        "Диагональ": '6,7"',
        "Разрешение": "2796 × 1290 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц, Always-On",
        "Процессор": "Apple A16 Bionic",
        "Основная камера": "48 Мп (тройная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "Lightning",
    },
    "iPhone 14 Pro": {
        "Диагональ": '6,1"',
        "Разрешение": "2556 × 1179 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц, Always-On",
        "Процессор": "Apple A16 Bionic",
        "Основная камера": "48 Мп (тройная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "Lightning",
    },
    "iPhone 14 Plus": {
        "Диагональ": '6,7"',
        "Разрешение": "2778 × 1284 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Процессор": "Apple A15 Bionic",
        "Основная камера": "12 Мп (двойная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "Lightning",
    },
    "iPhone 14": {
        "Диагональ": '6,1"',
        "Разрешение": "2532 × 1170 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Процессор": "Apple A15 Bionic",
        "Основная камера": "12 Мп (двойная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "Lightning",
    },
    "iPhone 13 Pro Max": {
        "Диагональ": '6,7"',
        "Разрешение": "2778 × 1284 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц",
        "Процессор": "Apple A15 Bionic",
        "Основная камера": "12 Мп (тройная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "Lightning",
    },
    "iPhone 13 Pro": {
        "Диагональ": '6,1"',
        "Разрешение": "2532 × 1170 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Технологии дисплея": "ProMotion до 120 Гц",
        "Процессор": "Apple A15 Bionic",
        "Основная камера": "12 Мп (тройная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "Lightning",
    },
    "iPhone 13": {
        "Диагональ": '6,1"',
        "Разрешение": "2532 × 1170 пикселей",
        "Тип дисплея": "Super Retina XDR (OLED)",
        "Процессор": "Apple A15 Bionic",
        "Основная камера": "12 Мп (двойная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "eSIM / Nano-SIM",
        "Разъём": "Lightning",
    },
    "iPhone 11": {
        "Диагональ": '6,1"',
        "Разрешение": "1792 × 828 пикселей",
        "Тип дисплея": "Liquid Retina HD (LCD)",
        "Процессор": "Apple A13 Bionic",
        "Основная камера": "12 Мп (двойная)",
        "Фронтальная камера": "12 Мп TrueDepth",
        "Face ID": "Да",
        "SIM": "Nano-SIM + eSIM",
        "Разъём": "Lightning",
    },
}

DEFAULT_SPECS = {
    "Диагональ": "—",
    "Разрешение": "—",
    "Тип дисплея": "—",
    "Процессор": "—",
    "Основная камера": "—",
    "Фронтальная камера": "—",
    "Face ID": "—",
    "SIM": "—",
    "Разъём": "—",
}


def extract_color(name: str) -> str | None:
    lower = name.lower()
    # Longer aliases first to match "space black" before "black"
    for alias, color in sorted(COLOR_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in lower:
            return color
    return None


def extract_memory(name: str) -> str | None:
    for pattern in MEMORY_PATTERNS:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            value = match.group(1)
            unit = match.group(2).upper()
            if unit in ("TB", "ТБ"):
                return f"{value} TB"
            return f"{value} GB"
    return None


def extract_model_key(name: str) -> str:
    name_upper = name.upper()
    # Sort keys by length descending so "iPhone 17 Pro Max" matches before "iPhone 17 Pro"
    for key in sorted(IPHONE_SPECS.keys(), key=lambda k: -len(k)):
        if key.upper().replace(" ", "") in name_upper.replace(" ", ""):
            return key
    # Fallback: extract iPhone number + suffix
    match = re.search(r"iPhone\s*(\d+\s*(?:Pro\s*Max|Pro|Plus|Air|e)?)", name, re.IGNORECASE)
    if match:
        return f"iPhone {match.group(1).strip().title()}"
    return ""


def get_specs(name: str) -> dict:
    key = extract_model_key(name)
    flat = dict(DEFAULT_SPECS)
    if key and key in IPHONE_SPECS:
        flat.update(IPHONE_SPECS[key])
    memory = extract_memory(name)
    if memory:
        flat["Память"] = memory

    return {
        "Дисплей": {
            "Диагональ": flat.get("Диагональ", "—"),
            "Разрешение": flat.get("Разрешение", "—"),
            "Тип дисплея": flat.get("Тип дисплея", "—"),
            "Технологии": flat.get("Технологии дисплея", "—"),
        },
        "Производительность": {
            "Процессор": flat.get("Процессор", "—"),
            "Память": flat.get("Память", "—"),
        },
        "Камеры": {
            "Основная камера": flat.get("Основная камера", "—"),
            "Фронтальная камера": flat.get("Фронтальная камера", "—"),
        },
        "Корпус и безопасность": {
            "Face ID": flat.get("Face ID", "—"),
            "Защита от воды": "IP68 (до 6 м на 30 минут)",
            "Материал корпуса": "Алюминий / стекло",
        },
        "Связь и разъёмы": {
            "SIM": flat.get("SIM", "—"),
            "Разъём": flat.get("Разъём", "—"),
            "Сеть": "5G / Wi-Fi 6E / Bluetooth 5.3",
        },
        "Заводские данные": {
            "Страна производителя": "Китай",
            "Гарантия, мес": "12",
        },
        "Комплектация": {
            "В комплекте": "Кабель USB-C, документация",
        },
    }
