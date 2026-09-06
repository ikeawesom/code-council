"""Client for sprs.parl.gov.sg (Singapore Hansard).

The search API is CONFIRMED and verified live on 2026-09-05 (captured from Chrome
devtools, then replayed from this machine with no cookies):

    POST https://sprs.parl.gov.sg/search/searchResult
    Content-Type: application/json
    -> HTTP 200, a JSON array of report metadata records

No authentication, no session cookie and no CSRF token are required; the only
headers that matter are Content-Type and a browser-shaped User-Agent. The
request body is SEARCH_BODY below - every key must be present, the server
rejects partial bodies.

Parameter semantics established by probing:

* dateRange  is the ONLY date filter that has any effect. It takes Solr range
  syntax - "2026-08-01T00:00:00Z TO 2026-08-31T23:59:59Z", or "* TO NOW" for
  everything. The fromday/frommonth/fromyear/today/tomonth/toyear fields are
  decorative: the SPA sends them, the server ignores them. (Aug 2026 explicit
  range -> 365 hits; same fields with "* TO NOW" -> 45,836 hits.)
* keyword    free text. The SPA sends the literal string "undefined" when the
  box is empty, and the server accepts that as "no keyword" - keep it.
* startIndex / endIndex are an inclusive 0-based window, page size = 20 in the
  UI. Pages do not overlap; results carry a 1-based "sno".
* maxResult  on every record is the total hit count for the query, which is how
  you know when to stop paging.
* selectedSort "date_dt desc" gives newest first - what the daily run wants.

Useful response fields: sittingDate ("5-8-2026", d-m-yyyy), reportType
("oral-answer" | "written-answer" | "written-answer-na" | ...), reportId
("written-answer-24144#", note the trailing '#'), title, parlNo, sessionNo,
volumeNo, sittingNo, memberName, portfolio.

CONTENT - both endpoints confirmed 2026-09-05, also anonymous, one field each:

    POST /search/getHansardTopic   {"id": "oral-answer-4165"}
        -> {"resultData", "resultHTML", "type", "sittingDate", "questionCount"}
        resultHTML.content is the item's full debate text as HTML (~22 KB for a
        typical oral answer). htmlContent/htmlFullContent stay null - `content`
        is the field that matters. resultHTML.mpNames is a comma-joined string
        of every speaker.
        GOTCHA: `id` is searchResult's reportId with the trailing '#' STRIPPED.
        "oral-answer-4165#" -> "oral-answer-4165". With the '#' it 400s.

    POST /search/getHansardReport  {"sittingDate": "05-08-2026"}
        -> the ENTIRE sitting in one response (~1 MB, 167 sections, ~963 KB of
        text for 5 Aug 2026). This is the right call for the daily run: one
        request per sitting date instead of fanning out per item.
        GOTCHA: sittingDate is zero-padded dd-mm-yyyy, but searchResult RETURNS
        d-m-yyyy ("5-8-2026"). Normalise before calling or it 500s.

getHansardReport response shape:
    metadata            parlimentNO, sessionNO, volumeNO, sittingNO, sittingDate,
                        dateToDisplay ("Wednesday, 5 August 2026"), speaker, startTimeStr
    takesSectionVOList  ALL the content lives here - 167 entries for 5 Aug 2026.
                        Fields: sectionType, title, subTitle, content (HTML),
                        questionNo, questionCount, startPgNo, endPgNo,
                        clarificationTitle/SubTitle/Text, footNotes.
                        sectionType counts observed: WANA 79, WA 66, OA 16, OS 5, WS 1
                        (OA oral answer, WA written answer, WANA written answer
                        not-answered, OS/WS oral/written statement).
    writtenAnswersVOList / writtenAnsNAVOList / annexureList / a2bList
                        DECOYS - all empty even though the sitting has 145
                        written answers. Do not read them; use takesSectionVOList.
    attendanceList      107 entries (mpName, attendance, locationName)
    vernacularList      12 entries

    GOTCHA: sections carry NO id field, so they cannot be joined back to a
    searchResult reportId. The two access paths are alternatives, not a chain:
      daily sweep -> getHansardReport(sitting_date), iterate takesSectionVOList
      keyword/ad-hoc -> searchResult(...) -> getHansardTopic(reportId minus '#')

    GOTCHA: responses contain non-cp1252 bytes. Always read/write with
    encoding="utf-8" - the Windows default codec raises UnicodeDecodeError.

Every response is written to data/fixtures/ by fixtures.py, so the demo can
replay offline (CC_OFFLINE=1). A verified capture already lives at
data/fixtures/searchResult/2026-08-01_2026-08-31.json.
"""

BASE_URL = "https://sprs.parl.gov.sg/search"
SEARCH_URL = f"{BASE_URL}/searchResult"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin": "https://sprs.parl.gov.sg",
    "referer": "https://sprs.parl.gov.sg/search/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    ),
}

# The server requires the complete body; overlay dateRange/keyword/paging on this.
SEARCH_BODY: dict = {
    "keyword": "undefined",  # literal "undefined" == no keyword, per the SPA
    "fromday": "01",
    "frommonth": "01",
    "fromyear": "2026",
    "today": "31",
    "tomonth": "12",
    "toyear": "2026",
    "dateRange": "* TO NOW",  # the only field that actually filters by date
    "reportContent": "with all the words",
    "parliamentNo": "",
    "selectedSort": "date_dt desc",
    "portfolio": [],
    "mpName": "",
    "rsSelected": "",
    "lang": "",
    "startIndex": "0",
    "endIndex": "19",
    "titleChecked": "false",
    "footNoteChecked": "false",
    "ministrySelected": [],
}


def date_range(start: str, end: str) -> str:
    """Build the Solr range string from two ISO dates, e.g. ("2026-08-01", "2026-08-31")."""
    return f"{start}T00:00:00Z TO {end}T23:59:59Z"


TOPIC_URL = f"{BASE_URL}/getHansardTopic"
REPORT_URL = f"{BASE_URL}/getHansardReport"


def topic_id(report_id: str) -> str:
    """searchResult reportId -> getHansardTopic id ('oral-answer-4165#' -> 'oral-answer-4165')."""
    return report_id.rstrip("#")


def report_date(sitting_date: str) -> str:
    """searchResult sittingDate -> getHansardReport sittingDate ('5-8-2026' -> '05-08-2026')."""
    d, m, y = sitting_date.split("-")
    return f"{int(d):02d}-{int(m):02d}-{y}"


def iso_from_sprs(d_m_yyyy: str) -> str:
    """SPRS d-m-yyyy (unpadded) -> ISO "YYYY-MM-DD", e.g. "5-8-2026" -> "2026-08-05"."""
    d, m, y = d_m_yyyy.split("-")
    return f"{y}-{int(m):02d}-{int(d):02d}"


def sprs_from_iso(iso: str) -> str:
    """ISO "YYYY-MM-DD" -> SPRS dd-mm-yyyy (zero-padded), e.g. "2026-08-05" -> "05-08-2026"."""
    y, m, d = iso.split("-")
    return f"{int(d):02d}-{int(m):02d}-{y}"


def search(
    start_iso: str, end_iso: str, start_index: int = 0, *, offline: bool | None = None
) -> list[dict]:
    """One page (20 records) of searchResult over [start_iso, end_iso] inclusive."""
    from app.scraper.fixtures import call

    body = dict(SEARCH_BODY)
    body["dateRange"] = date_range(start_iso, end_iso)
    body["startIndex"] = str(start_index)
    body["endIndex"] = str(start_index + 19)
    key = f"{start_iso}_{end_iso}" if start_index == 0 else f"{start_iso}_{end_iso}_{start_index}"
    return call("searchResult", key, body, offline=offline)


def list_sitting_dates(start_iso: str, end_iso: str, *, offline: bool | None = None) -> list[str]:
    """Distinct ISO sitting dates over [start_iso, end_iso], newest first.

    Pages searchResult by 20 until start_index reaches the first record's
    maxResult (an empty page also stops paging). In offline mode a
    FixtureMissing on any page after the first stops paging and returns what
    was collected so far; on the first page it propagates.
    """
    from app.scraper.fixtures import FixtureMissing

    seen: dict[str, None] = {}
    start_index = 0
    max_result: int | None = None
    while True:
        try:
            page = search(start_iso, end_iso, start_index, offline=offline)
        except FixtureMissing:
            if start_index == 0:
                raise
            break
        if not page:
            break
        if max_result is None:
            max_result = int(page[0]["maxResult"])
        for record in page:
            seen[iso_from_sprs(record["sittingDate"])] = None
        start_index += 20
        if start_index >= max_result:
            break
    return sorted(seen, reverse=True)


def get_report(sitting_date_iso: str, *, offline: bool | None = None) -> dict:
    """The full getHansardReport payload for one sitting date."""
    from app.scraper.fixtures import call

    key = sprs_from_iso(sitting_date_iso)
    return call("getHansardReport", key, {"sittingDate": key}, offline=offline)


def get_topic(report_id: str, *, offline: bool | None = None) -> dict:
    """The full getHansardTopic payload for one searchResult reportId."""
    from app.scraper.fixtures import call

    key = topic_id(report_id)
    return call("getHansardTopic", key, {"id": key}, offline=offline)
