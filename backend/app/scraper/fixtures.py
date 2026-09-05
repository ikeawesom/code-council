"""Record/replay layer over the SPRS client.

record: every live response is saved to data/fixtures/<endpoint>/<key>.json
replay: LEX_OFFLINE=1 serves from disk and never touches the network

This is the demo's insurance policy against venue wifi and site changes.
"""
# TODO(M2)
