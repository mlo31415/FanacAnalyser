# FanacAnalyzer

FanacAnalyzer reads every fanzine index page on fanac.org — about 2,000 of them, covering some 31,000 issues —
and writes the listings which are published back to the site: fanzines by title, by date, by editor, by country,
the newszine listings, and a page for every APA mailing.

It reads the website and writes files. It never writes to the server.

A full run takes roughly half an hour, nearly all of it fetching pages.


## Where everything lives

Three places, each named after the program so that several of these site-maintenance tools can share one folder
without colliding:

| | what it holds |
|---|---|
| the program folder | the code, `FanacAnalyzer Parameters.txt`, the logs, the cached fanzine list |
| `FanacAnalyzer - Inputs\` | everything the program reads: control files, page templates, APA material |
| `FanacAnalyzer - Reports\` | everything it writes |

The two folder names come from the `Input Directory` and `Report Directory` settings, so they can be changed.
A file missing from the Inputs folder is looked for in the program folder as well, so an older flat layout
still works.


## Settings

`FanacAnalyzer Parameters.txt` sits beside the program and holds the settings for this machine — which folders to
use, which APAs to report on, and whether to reuse the cached fanzine list. It is deliberately **not** in git,
because its paths are particular to one machine; `FanacAnalyzer - Inputs\Parameters-sample.txt` **is** in git and
documents every setting with its default.

If you have your own copy of this file, it is yours and the program will not touch it.


## What it reads

### Control files

Each is a plain list, one name per line. `#` starts a comment, and everything from a `#` to the end of the line
is ignored, so you can annotate entries.

| file | what it does |
|---|---|
| `control-topleveldirectories.txt` | which index page(s) to read. Empty or missing means `Classic_Fanzines.html`, which is what you want |
| `control-skippers.txt` | fanzine folders to pass over entirely |
| `control-unskippers.txt` | if this has any entries, **only** these folders are read and the skippers list is ignored. For debugging |
| `control-startat.txt` | begin the scan at this folder rather than the first. For debugging |
| `control-offsite.txt` | fanzines listed on fanac.org but actually hosted elsewhere, so there is no index table to read |
| `control-newszines.txt` | which fanzines count as newszines. Pages can also declare this themselves |
| `control-BogusEditors.txt` | names to leave out of the by-editor listings — "et al", "various" |
| `control-Ignore Page Count Errors.txt` | fanzines which genuinely have no page count, so the run should not complain. `*` matches any run of characters |
| `control-NoCrossReference.txt` | names which should never get a "see …" signpost in the alphabetical listing |
| `control-OnlyThisReport.txt` | name one or more reports here to generate only those. For debugging |

The three marked "for debugging" are steering switches rather than settings, and are not in git.

### Page furniture

`control-Header (…).html` — one per report, giving that page's title and its introductory text. **The first line
of the file is the page title**; everything after it is dropped into the top of the page. `control-Header
(basic).html` is the shared skeleton the others are fitted into, and `control-Default.Footer` closes every page.

### APA material

| file | what it does |
|---|---|
| `Template - Mailing.html`, `Template - APA.html`, `Template - All APAs.html` | the shapes of the three kinds of APA page. Required — without them the APA report is skipped |
| `<apa>-bumpf.txt` | a paragraph describing that APA, dropped into its page. Optional |
| `APA Mailings.xlsx` | Joe Siclari's table of when each mailing came out and who its Official Editor was. Optional, but without it the mailing pages carry no dates or editors |

The spreadsheet's sheet names are matched loosely, so "Shadow-FAPA" there and "Shadow FAPA" in the settings are
recognised as the same APA.


## What it writes

Everything lands in `FanacAnalyzer - Reports\`. The HTML files are the ones published to the site; the text files
are working documents for checking the data.

### The published listings

| file | what it is |
|---|---|
| `Alphabetical_Listing_of_Fanzines.html` | every issue, filed under its fanzine's name. The big one |
| `Chronological_Listing_of_Fanzines.html` | the same issues by date |
| `Alphabetical_Listing_of_Fanzines_by_Editor.html` | grouped by editor, editors alphabetical |
| `Chronological_Listing_of_Fanzines_by_Editor.html` | grouped by editor, issues by date |
| `Alphabetical_Listing_of_Fanzine_Series_by_Editor.html` | one line per fanzine rather than per issue |
| `Chronological_Listing_of_Newszines.html` | newszines only |
| `Series_by_Country.html` | grouped by country of publication |
| `Undated Fanzine Issues.html` | the handful with no date at all |
| `APAs\` | one folder per APA, holding a page per mailing, a page for the APA, and `index.html` listing them all |

A fanzine which changed its name gets a signpost in the alphabetical listings — look up *Starship* and you are
pointed at *Algol*, where its issues are filed.

### Plain-text versions

Three of the listings are also written as plain text, holding the same issues in the same order:
`Alphabetical Listing of Fanzines.txt`, `Chronological Listing of Fanzines.txt` and
`Chronological Listing of Newszines.txt`. `Fanzines in date order.txt` and `Newszines in date order.txt` are
flatter still — one issue per line, with no grouping — and are handy for searching or for feeding to something
else.

### Working documents

`Statistics.txt` is the headline count and the first thing to look at. `Decade counts.txt`, `Counts
diagnostics.txt` and `Reports by year\` break the same numbers down. `Fanzines with odd names.txt`, `Fanzines
with odd page counts.txt` and `Fanzines which are not PDFs.txt` flag things worth a human glance. The three
`Items identified as newszines…` files show how that decision was reached. `mailings.csv` lists every issue
which appeared in an APA mailing; nothing reads it any more, but it is a useful artifact.

### One oddity

`People Canonical Names.txt` lives in the **Reports** folder but is an input: FancyAnalyzer produces it, and
FanacAnalyzer reads it to settle on one spelling per editor. Without it the run still works, but editors' names
are left exactly as the pages spell them.


## Logs

Two files beside the program, rewritten each run:

- `Log - FanacAnalyzer - Detailed Analysis Log.txt` — everything, about 13MB, useful when something specific
  needs chasing
- `Log - FanacAnalyzer - Error Log.txt` — only what needs attention: pages which would not parse, mailings
  naming an APA that is not in the settings, fanzines with no page count, and so on. **Read this one after every
  run.**


## The cached fanzine list

`Saved Fanzine List.json` is what the last run read from the website. Every run which reads the site writes it,
so it is never older than the last real run.

Setting `Use Saved Fanzine List` makes the program reload that file instead of reading the site, which turns a
half-hour run into a few seconds. **It is a developer shortcut, not a way to produce reports for publication**:
the results are as old as the file, and because the Classic Fanzines page is not read, the alphabetical listings
come out with none of their alternate-title signposts. A run which does this says so in the error log.


## Running it

From PyCharm, or:

```
.venv12\Scripts\python.exe FanacAnalyzer.py
```

`requirements.txt` pins the packages, with versions chosen deliberately — a beta of `openpyxl` once misread the
APA spreadsheet silently.

If you redirect the output to a file on Windows, the console can be left on a character set which cannot spell
the accented fanzine names. The program asks for UTF-8 at startup, but `set PYTHONIOENCODING=utf-8` first if
anything looks wrong.


## A note on the code

Several modules here — `HelpersPackage.py`, `Log.py`, `Settings.py`, `FanzineIssueSpecPackage.py` and others —
are not part of this project. They are links to shared code kept in its own repository, created by the
`mklinks*.bat` scripts. Editing one of them changes it for every program in the family.
