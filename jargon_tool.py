#!/usr/bin/env python3
"""Utility for working with the Jargon File."""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from textwrap import indent

from lxml import etree


# Basic ANSI styling for nicer terminal output.
COLOR_EMPH = "\033[36m"   # cyan
COLOR_REF = "\033[35m"    # magenta
COLOR_TITLE = "\033[33m"  # yellow
COLOR_RESET = "\033[0m"


DEFAULT_XML = Path(__file__).resolve().parent / "data" / "jargon.xml"
DEFAULT_JSON = Path(__file__).resolve().parent / "data" / "jargon.json"


def _local_tag(tag: str) -> str:
    """Strip any XML namespace from a tag name."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _style(text: str, color: str) -> str:
    return f"{color}{text}{COLOR_RESET}" if text else text


def render_element(node: etree._Element) -> str:
    """Render an element's text content, styling emphasis/references."""
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
    """Render a <para> to styled plain text without dropping nested content."""
    parts: list[str] = []
    if paragraph.text:
        parts.append(paragraph.text)

    for child in paragraph:
        parts.append(render_element(child))
        if child.tail:
            parts.append(child.tail)

    combined = "".join(parts)
    # Collapse excessive whitespace but preserve single spaces.
    return " ".join(combined.split())


def parse_glossentry(glossentry: etree._Element) -> dict:
    """Parse a <glossentry> XML element into a dict entry."""
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

        senses.append(
            {
                "definition": definition,
                "pronunciation": pronunciation,
                "grammar": grammar,
            }
        )

    return {"id": entry_id, "term": term, "senses": senses}


def xml_to_json(xml_path: Path, json_path: Path) -> None:
    """Convert Jargon XML file to a JSON list of entries."""
    xml_path = Path(xml_path)
    json_path = Path(json_path)

    if not xml_path.exists():
        raise FileNotFoundError(f"XML source not found: {xml_path}")

    print(f"Reading XML: {xml_path}")

    with xml_path.open("rb") as xml_file:
        parser = etree.XMLParser(recover=True)
        tree = etree.parse(xml_file, parser)

    root = tree.getroot()

    entries = []
    for glossentry in root.findall(".//glossentry"):
        entry = parse_glossentry(glossentry)
        entries.append(entry)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Parsed {len(entries)} entries. Writing JSON → {json_path}")
    with json_path.open("w", encoding="utf-8") as json_file:
        json.dump(entries, json_file, indent=2, ensure_ascii=False)


def display_entry(entry: dict, show_all: bool) -> None:
    """Print an entry with styling."""
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
    """Pick an entry by term/id (case-insensitive), or at random if not provided."""
    if not term:
        return random.choice(entries)

    query = term.lower()
    exact = [
        e
        for e in entries
        if e.get("term", "").lower() == query or e.get("id", "").lower() == query
    ]
    if exact:
        return random.choice(exact)

    partial = [
        e
        for e in entries
        if query in e.get("term", "").lower() or query in e.get("id", "").lower()
    ]
    if partial:
        return random.choice(partial)

    raise KeyError(f"No entry found for: {term}")


def show_entry(json_path: Path, show_all: bool = False, term: str | None = None) -> dict:
    """Print and return an entry (random or matched)."""
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON data not found: {json_path}")

    with json_path.open("r", encoding="utf-8") as json_file:
        entries = json.load(json_file)

    entry = choose_entry(entries, term)
    display_entry(entry, show_all)

    return entry


def ensure_json(json_path: Path, xml_path: Path, force: bool = False) -> None:
    """Create JSON data from XML if needed (or forced)."""
    json_path = Path(json_path)
    xml_path = Path(xml_path)
    needs_regen = force or not json_path.exists()

    if needs_regen:
        reason = "Rebuilding JSON" if force else "JSON missing; generating"
        print(f"{reason} from {xml_path}")
        xml_to_json(xml_path, json_path)

    if not json_path.exists():
        raise FileNotFoundError(f"Unable to build JSON: {json_path}")


def cmd_build(args: argparse.Namespace) -> None:
    xml_to_json(args.xml, args.json)


def cmd_random(args: argparse.Namespace) -> None:
    ensure_json(args.json, args.xml, force=args.rebuild)
    try:
        show_entry(args.json, show_all=args.show_all, term=args.term)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show Jargon File entries (random or by term). Use --build to regenerate the JSON from DocBook XML.",
        usage="%(prog)s [term] [options] | %(prog)s --build [options]",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "term",
        nargs="*",
        help="Term or id to display (defaults to a random entry)",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Convert DocBook XML to JSON and exit",
    )
    parser.add_argument(
        "-j",
        "--json",
        default=DEFAULT_JSON,
        type=Path,
        help="JSON data file (output for --build; input for lookups)",
    )
    parser.add_argument(
        "-x",
        "--xml",
        default=DEFAULT_XML,
        type=Path,
        help="XML source to build JSON when needed",
    )
    parser.add_argument(
        "-r",
        "--rebuild",
        action="store_true",
        help="Rebuild JSON from XML before picking an entry",
    )
    parser.add_argument(
        "-a",
        "--all",
        dest="show_all",
        action="store_true",
        help="Show all senses instead of a single random sense",
    )

    parser.set_defaults(
        build=False,
        rebuild=False,
        show_all=False,
        term=None,
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    argv_list = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()

    # Show top-level help without rewriting args.
    if argv_list and argv_list[0] in ("-h", "--help"):
        parser.print_help()
        return

    args = parser.parse_args(argv_list)

    # Join multi-word terms to support queries like "black hat".
    if isinstance(args.term, list):
        joined = " ".join(args.term).strip()
        args.term = joined if joined else None

    # Compatibility: allow `jargon build` style.
    if args.term in {"build", "xml-to-json"} and not args.build:
        args.build = True
        args.term = None

    if args.build:
        cmd_build(args)
    else:
        cmd_random(args)


if __name__ == "__main__":
    main()
