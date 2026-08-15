"""Shared config factories for the 2026 primary.

The Democracy Suite ``All Results Excel.xlsx`` long layout is shared by every
county that exports it, so the engine options are identical; only the county
name, slug, source file, and any office-title overrides differ.
"""
from __future__ import annotations

from ..model import CountyConfig

# Turnout pseudo-offices, placed first in office_order so the single
# per-precinct Ballots Cast / Registered Voters rows sort to the top of each
# precinct's block.  Real contests are not listed, so they sort at rank 99
# alphabetically -- the same order they had under office_order=[].
_TURNOUT_ORDER = [("Ballots Cast", ""), ("Registered Voters", "")]


def long_config(county: str, slug: str, source_name: str,
                office_map: dict | None = None) -> CountyConfig:
    """Config for a Democracy Suite long-XLSX primary source.

    ``office_map`` optionally maps an exact source office title to
    ``(office, district)`` -- use it to supply a district the title omits.
    """
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts={
            "sheet": "Election District Results",
            "columns": {"precinct": 0, "office": 1, "ballot": 3,
                        "party": 5, "total": 6},
            "summary_sheet": "Summary Results",
            "summary_columns": {"office": 0, "ballot": 2, "party": 4,
                                 "total": 5},
            "total_label": "ballots cast",
            "total_includes_under": True,
            "office_map": office_map or {},
        },
    )


def wide_config(county: str, slug: str, source_name: str,
                office_map: dict | None = None) -> CountyConfig:
    """Config for a Democracy Suite wide-XLSX primary source (single
    ``Results`` sheet; no summary sheet, so verification is per-precinct
    arithmetic only)."""
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts={
            "sheet": "Results",
            "columns": {"office": 0, "votes_allowed": 1, "precinct": 2,
                        "ballot": 3, "party": 4, "total": 5},
            "total_label": "total votes cast",
            "total_includes_under": False,
            "total_includes_over": False,
            "office_map": office_map or {},
        },
    )


def wide_per_sheet_config(county: str, slug: str, source_name: str,
                          office_map: dict | None = None) -> CountyConfig:
    """Config for a one-sheet-per-contest wide XLSX (Chautauqua style):
    each sheet has candidates as columns with a ``Total Votes`` column and
    ``Scatterings`` / ``Over Votes`` / ``Under Votes`` trailing columns.
    Verification is per-precinct arithmetic only (no summary sheet)."""
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts={
            "reader": "wide_per_sheet",
            "columns": {"precinct": 0, "office": 1, "ballot": 3,
                        "party": 5, "total": 6},
            "total_label": "ballots cast",
            "total_includes_under": True,
            "total_includes_over": True,
            "office_map": office_map or {},
        },
    )


def _synth_config(county: str, slug: str, source_name: str, reader: str,
                  office_map: dict | None = None,
                  engine_opts: dict | None = None) -> CountyConfig:
    """Config for the synthesized-long-row readers (long_per_sheet, canvass,
    zip_wide).  These readers melt their native layout into the same
    {0:prec,1:office,3:ballot,5:party,6:total} column schema as
    wide_per_sheet, so the engine options are shared.  No summary sheet --
    verification is per-precinct arithmetic only."""
    opts = {
        "reader": reader,
        "columns": {"precinct": 0, "office": 1, "ballot": 3,
                    "party": 5, "total": 6},
        "total_label": "ballots cast",
        "total_includes_under": True,
        "total_includes_over": True,
        "office_map": office_map or {},
    }
    if engine_opts:
        opts.update(engine_opts)
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts=opts,
    )


def long_per_sheet_config(county: str, slug: str, source_name: str,
                          office_map: dict | None = None) -> CountyConfig:
    """Config for a one-sheet-per-precinct XLSX report (Otsego PE26 style)."""
    return _synth_config(county, slug, source_name, "long_per_sheet", office_map)


def canvass_config(county: str, slug: str, source_name: str,
                   canvass_glob: str = "*Canvass Book*.xlsx",
                   office_map: dict | None = None) -> CountyConfig:
    """Config for Erie-style canvass books (one workbook per party, one sheet
    per contest, candidates as columns).  ``canvass_glob`` selects the
    workbook(s) in the source directory."""
    return _synth_config(county, slug, source_name, "canvass", office_map,
                         {"canvass_glob": canvass_glob})


def zip_wide_config(county: str, slug: str, source_name: str,
                    office_map: dict | None = None) -> CountyConfig:
    """Config for a zip of one-XLSX-per-contest (Monroe style): flat precinct
    rows, candidates as columns, explicit WI/OV/UV columns, col 2 = ballots
    total labeled by party."""
    return _synth_config(county, slug, source_name, "zip_wide", office_map)


def html_wide_config(county: str, slug: str, source_name: str,
                     office_map: dict | None = None) -> CountyConfig:
    """Config for a one-table-per-contest HTML results page (Montgomery style):
    ``<h2>title</h2><table>`` with candidate columns + a Write-Ins column and
    precinct rows.  No over/under columns; Ballots Cast = sum(cand)+write-ins."""
    return _synth_config(county, slug, source_name, "html_wide", office_map)


def pdf_config(county: str, slug: str, source_name: str,
               office_map: dict | None = None) -> CountyConfig:
    """Config for an image-only PE26 official-results PDF parsed via its
    PaddleOCR markdown cache (Orleans style): each contest is a centered
    ``"Office (Party) Vote for N"`` title above an HTML table with precinct
    rows, candidate columns, and Over/Under/Write-in/Total Votes columns.
    OCR the PDF first with ``convert_pdfs_paddleocr.py``; the reader consumes
    the ``.paddleocr_cache`` markdown, so no network access at parse time.
    ``office_map`` (exact title -> (office, district)) overrides the shared
    title parser for offices it would mis-canonicalize (e.g. "Representative
    to Congress 24th District" -> ("U.S. House", "24"))."""
    opts = {
        "reader": "pdf",
        "columns": {"precinct": 0, "office": 1, "votes_allowed": 2,
                    "ballot": 3, "party": 5, "total": 6},
        "total_label": "ballots cast",
        "total_includes_under": True,
        "total_includes_over": True,
        "office_map": office_map or {},
    }
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts=opts,
    )


def pdf_table_config(county: str, slug: str, source_name: str, *,
                     office_source: str = "office_line",
                     counting_group_all_only: bool = False,
                     town_precinct_fallback: bool = False,
                     office_map: dict | None = None) -> CountyConfig:
    """Config for a text-layer PE26 PDF parsed via pdfplumber table extraction
    (Chenango/Allegany/Fulton): each contest is a grid of precinct rows and
    candidate columns.  ``office_source`` is ``"office_line"`` (an ``Office:``
    line -- Chenango), ``"col0"`` (the office is the grid's first header cell --
    Allegany), or ``"text_above"`` (the office line sits just above the table --
    Fulton).  ``counting_group_all_only`` keeps only the 'All' copy of a contest
    the source repeats across counting groups (Chenango).  ``office_map`` (exact
    title -> (office, district)) overrides the shared title parser."""
    opts = {
        "reader": "pdf",
        "pdf_layout": "table",
        "columns": {"precinct": 0, "office": 1, "votes_allowed": 2,
                    "ballot": 3, "party": 5, "total": 6},
        "total_label": "ballots cast",
        "total_includes_under": True,
        "total_includes_over": True,
        "office_source": office_source,
        "counting_group_all_only": counting_group_all_only,
        "town_precinct_fallback": town_precinct_fallback,
        "office_map": office_map or {},
    }
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts=opts,
    )


def pdf_blocks_config(county: str, slug: str, source_name: str,
                      office_map: dict | None = None) -> CountyConfig:
    """Config for a per-precinct text-block PE26 PDF (Washington style): each
    page is one precinct with contest blocks -- an "Office - Party Party -
    [District N ]Vote for N" line, candidate rows whose names span two lines,
    and Cast Votes / Undervotes / Overvotes summary lines.  Machine and
    absentee (``ABS``) pages for a precinct are summed by the reader, so
    ``total_includes_over/under`` are False (the source's "Cast Votes" is
    candidate votes only; over/under are added back by the engine for Ballots
    Cast).  Registered Voters come from the precinct-line "N of M registered
    voters".  ``office_map`` (exact title -> (office, district)) overrides the
    shared title parser."""
    opts = {
        "reader": "pdf",
        "pdf_layout": "blocks",
        "columns": {"precinct": 0, "office": 1, "votes_allowed": 2,
                    "ballot": 3, "party": 5, "total": 6},
        "total_label": "ballots cast",
        "total_includes_under": False,
        "total_includes_over": False,
        "office_map": office_map or {},
    }
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts=opts,
    )


def pdf_transposed_config(county: str, slug: str, source_name: str,
                         office_map: dict | None = None) -> CountyConfig:
    """Config for a transposed text-layer PE26 PDF (Tioga style): candidates are
    rows, precincts are rotated columns (each label extracts reversed, decoded
    by grouping chars by x).  One party's primary per page; contests stack
    vertically.  'Total Ballots' is the per-precinct contest total (it includes
    over+under, so total_includes_over/under are True).  No Registered Voters.
    ``office_map`` (exact title -> (office, district)) overrides the shared
    title parser."""
    opts = {
        "reader": "pdf",
        "pdf_layout": "transposed",
        "columns": {"precinct": 0, "office": 1, "votes_allowed": 2,
                    "ballot": 3, "party": 5, "total": 6},
        "total_label": "ballots cast",
        "total_includes_under": True,
        "total_includes_over": True,
        "office_map": office_map or {},
    }
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts=opts,
    )


def pdf_stlaw_config(county: str, slug: str, source_name: str,
                     office_map: dict | None = None) -> CountyConfig:
    """Config for a rotated-header PE26 PDF parsed via its PaddleOCR markdown
    cache (St. Lawrence style): one HTML table per page with the office/party/
    "Vote for N" title in leading colspan rows, precincts as rows, candidates as
    columns.  Over/under are not broken out -- the gap between TOTAL TURNOUT
    (ballots) and TOTAL VOTES CAST (cand+wi) is combined over+under, so
    total_includes_over/under are False and the gap is emitted as Under Votes
    (the engine adds it back for precinct Ballots Cast).  OCR the PDF first with
    ``convert_pdfs_paddleocr.py``; the reader consumes the ``.paddleocr_cache``
    markdown.  ``office_map`` (exact title -> (office, district)) overrides the
    shared title parser (St. Lawrence forces "Representative in Congress" ->
    ("U.S. House", "21") because the county is wholly within NY-21 and OCR
    drops the district number on some pages)."""
    opts = {
        "reader": "pdf",
        "pdf_layout": "stlaw",
        "columns": {"precinct": 0, "office": 1, "votes_allowed": 2,
                    "ballot": 3, "party": 5, "total": 6},
        "total_label": "ballots cast",
        "total_includes_under": False,
        "total_includes_over": False,
        "office_map": office_map or {},
    }
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts=opts,
    )


def pdf_essex_config(county: str, slug: str, source_name: str,
                     office_map: dict | None = None) -> CountyConfig:
    """Config for an Essex-style two-layout canvass PDF (text layer, pdfplumber):
    layout A (rotated candidate-header statewide/federal contests) + layout B
    (transposed town-office contests with district columns).  No OCR.  The
    per-contest 'WHOLE NUMBER OF VOTES CAST' / 'Total Votes Cast For This
    Office' already counts over+under, so total_includes_over/under are True.
    ``office_map`` (exact title -> (office, district)) overrides the shared
    title parser; Essex forces 'Representative in Congress' -> ('U.S. House',
    '21') because the county is wholly within NY-21."""
    opts = {
        "reader": "pdf",
        "pdf_layout": "essex",
        "columns": {"precinct": 0, "office": 1, "votes_allowed": 2,
                    "ballot": 3, "party": 5, "total": 6},
        "total_label": "ballots cast",
        "total_includes_under": True,
        "total_includes_over": True,
        "office_map": office_map or {},
    }
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts=opts,
    )


def pdf_orange_config(county: str, slug: str, source_name: str,
                      office_map: dict | None = None,
                      pdf_glob: str = "Orange PE 2026 RESULTS*.pdf"
                      ) -> CountyConfig:
    """Config for Orange's per-contest PE26 PDF set (7 text-layer PDFs): each
    file is one contest with rotated candidate columns + Write-in / Over Votes
    / Under Votes / Registered Voters / Total Votes Cast.  No OCR.  The reader
    globs ``pdf_glob`` in the source directory (the config's source_name is the
    glob pattern itself, so resolve_source().parent is the source dir).
    'Total Votes Cast' already counts over+under.  ``office_map`` overrides the
    shared title parser for Judicial Delegate / Alternate Judicial Delegate /
    Council Member (the shared parser would mis-map 'Assembly District' to
    State Assembly and would not extract the 'Ward 1' district)."""
    opts = {
        "reader": "pdf",
        "pdf_layout": "orange",
        "pdf_glob": pdf_glob,
        "columns": {"precinct": 0, "office": 1, "votes_allowed": 2,
                    "ballot": 3, "party": 5, "total": 6},
        "total_label": "ballots cast",
        "total_includes_under": True,
        "total_includes_over": True,
        "office_map": office_map or {},
    }
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts=opts,
    )


def block_wide_config(county: str, slug: str, source_name: str,
                      office_map: dict | None = None,
                      contest_map: dict | None = None,
                      va_map: dict | None = None) -> CountyConfig:
    """Config for a block-wide BoE .xls (Oswego/Saratoga PE26 style): one sheet
    with contest blocks stacked vertically, candidate columns + Write-ins/
    Blanks/Voids (and optionally a Total column).  ``contest_map`` (candidate
    tuple -> (office_name, party)) supplies labels when the .xls carries none
    (Saratoga); otherwise labels come from the sheet's party label rows (Oswego).
    ``va_map`` (office -> votes_allowed) marks multi-vote contests so they are
    excluded from precinct Ballots Cast.  Read with python-calamine."""
    opts = {
        "reader": "block_wide",
        "columns": {"precinct": 0, "office": 1, "votes_allowed": 2,
                    "ballot": 3, "party": 5, "total": 6},
        "total_label": "ballots cast",
        "total_includes_under": True,
        "total_includes_over": True,
        "office_map": office_map or {},
    }
    if contest_map:
        opts["contest_map"] = contest_map
    if va_map:
        opts["va_map"] = va_map
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts=opts,
    )


def json_config(county: str, slug: str, source_name: str,
                office_map: dict | None = None) -> CountyConfig:
    """Config for a NY ENR VIC API JSON response cached as a local source file
    (``getdistrictresultsbyparty``).  The reader melts each per-precinct contest
    record into the {0:prec,1:office,2:va,3:ballot,5:party,6:total} schema.
    ``office_map`` maps each contest ``name`` to (office, district) -- required,
    since the API's contest names ("Representative in Congress District 23",
    "Supervisor - Lewiston - Rep") are not canonicalized by the shared title
    parser.  The per-contest Ballots Cast total is candidate+write-in votes (cast
    votes); total_includes_over/under is False so the engine adds over+under back
    to recover true ballots.  ``pos`` (vote-for-N) rides in col 2 so multi-vote
    contests are excluded from precinct Ballots Cast."""
    opts = {
        "reader": "json",
        "columns": {"precinct": 0, "office": 1, "votes_allowed": 2,
                    "ballot": 3, "party": 5, "total": 6},
        "total_label": "ballots cast",
        "total_includes_under": False,
        "total_includes_over": False,
        "office_map": office_map or {},
    }
    return CountyConfig(
        county=county,
        slug=slug,
        engine="primary",
        date="20260623",
        election="primary",
        source_name=source_name,
        office_order=_TURNOUT_ORDER,
        cand={},
        anchors={},
        writeins="named",
        engine_opts=opts,
    )


# borough name -> OpenElections county slug
_NYC_SLUGS = {
    "New York": "new_york", "Kings": "kings", "Queens": "queens",
    "Bronx": "bronx", "Richmond": "richmond",
}


def nyc_config(county: str, source_dir: str | None = None) -> CountyConfig:
    """Config for a NYC borough's EDLevel.csv precinct results (the ``nyc``
    engine).  ``county`` is the borough display name (``"New York"``, ``"Kings"``,
    ``"Queens"``, ``"Bronx"``, ``"Richmond"``); the slug is derived from it.

    The NYC BoE publishes one ``EDLevel.csv`` per contest; the 2026 format
    prepends the 11 column headers to every row (22 fields).  The engine reads
    every ``<borough_prefix>*EDLevel.csv`` under the source directory -- only the
    borough-prefixed files (the ``NYC Crossover/Citywide`` files duplicate the
    borough files and would double-count).  ``borough_prefix`` is ``"<county>
    NY"``.  Only ``IN-PLAY`` rows are emitted; tally categories (Public Counter
    = ballots cast, Absentee/Military, ...) are emitted as candidate rows, the
    repo's NYC convention -- there are no synthesized Ballots Cast/Registered
    Voters pseudo-offices.  ``sort_output`` is False so the shared writer emits
    the engine's (precinct, office, district, party, candidate) sort verbatim,
    matching the standalone ``nyc_parser.py``.  Override the source root with the
    ``OE_NY_SOURCE_DIR`` environment variable."""
    slug = _NYC_SLUGS[county]
    opts = {"borough_prefix": f"{county} NY"}
    if source_dir is not None:
        opts["source_dir"] = source_dir
    return CountyConfig(
        county=county,
        slug=slug,
        engine="nyc",
        date="20260623",
        election="primary",
        office_order=[],
        cand={},
        anchors={},
        writeins="named",
        sort_output=False,
        engine_opts=opts,
    )