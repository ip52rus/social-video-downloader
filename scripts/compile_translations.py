"""Compile trusted catalogs deterministically; --check never writes files."""

import argparse
from io import BytesIO
from pathlib import Path
from string import Formatter

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

from social_video_downloader.telegram_i18n import SUPPORTED_LOCALES

LOCALES = tuple(sorted(SUPPORTED_LOCALES))
CATALOG_ROOT = Path(__file__).resolve().parents[1] / "src/social_video_downloader/locales"


def placeholders(text: str) -> set[str]:
    names = set()
    for _, field, specification, conversion in Formatter().parse(text):
        if field is None:
            continue
        if not field.isidentifier() or specification or conversion:
            raise ValueError("Only plain named translation placeholders are supported.")
        names.add(field)
    return names


def compile_catalog(source: Path, locale: str) -> bytes:
    with source.open("rb") as stream:
        catalog = read_po(stream, locale=locale, domain="messages", abort_invalid=True)
    if list(catalog.check()) or any(message.fuzzy for message in catalog if message.id):
        raise ValueError("Invalid or fuzzy translation catalog.")
    for message in catalog:
        if not message.id or "python-brace-format" not in message.flags:
            continue
        originals = message.id if isinstance(message.id, tuple) else (message.id,)
        translations = message.string if isinstance(message.string, tuple) else (message.string,)
        expected = placeholders(originals[0])
        if any(placeholders(text) != expected for text in originals) or any(
            placeholders(text) != expected for text in translations if text
        ):
            raise ValueError("Translation placeholders do not match the source.")
    output = BytesIO()
    write_mo(output, catalog, use_fuzzy=False)
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = True
    for locale in LOCALES:
        source = CATALOG_ROOT / locale / "LC_MESSAGES/messages.po"
        destination = source.with_suffix(".mo")
        compiled = compile_catalog(source, locale)
        if args.check:
            current &= destination.is_file() and destination.read_bytes() == compiled
        else:
            destination.write_bytes(compiled)
    print(
        "Translation catalogs are up to date."
        if current
        else "Translation catalogs need compilation."
    )
    return 0 if current else 1


if __name__ == "__main__":
    raise SystemExit(main())
