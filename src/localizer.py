import yaml
import logging
from pathlib import Path

localizations = {}

# not sure where to put this const
DEFAULT_LANG = "en"


def load():
    """ Concatenates all .yml files """

    localizations = {}
    localization_files_dir = Path(__file__).parent.parent / "static/localization"
    print("localization_files_dir", localization_files_dir)
    for localization_file in localization_files_dir.iterdir():
        if localization_file.is_dir() or localization_file.suffix != ".yml":
            continue

        with open(localization_file, "r") as f:
            localizations |= yaml.safe_load(f)

    logging.info(f"Loaded {len(localizations)} localization strings.")
    print("localizations", localizations)
    return localizations


def t(
    key: str, 
    lang: str | None
) -> str:
    if lang is None or lang not in localizations[key]:
        lang = DEFAULT_LANG

    return localizations[key][lang]
