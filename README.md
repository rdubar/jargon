# Jargon utility

[![PyPI](https://img.shields.io/pypi/v/jargon-file)](https://pypi.org/project/jargon-file/)

Small CLI for browsing the Jargon File from your terminal — random entries, term lookups, colored output.

> "The Jargon File is a glossary and usage dictionary of slang used by computer programmers. The original Jargon File was a collection of terms from technical cultures such as the MIT AI Lab, the Stanford AI Lab (SAIL) and others of the old ARPANET AI/LISP/PDP-10 communities, including Bolt, Beranek and Newman (BBN), Carnegie Mellon University, and Worcester Polytechnic Institute. It was published in paperback form in 1983 as The Hacker's Dictionary (edited by Guy Steele) and revised in 1991 as The New Hacker's Dictionary (ed. Eric S. Raymond; third edition published 1996)." — [Wikipedia](https://en.wikipedia.org/wiki/Jargon_File)

## Data source

Uses the community-maintained [agiacalone/jargonfile](https://github.com/agiacalone/jargonfile) (~2300 entries). A baseline snapshot is bundled with the package; run `jargon fetch` to update to the latest.

## Install

```bash
uv tool install jargon-file
# or:
pipx install jargon-file
```

### From source

```bash
gh repo clone rdubar/jargon && cd jargon
uv venv && source .venv/bin/activate
uv pip install -e .
```

## Usage

```bash
jargon                  # random entry
jargon endian           # look up a term (case-insensitive, partial match ok)
jargon -a endian        # show all senses
jargon -s hack          # list all matching terms without showing content
jargon hack -a          # show all entries that match 'hack' in full
```

If a lookup has multiple partial matches, `jargon` lists them so you can narrow down. Use `-a` to dump all matches at once.

## Commands

| Command | What it does |
| ------- | ------------ |
| `jargon [term]` | Random entry, or look up a term |
| `jargon fetch` | Update community data to the latest |
| `jargon info` | Show version, data stats, and credits |
| `jargon update` | Check for a newer release and print the upgrade command |
| `jargon build` | Rebuild JSON from a local DocBook XML file |

**Flags:** `-a` / `--all` show all senses (or all matching entries) · `-s` / `--search` list matches without showing content · `--json` override data path

## License

MIT — see [LICENSE](LICENSE).

## Author

**Roger Dubar** — [rdubar@gmail.com](mailto:rdubar@gmail.com) — [github.com/rdubar](https://github.com/rdubar)

## Credits

Original Jargon File by Eric S. Raymond <esr@snark.thyrsus.com> — [catb.org/jargon](https://catb.org/jargon/)

Community edition maintained at [agiacalone/jargonfile](https://github.com/agiacalone/jargonfile) — submissions and corrections welcome there.
