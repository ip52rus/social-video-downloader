"""Offline compiled-resource and installed-wheel verification for E1a."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from babel.messages.pofile import PoFileError

ROOT = Path(__file__).resolve().parents[1]


def compiler():
    spec = importlib.util.spec_from_file_location(
        "compile_translations", ROOT / "scripts/compile_translations.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("locale", ["en", "ru", "es"])
def test_compiled_catalog_is_reproducible(locale):
    module = compiler()
    source = module.CATALOG_ROOT / locale / "LC_MESSAGES/messages.po"
    first = module.compile_catalog(source, locale)
    assert first == module.compile_catalog(source, locale) == source.with_suffix(".mo").read_bytes()


def test_compiler_check_is_read_only():
    module = compiler()
    paths = list(module.CATALOG_ROOT.rglob("*.*"))
    before = {p: p.read_bytes() for p in paths}
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/compile_translations.py"), "--check"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "up to date" in result.stdout
    assert before == {p: p.read_bytes() for p in paths}


def test_wheel_installed_outside_checkout_contains_catalogs(tmp_path):
    staging = tmp_path / "source"
    staging.mkdir()
    for name in ("pyproject.toml", "README.md"):
        shutil.copyfile(ROOT / name, staging / name)
    shutil.copytree(
        ROOT / "src", staging / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    build = "from hatchling.build import build_wheel; import sys; build_wheel(sys.argv[1])"
    subprocess.run(
        [sys.executable, "-B", "-c", build, str(wheels)],
        cwd=staging,
        capture_output=True,
        text=True,
        check=True,
    )
    (wheel,) = wheels.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    for locale in ("en", "ru", "es"):
        for suffix in ("po", "mo"):
            assert (
                f"social_video_downloader/locales/{locale}/LC_MESSAGES/messages.{suffix}" in names
            )
    target = tmp_path / "installed"
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(tmp_path / "uv-cache")
    subprocess.run(
        [
            "uv",
            "--offline",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--target",
            str(target),
            str(wheel),
        ],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    # Keep inherited network-denial sitecustomize, but remove source PYTHONPATH entries.
    guards = [
        p
        for p in env.get("PYTHONPATH", "").split(os.pathsep)
        if p and (Path(p) / "sitecustomize.py").is_file()
    ]
    env["PYTHONPATH"] = os.pathsep.join([str(target), *guards])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    probe = """
import json, pathlib, sys
from social_video_downloader import telegram_i18n
from social_video_downloader.telegram_i18n import create_i18n
installed = pathlib.Path(sys.argv[1]).resolve()
assert pathlib.Path(telegram_i18n.__file__).resolve().is_relative_to(installed)
engine = create_i18n()
assert engine.gettext('I18n foundation', locale='ru') == 'Основа локализации'
assert engine.gettext('Choose a format:', locale='ru') == 'Выбери формат:'
assert engine.gettext('TikTok video', locale='es') == 'Vídeo de TikTok'
translated = engine.gettext('{count} file', '{count} files', n=2, locale='es')
assert translated.format(count=2) == '2 archivos'
print(json.dumps(sorted(engine.available_locales)))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", probe, str(target)],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == ["en", "es", "ru"]


@pytest.mark.parametrize("failure", ["placeholder", "fuzzy", "syntax", "brace", "format-spec"])
def test_compiler_refuses_invalid_catalog(tmp_path, failure):
    module = compiler()
    text = (module.CATALOG_ROOT / "ru/LC_MESSAGES/messages.po").read_text()
    if failure == "placeholder":
        text = text.replace('msgstr[0] "{count} файл"', 'msgstr[0] "{other} файл"')
    elif failure == "brace":
        text = text.replace('msgstr[0] "{count} файл"', 'msgstr[0] "{count файл"')
    elif failure == "format-spec":
        text = text.replace('msgstr[0] "{count} файл"', 'msgstr[0] "{count!r} файл"')
    elif failure == "fuzzy":
        text = text.replace("#, python-brace-format", "#, fuzzy, python-brace-format")
    else:
        text += '\nmsgid "unterminated\n'
    path = tmp_path / "messages.po"
    path.write_text(text)
    with pytest.raises((ValueError, PoFileError)):
        module.compile_catalog(path, "ru")


def test_missing_mo_check_fails_without_writing(tmp_path, monkeypatch):
    module = compiler()
    for locale in module.LOCALES:
        target = tmp_path / locale / "LC_MESSAGES/messages.po"
        target.parent.mkdir(parents=True)
        shutil.copyfile(module.CATALOG_ROOT / locale / "LC_MESSAGES/messages.po", target)
    monkeypatch.setattr(module, "CATALOG_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["compile_translations.py", "--check"])
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.po")}
    assert module.main() == 1
    assert not list(tmp_path.rglob("*.mo"))
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.po")}
