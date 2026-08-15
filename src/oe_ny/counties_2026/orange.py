from ._common import pdf_orange_config

# The shared parse_office_title would mis-map these three: "Assembly District"
# triggers State Assembly, and "Council Member Ward 1" needs the "Ward 1"
# district extracted.  Map them explicitly; the other contests (Comptroller,
# State Senate 39/42, and the precinct-derived "Newburgh Town Justice")
# canonicalize / pass through cleanly.
_OFFICE_MAP = {
    "99th Assembly District Judicial Delegates": ("Judicial Delegate", "99"),
    "99th Assembly District Alternate Judicial Delegates":
        ("Alternate Judicial Delegate", "99"),
    "Council Member Ward 1": ("Council Member", "Ward 1"),
}

CONFIG = pdf_orange_config(
    county="Orange",
    slug="orange",
    source_name="Orange PE 2026 RESULTS*.pdf",
    office_map=_OFFICE_MAP,
)