# Jargon utility

Small CLI for working with the Jargon File. It can convert the bundled DocBook XML into JSON and print a random entry for quick inspiration, with colored emphasis and references.

> “The Jargon File is a glossary and usage dictionary of slang used by computer programmers. The original Jargon File was a collection of terms from technical cultures such as the MIT AI Lab, the Stanford AI Lab (SAIL) and others of the old ARPANET AI/LISP/PDP-10 communities, including Bolt, Beranek and Newman (BBN), Carnegie Mellon University, and Worcester Polytechnic Institute. It was published in paperback form in 1983 as The Hacker's Dictionary (edited by Guy Steele) and revised in 1991 as The New Hacker's Dictionary (ed. Eric S. Raymond; third edition published 1996).” — [Wikipedia](https://en.wikipedia.org/wiki/Jargon_File)

Source data: Jargon File 4.1.0 (DocBook XML), last updated 2003 by Eric S. Raymond.

## Install

### Quick (no clone)
- With uv:
  ```bash
  uv tool install 'git+https://github.com/rdubar/jargon.git'
  ```
- With pip/pipx:
  ```bash
  pipx install 'git+https://github.com/rdubar/jargon.git'
  # or if you really want a global pip install:
  pip install 'git+https://github.com/rdubar/jargon.git'
  ```

### From a clone
Clone via GitHub CLI or git, then install in an isolated env:

- Using gh:
  ```bash
  gh repo clone rdubar/jargon && cd jargon
  ```
- Using git:
  ```bash
  git clone https://github.com/rdubar/jargon.git
  cd jargon
  ```

- With uv (recommended):
  ```bash
  uv venv && source .venv/bin/activate
  uv pip install -e .           # installs lxml and registers the console script
  ```
- With pip:
  ```bash
  python -m venv .venv && source .venv/bin/activate
  pip install -e .
  ```
- Global “just type jargon” install (no venv):
  ```bash
  uv tool install .             # or: pipx install .
  ```

## Usage

- Print a random entry (builds JSON if missing):
  ```bash
  uv run -- jargon              # or simply: jargon
  ```
- Show a specific entry:
  ```bash
  jargon endian                 # term/id lookup (case-insensitive, partial ok)
  ```
- Show all senses for the chosen term:
  ```bash
  jargon --all                  # or: jargon random --all
  ```
- Rebuild JSON explicitly:
  ```bash
  jargon build                  # defaults to data/jargon.xml → data/jargon.json
  ```
- Point at custom locations:
  ```bash
  jargon random --json /tmp/jargon.json --xml ~/Downloads/jargon.xml
  ```

## Commands

- `jargon` or `jargon random` — print a random jargon entry. If `data/jargon.json` is missing, it is built from `data/jargon.xml` first. Pass `--rebuild` to force regeneration.
- `jargon build` — convert DocBook XML to JSON. Paths default to `data/jargon.xml` → `data/jargon.json`, override with `--xml`/`--json`.

Both commands accept `--xml / --json` flags to point at alternative sources/outputs.

## Data files

- `data/jargon.xml` — DocBook source (default input).
- `data/jargon.json` — generated JSON (default output and runtime data).

## Notes

- Requires Python 3.10+. Make sure you include the dot in `pip install -e .`.
- If the console script isn’t on your PATH, you can always run `python jargon_tool.py --help`.

## Credits

This utility incorporates `Jargon File 4.1.0` of 2003 by Eric S. Raymond <esr@snark.thyrsus.com>.
