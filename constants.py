"""Константы для организации медиафайлов.

Этот модуль содержит все константы, используемые в проекте:
- Поддерживаемые расширения медиафайлов
- Названия приложений для классификации
- Паттерны поиска файлов и папок
"""


class MediaExtensions:
    """Константы для расширений медиафайлов.

    ALL: Множество всех поддерживаемых расширений медиафайлов.
         Включает фото (HEIC, JPG, PNG, DNG), видео (MOV) и метаданные (AAE).
    """

    ALL = {".HEIC", ".JPG", ".PNG", ".DNG", ".MOV", ".AAE"}


class AppNames:
    """Названия приложений для классификации файлов.

    PHOTOS: Стандартное приложение "Фото" iOS (файлы размещаются в корне устройства)
    HALIDE: Камера Halide (RAW + обработанные снимки)
    BLACKMAGIC: Blackmagic Camera (профессиональная видеосъемка)
    MOMENT: Moment Camera (объективы и аксессуары)
    FILMIC: Filmic Pro (кинематографические видео)
    """

    PHOTOS = "устройство"
    HALIDE = "Halide"
    BLACKMAGIC = "Blackmagic Camera"
    MOMENT = "Moment"
    FILMIC = "Filmic"


class FilePatterns:
    """Паттерны для поиска файлов и папок.

    IMG_BASE: Префикс базовых файлов IMG_ (обычные фото)
    IMG_E: Префикс отредактированных файлов IMG_E (Live Photos, обработанные)
    APPLE_PREFIX: Префикс папок устройств Apple
    FILMIC_KEYWORD: Ключевое слово для поиска файлов Filmic
    MOMENT_VERSION: Версия приложения Moment для очистки названий папок
    BLACKMAGIC_VERSION: Версия Blackmagic Cam для очистки названий папок
    IOS_VERSION: Регулярное выражение для определения папок версий iOS
    BLACKMAGIC_SOFTWARE_KEYWORD: Ключевое слово в EXIF для Blackmagic файлов
    """

    IMG_BASE = "IMG_"
    IMG_E = "IMG_E"
    APPLE_PREFIX = "Apple"
    FILMIC_KEYWORD = "filmic"
    MOMENT_VERSION = "Moment "
    BLACKMAGIC_VERSION = "Blackmagic Cam"
    IOS_VERSION = r"^\d+\.\d+$"
    BLACKMAGIC_SOFTWARE_KEYWORD = "blackmagic"
