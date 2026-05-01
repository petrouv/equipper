"""Константы для организации медиафайлов.

Этот модуль содержит все константы, используемые в проекте:
- Поддерживаемые расширения медиафайлов
- Названия приложений для классификации
- Паттерны поиска файлов и папок
"""


class MediaExtensions:
    """Константы для расширений медиафайлов.

    PHOTOS: Стандартные/обработанные фото (HEIC, JPG, JPEG, PNG, TIFF, HEIF).
    RAW: RAW-форматы основных производителей камер.
    VIDEOS: Видео-форматы.
    METADATA: Файлы метаданных (Apple AAE, sidecar XMP).
    ALL: Множество всех поддерживаемых расширений.
    """

    PHOTOS = {".HEIC", ".HEIF", ".JPG", ".JPEG", ".PNG", ".TIF", ".TIFF"}

    # RAW-форматы по производителям:
    # - DNG: Adobe / Apple (Halide) / Leica / Pentax / Ricoh / Sigma (новые)
    # - RAF: Fujifilm
    # - ARW, SR2, SRF: Sony
    # - CR2, CR3, CRW: Canon
    # - NEF, NRW: Nikon
    # - ORF: Olympus / OM System
    # - RW2: Panasonic
    # - RWL: Leica
    # - PEF: Pentax
    # - 3FR, FFF: Hasselblad
    # - IIQ: Phase One
    # - X3F: Sigma (старые)
    # - SRW: Samsung
    # - MRW: Minolta
    # - MEF: Mamiya
    # - MOS: Leaf
    # - ERF: Epson
    # - KDC, DCR: Kodak
    # - RAW: универсальное расширение (Panasonic, Leica и др.)
    RAW = {
        ".DNG",
        ".RAF",
        ".ARW",
        ".SR2",
        ".SRF",
        ".CR2",
        ".CR3",
        ".CRW",
        ".NEF",
        ".NRW",
        ".ORF",
        ".RW2",
        ".RAW",
        ".RWL",
        ".PEF",
        ".3FR",
        ".FFF",
        ".IIQ",
        ".X3F",
        ".SRW",
        ".MRW",
        ".MEF",
        ".MOS",
        ".ERF",
        ".KDC",
        ".DCR",
    }

    VIDEOS = {".MOV", ".MP4", ".M4V", ".INSV", ".LRV", ".THM"}

    # Sidecar-файлы, перемещаемые вместе с основным медиа:
    # - AAE: метаданные редактирования iOS Photos
    # - XMP: универсальные XMP sidecar (Adobe и др.)
    # - SRT: субтитры/телеметрия дронов DJI (записываются рядом с MP4)
    # - LRF: low-resolution preview видео DJI Osmo Action / дронов
    METADATA = {".AAE", ".XMP", ".SRT", ".LRF"}

    ALL = PHOTOS | RAW | VIDEOS | METADATA


class JunkFiles:
    """Системные файлы, которые не несут пользовательского содержимого
    и не должны мешать удалению "пустых" папок.

    NAMES: точные имена файлов
    - .DS_Store: метаданные Finder на macOS
    - Thumbs.db / desktop.ini: Windows

    PREFIXES: префиксы имён
    - ._*: AppleDouble resource forks (появляются при копировании на не-HFS ФС)
    """

    NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
    PREFIXES = ("._",)


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


class DeviceMakers:
    """Канонические названия производителей.

    Ключи — варианты, в которых производитель пишет себя в EXIF поле Make
    (приведённые к нижнему регистру). Значения — каноническое написание,
    как принято у самого производителя в маркетинговых материалах.
    """

    CANONICAL = {
        "fujifilm": "Fujifilm",
        "fuji photo film co., ltd.": "Fujifilm",
        "fuji photo film co.,ltd.": "Fujifilm",
        "fuji photo film co., ltd": "Fujifilm",
        "fuji": "Fujifilm",
        "nikon": "Nikon",
        "nikon corporation": "Nikon",
        "canon": "Canon",
        "sony": "Sony",
        "olympus": "Olympus",
        "olympus corporation": "Olympus",
        "olympus imaging corp.": "Olympus",
        "om digital solutions": "OM System",
        "panasonic": "Panasonic",
        "leica": "Leica",
        "leica camera ag": "Leica",
        "pentax": "Pentax",
        "ricoh": "Ricoh",
        "ricoh imaging company, ltd.": "Ricoh",
        "sigma": "Sigma",
        "hasselblad": "Hasselblad",
        "phase one": "Phase One",
        "phaseone": "Phase One",
        "samsung": "Samsung",
        "gopro": "GoPro",
        "dji": "DJI",
        "sz dji technology co., ltd.": "DJI",
        "sz dji technology co.,ltd": "DJI",
        "hasselblad (dji)": "DJI",
        "insta360": "Insta360",
        "arashi vision": "Insta360",
        "apple": "Apple",
        "google": "Google",
    }


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
