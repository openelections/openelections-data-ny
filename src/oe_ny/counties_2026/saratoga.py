from ._common import block_wide_config

# Saratoga's .xls carries NO office/party labels -- only town headers, candidate
# headers, precinct rows, and town 'Total' subtotals.  The six contests are
# identified by their candidate columns; the map below (candidate tuple ->
# (office_name, party)) was derived from the matching PDF's text layer, which
# labels each contest (e.g. "Comptroller (Dem)", "Member of Congress, 21st
# Congressional District (Dem)", "Senator 44th District (Dem)").  The office_name
# strings here are phrasings parse_office_title canonicalizes (-> Comptroller,
# U.S. House/21, State Senate/44); the two town offices pass through as local
# offices.  All six contests are Vote for 1, so no va_map is needed.
_CONTEST_MAP = {
    ("Thomas P. DiNapoli", "Raj Goyle", "Drew Warshaw"):
        ("Comptroller", "DEM"),
    ("Blake Gendebien", "Stuart J. Amoriell"):
        ("Member of Congress, 21st Congressional District", "DEM"),
    ("Sarah F. Rogerson", "Patrick F. Nelson"):
        ("State Senator 44th District", "DEM"),
    ("Robert J. Smullen", "Anthony Constantino"):
        ("Member of Congress, 21st Congressional District", "REP"),
    ("Eric Connolly", "John Antoski"):
        ("Ballston Supervisor", "REP"),
    ("William Winslow", "Michael D. Baker"):
        ("Northumberland Highway Superintendent", "REP"),
}

CONFIG = block_wide_config(
    county="Saratoga",
    slug="saratoga",
    source_name="Saratoga NY 2026 Primary BoE-PrimaryElection-Results.xls",
    contest_map=_CONTEST_MAP,
)