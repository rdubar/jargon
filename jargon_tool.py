#!/usr/bin/env python3
"""Utility for working with the Jargon File."""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from textwrap import indent

from lxml import etree
from lxml import html as lxml_html

try:
    __version__ = _pkg_version("jargon-file")
except PackageNotFoundError:
    __version__ = "dev"

PROJECT_URL = "https://github.com/rdubar/jargon"
PYPI_API_URL = "https://pypi.org/pypi/jargon-file/json"

# Basic ANSI styling for nicer terminal output.
COLOR_EMPH = "\033[36m"   # cyan
COLOR_REF = "\033[35m"    # magenta
COLOR_TITLE = "\033[33m"  # yellow
COLOR_RESET = "\033[0m"


DEFAULT_XML = Path(__file__).resolve().parent / "data" / "jargon.xml"

# Community edition — agiacalone/jargonfile (primary data source)
COMMUNITY_REPO = "agiacalone/jargonfile"
COMMUNITY_API_URL = f"https://api.github.com/repos/{COMMUNITY_REPO}/commits/HEAD"
COMMUNITY_ZIP_TEMPLATE = "https://github.com/{repo}/archive/{sha}.zip"
COMMUNITY_JSON = Path(__file__).resolve().parent / "data" / "community.json"
COMMUNITY_META = Path(__file__).resolve().parent / "data" / "community_meta.json"
DEFAULT_JSON = COMMUNITY_JSON  # community is the primary data source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _progress(msg: str, end: str = "") -> None:
    print(f"\r{msg:<72}", end=end, flush=True)


def _fetch_json_url(url: str, timeout: int = 10) -> dict:
    """Fetch a JSON URL and return the parsed response."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _fmt_date(iso: str) -> str:
    """Return the YYYY-MM-DD portion of an ISO date string."""
    return iso[:10]


def _style(text: str, color: str) -> str:
    return f"{color}{text}{COLOR_RESET}" if text else text


def _detect_installer() -> tuple[str, str]:
    """Return (installer_name, upgrade_command) based on the Python executable path."""
    exe = str(Path(sys.executable).resolve())
    if "uv" in exe and "tools" in exe:
        return "uv tool", "uv tool upgrade jargon-file"
    if "pipx" in exe:
        return "pipx", "pipx upgrade jargon-file"
    return "pip", "pip install --upgrade jargon-file"


# ---------------------------------------------------------------------------
# Community edition — fetch and parse
# ---------------------------------------------------------------------------

def _download_zip(url: str, dest: Path) -> None:
    """Download url to dest with a live progress line."""
    _progress("Downloading community Jargon File…")

    def _reporthook(block: int, block_size: int, total: int) -> None:
        done = block * block_size
        if total > 0:
            pct = min(done / total * 100, 100)
            mb_done = done / 1_048_576
            mb_total = total / 1_048_576
            _progress(f"Downloading… {mb_done:.1f} / {mb_total:.1f} MB  ({pct:.0f}%)")
        else:
            _progress(f"Downloading… {done / 1_048_576:.1f} MB")

    urllib.request.urlretrieve(url, dest, reporthook=_reporthook)
    print()  # newline after progress


def _parse_entry_html(path: Path) -> dict | None:
    """Parse one community entry HTML file into the shared entry schema."""
    try:
        raw = path.read_bytes()
        tree = lxml_html.fromstring(raw)
    except Exception:
        return None

    dt_nodes = tree.xpath('.//dt[@id]')
    if not dt_nodes:
        return None
    dt = dt_nodes[-1]

    entry_id = dt.get("id", "")
    bold = dt.find(".//b")
    term = bold.text_content().strip() if bold is not None else entry_id

    pronunciations = [
        el.text_content().strip()
        for el in dt.xpath('.//span[@class="pronunciation"]')
        if el.text_content().strip()
    ]
    grammar_els = dt.xpath('.//span[@class="grammar"]')
    grammar = grammar_els[0].text_content().strip() if grammar_els else None
    pronunciation = "  ".join(pronunciations) if pronunciations else None

    senses = []
    for dd in tree.xpath('.//dd'):
        paras = dd.xpath('.//p')
        parts = [p.text_content().strip() for p in paras if p.text_content().strip()]
        definition = "\n".join(parts) if parts else dd.text_content().strip()
        if definition:
            senses.append({
                "definition": definition,
                "pronunciation": pronunciation,
                "grammar": grammar,
            })

    if not senses:
        return None

    return {"id": entry_id, "term": term, "senses": senses}


def fetch_community(json_path: Path = COMMUNITY_JSON, meta_path: Path = COMMUNITY_META) -> None:
    """Download the latest community Jargon File and build a JSON cache."""
    json_path = Path(json_path)
    meta_path = Path(meta_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve latest commit via GitHub API
    _progress("Checking latest community commit…")
    try:
        commit_data = _fetch_json_url(
            COMMUNITY_API_URL,
            timeout=15,
        )
        sha = commit_data["sha"]
        commit_date = commit_data["commit"]["committer"]["date"]
    except Exception as exc:
        print(f"\nCould not reach GitHub API: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\rLatest commit: {sha[:8]}  ({_fmt_date(commit_date)}){' ' * 20}")

    zip_url = COMMUNITY_ZIP_TEMPLATE.format(repo=COMMUNITY_REPO, sha=sha)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "jargonfile.zip"

        _download_zip(zip_url, zip_path)

        _progress("Extracting archive…")
        with zipfile.ZipFile(zip_path) as zf:
            members = [m for m in zf.namelist() if "/html/" in m and m.endswith(".html")]
            total_files = len(members)
            zf.extractall(tmp_path, members=members)
        print(f"\rExtracted {total_files} HTML files.{' ' * 20}")

        html_root = next(tmp_path.glob("jargonfile-*/html"), None)
        if html_root is None:
            print("Error: could not find html/ directory in archive.", file=sys.stderr)
            sys.exit(1)

        entry_files = sorted(
            p for p in html_root.rglob("*.html")
            if p.parent != html_root
        )

        entries = []
        total = len(entry_files)
        _progress(f"Parsing 0 / {total} entries…")
        for i, path in enumerate(entry_files, 1):
            if i % 50 == 0 or i == total:
                _progress(f"Parsing {i} / {total} entries…")
            entry = _parse_entry_html(path)
            if entry:
                entries.append(entry)
        print(f"\rParsed {len(entries)} entries from {total} files.{' ' * 20}")

        _progress("Writing community.json…")
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        print(f"\rCommunity data saved → {json_path}{' ' * 20}")

    # Save metadata sidecar
    meta = {
        "commit": sha,
        "commit_date": commit_date,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entries": len(entries),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")

    print(f"Run 'jargon -c' to use the community edition.")


# ---------------------------------------------------------------------------
# Classic XML → JSON
# ---------------------------------------------------------------------------

def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def render_element(node: etree._Element) -> str:
    tag = _local_tag(node.tag)
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        parts.append(render_element(child))
        if child.tail:
            parts.append(child.tail)
    combined = "".join(parts)
    if tag == "emphasis":
        return _style(combined, COLOR_EMPH)
    if tag in {"xref", "ulink", "link", "systemitem"}:
        return _style(combined, COLOR_REF)
    return combined


def render_paragraph(paragraph: etree._Element) -> str:
    parts: list[str] = []
    if paragraph.text:
        parts.append(paragraph.text)
    for child in paragraph:
        parts.append(render_element(child))
        if child.tail:
            parts.append(child.tail)
    combined = "".join(parts)
    return " ".join(combined.split())


def parse_glossentry(glossentry: etree._Element) -> dict:
    entry_id = glossentry.get("id", "")
    term_el = glossentry.find("glossterm")
    term = term_el.text.strip() if term_el is not None else entry_id

    pronunciation = None
    grammar = None
    abbrev = glossentry.find("abbrev")
    if abbrev is not None:
        for emph in abbrev.findall("emphasis"):
            role = emph.attrib.get("role")
            if role == "pronunciation":
                pronunciation = emph.text.strip() if emph.text else None
            if role == "grammar":
                grammar = emph.text.strip() if emph.text else None

    senses = []
    for glossdef in glossentry.findall("glossdef"):
        paras = glossdef.findall("para")
        text_parts = []
        for paragraph in paras:
            rendered = render_paragraph(paragraph)
            if rendered:
                text_parts.append(rendered)
        definition = "\n".join(text_parts) if text_parts else ""
        senses.append({"definition": definition, "pronunciation": pronunciation, "grammar": grammar})

    return {"id": entry_id, "term": term, "senses": senses}


def xml_to_json(xml_path: Path, json_path: Path) -> None:
    xml_path = Path(xml_path)
    json_path = Path(json_path)

    if not xml_path.exists():
        raise FileNotFoundError(f"XML source not found: {xml_path}")

    print(f"Reading XML: {xml_path}")
    with xml_path.open("rb") as xml_file:
        parser = etree.XMLParser(recover=True)
        tree = etree.parse(xml_file, parser)

    root = tree.getroot()
    entries = [parse_glossentry(e) for e in root.findall(".//glossentry")]

    json_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Parsed {len(entries)} entries. Writing JSON → {json_path}")
    with json_path.open("w", encoding="utf-8") as json_file:
        json.dump(entries, json_file, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entry display
# ---------------------------------------------------------------------------

def display_entry(entry: dict, show_all: bool) -> None:
    print("============================================================")
    print(f"{COLOR_TITLE}{entry['term']}{COLOR_RESET}")
    print("============================================================")

    if show_all:
        for i, sense in enumerate(entry["senses"], 1):
            print(f"\nSense {i}:")
            if sense.get("grammar"):
                print(f"  [{sense['grammar']}]")
            if sense.get("pronunciation"):
                print(f"  Pronunciation: {sense['pronunciation']}")
            print(indent(sense["definition"], "  "))
    else:
        sense = random.choice(entry["senses"])
        print(indent(sense["definition"], "  "))


def choose_entry(entries: list[dict], term: str | None) -> dict:
    if not term:
        return random.choice(entries)

    query = term.lower()
    exact = [
        e for e in entries
        if e.get("term", "").lower() == query or e.get("id", "").lower() == query
    ]
    if exact:
        return random.choice(exact)

    partial = [
        e for e in entries
        if query in e.get("term", "").lower() or query in e.get("id", "").lower()
    ]
    if partial:
        return random.choice(partial)

    raise KeyError(f"No entry found for: {term}")


def show_entry(json_path: Path, show_all: bool = False, term: str | None = None) -> dict:
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON data not found: {json_path}")

    with json_path.open("r", encoding="utf-8") as json_file:
        entries = json.load(json_file)

    entry = choose_entry(entries, term)
    display_entry(entry, show_all)
    return entry


def ensure_json(json_path: Path, xml_path: Path, force: bool = False) -> None:
    json_path = Path(json_path)
    xml_path = Path(xml_path)
    needs_regen = force or not json_path.exists()

    if needs_regen:
        if not xml_path.exists():
            print(
                f"Classic data not available. Run 'jargon fetch' to download the community edition.",
                file=sys.stderr,
            )
            sys.exit(1)
        reason = "Rebuilding JSON" if force else "JSON missing; generating"
        print(f"{reason} from {xml_path}")
        xml_to_json(xml_path, json_path)

    if not json_path.exists():
        raise FileNotFoundError(f"Unable to build JSON: {json_path}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_build(args: argparse.Namespace) -> None:
    xml_to_json(args.xml, args.json)


def cmd_fetch(args: argparse.Namespace) -> None:
    fetch_community(COMMUNITY_JSON, COMMUNITY_META)


def cmd_info(args: argparse.Namespace) -> None:
    SEP = "=" * 60
    print(SEP)
    print(f"{COLOR_TITLE}jargon-file {__version__}{COLOR_RESET}   {PROJECT_URL}")
    print(SEP)

    # PyPI release date for installed version
    try:
        data = _fetch_json_url(PYPI_API_URL, timeout=6)
        releases = data.get("releases", {}).get(__version__, [])
        latest_ver = data["info"]["version"]
        if releases:
            release_date = _fmt_date(releases[0]["upload_time"])
            print(f"Released {release_date} on PyPI", end="")
            if latest_ver != __version__:
                print(f"  (latest: {latest_ver} — run: jargon update)", end="")
            print()
    except Exception:
        pass  # offline or version not on PyPI yet

    print()

    # Community edition
    if COMMUNITY_META.exists():
        meta = json.loads(COMMUNITY_META.read_text())
        n = meta.get("entries", "?")
        commit = meta.get("commit", "?")[:8]
        commit_date = _fmt_date(meta.get("commit_date", "?"))
        fetched = _fmt_date(meta.get("fetched_at", "?"))
        print(f"Community edition {n} entries · data {commit_date} ({commit}) · fetched {fetched}")
    elif COMMUNITY_JSON.exists():
        with COMMUNITY_JSON.open() as f:
            n = len(json.load(f))
        print(f"Community edition {n} entries · (run 'jargon fetch' to refresh)")
    else:
        print(f"Community edition not downloaded  (run: jargon fetch)")

    print()
    print("Credits:")
    print(f"  Original Jargon File by Eric S. Raymond <esr@snark.thyrsus.com>")
    print(f"    https://catb.org/jargon/")
    print(f"  Community edition maintained by {COMMUNITY_REPO}")
    print(f"    https://github.com/{COMMUNITY_REPO}")


def cmd_update(args: argparse.Namespace) -> None:
    installer, upgrade_cmd = _detect_installer()
    print(f"Installed: jargon-file {__version__}  (via {installer})")

    try:
        data = _fetch_json_url(PYPI_API_URL, timeout=6)
        latest = data["info"]["version"]
        releases = data.get("releases", {}).get(latest, [])
        release_date = _fmt_date(releases[0]["upload_time"]) if releases else ""
        if latest == __version__:
            date_str = f"  (released {release_date})" if release_date else ""
            print(f"Latest:    {latest}{date_str} — up to date")
        else:
            date_str = f", released {release_date}" if release_date else ""
            print(f"Latest:    {latest}{date_str} — update available!")
    except Exception:
        print("Latest:    (could not reach PyPI)")

    print()
    print("To upgrade the tool:")
    print(f"  {upgrade_cmd}")
    print()
    print("To update community data:")
    print("  jargon fetch")


def cmd_random(args: argparse.Namespace) -> None:
    if not args.json.exists():
        print(
            f"Jargon data not found: {args.json}\n"
            "Run:  jargon fetch",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        show_entry(args.json, show_all=args.show_all, term=args.term)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Show Jargon File entries (random or by term). "
            "Subcommands: fetch, build, info, update."
        ),
        usage="%(prog)s [term] [options]  |  %(prog)s {fetch,build,info,update}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=f"Project home: {PROJECT_URL}",
    )

    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s {__version__}  <{PROJECT_URL}>",
    )
    parser.add_argument(
        "term",
        nargs="*",
        help="Term or id to display (defaults to a random entry); or a subcommand: fetch, build, info, update",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Convert DocBook XML to JSON and exit",
    )
    parser.add_argument(
        "-j", "--json",
        default=DEFAULT_JSON,
        type=Path,
        help="JSON data file",
    )
    parser.add_argument(
        "-x", "--xml",
        default=DEFAULT_XML,
        type=Path,
        help="XML source (classic edition)",
    )
    parser.add_argument(
        "-a", "--all",
        dest="show_all",
        action="store_true",
        help="Show all senses instead of a single random sense",
    )
    parser.set_defaults(build=False, rebuild=False, show_all=False, term=None)

    return parser


def main(argv: list[str] | None = None) -> None:
    argv_list = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()

    if argv_list and argv_list[0] in ("-h", "--help"):
        parser.print_help()
        return

    args = parser.parse_args(argv_list)

    if isinstance(args.term, list):
        joined = " ".join(args.term).strip()
        args.term = joined if joined else None

    # Subcommand dispatch via positional "term" slot
    SUBCOMMANDS = {
        "build":        (True,  "build",  None),
        "xml-to-json":  (True,  "build",  None),
        "fetch":        (False, "fetch",  None),
        "info":         (False, "info",   None),
        "update":       (False, "update", None),
    }

    args.fetch = False
    args.info = False
    args.update = False

    if args.term in SUBCOMMANDS:
        _, flag, _ = SUBCOMMANDS[args.term]
        if flag == "build":
            args.build = True
        else:
            setattr(args, flag, True)
        args.term = None

    if args.build:
        cmd_build(args)
    elif args.fetch:
        cmd_fetch(args)
    elif args.info:
        cmd_info(args)
    elif args.update:
        cmd_update(args)
    else:
        cmd_random(args)


if __name__ == "__main__":
    main()
