"""Demo provider: shells out to the Claude Code CLI in headless mode.

    claude -p "<prompt>" --model <alias> --output-format json

Verified flags: -p/--print, --model, --output-format json. Every call goes
through cache.py first, so a rehearsed demo makes zero live calls.
"""
# TODO(M3): subprocess.run with timeout, parse the JSON envelope, extract result text.
