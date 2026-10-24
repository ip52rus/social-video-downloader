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
    raw_lines = source.read_text(encoding="utf-8").splitlines()
    with source.open("rb") as stream:
        catalog = read_po(stream, locale=locale, domain="messages", abort_invalid=True)
    if (
        catalog.fuzzy
        or list(catalog.check())
        or any(message.fuzzy for message in catalog if message.id)
    ):
        raise ValueError("Invalid or fuzzy translation catalog.")
    for message in catalog:
        if not message.id:
            continue
        originals = message.id if isinstance(message.id, tuple) else (message.id,)
        translations = message.string if isinstance(message.string, tuple) else (message.string,)
        if any(not isinstance(text, str) or not text for text in translations):
            raise ValueError("Translations must not be empty.")
        expected = placeholders(originals[0])
        names = [placeholders(text) for text in (*originals, *translations)]
        if any(names):
            comments = []
            for line in reversed(raw_lines[: message.lineno - 1]):
                if not line.startswith("#"):
                    break
                comments.append(line)
            if not any(
                "python-brace-format" in line[2:].replace(",", " ").split()
                for line in comments
                if line.startswith("#,")
            ):
                raise ValueError(
                    "Placeholder messages must be explicitly marked python-brace-format."
                )
        if any(fields != expected for fields in names):
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
