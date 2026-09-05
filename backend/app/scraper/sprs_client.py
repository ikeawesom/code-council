"""Client for sprs.parl.gov.sg (Singapore Hansard).

Confirmed by inspecting the Angular bundle (main.*.js): the SPA calls a JSON API
under https://sprs.parl.gov.sg/search/ with these endpoints -

    /fetchData
    /getHansardReport
    /getHansardTopic
    /getMpNameByMpId
    /officialReport/getFile
    /officialReport/download

The endpoints are live and return JSON, but reject guessed query parameters with
{"errorCode":500}. HIGHEST-RISK UNKNOWN: capture a real request from Chrome
devtools (Network tab, filter XHR) while browsing a sitting, then encode the
exact params here. Fallback if that fails: parse the rendered HTML report.

Every response is written to data/fixtures/ by fixtures.py, so the demo can
replay offline (LEX_OFFLINE=1).
"""
# TODO(M2): list_sittings(since), get_report(sitting_date)
