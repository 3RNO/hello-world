"""Command line entry point.

    python3 -m futdash                 # start the dashboard
    python3 -m futdash --demo          # start it with example data
    python3 -m futdash --import x.csv  # load prices from a CSV and exit
"""

from __future__ import annotations

import argparse
import sys
import webbrowser

from . import config, db, demo, sources


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="futdash", description="FUT trading dashboard")
    ap.add_argument("--db", default=None, help=f"database path (default {db.DEFAULT_PATH})")
    ap.add_argument("--host", default=config.HOST)
    ap.add_argument("--port", type=int, default=config.PORT)
    ap.add_argument("--platform", default=config.PLATFORM, choices=["pc", "console"])
    ap.add_argument("--demo", action="store_true", help="seed example data (in memory)")
    ap.add_argument("--import", dest="csv", metavar="FILE", help="import prices from CSV, then exit")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)

    config.PLATFORM = args.platform
    conn = db.connect(":memory:" if args.demo else args.db)

    if args.demo:
        info = demo.seed(conn)
        print(f"Seeded {info['players']} cards with {info['days']} days of prices "
              f"(in memory -- nothing is written to disk).")

    if args.csv:
        try:
            n = sources.record(conn, sources.CsvSource(args.csv).fetch())
        except (OSError, sources.SourceError) as exc:
            print(f"Import failed: {exc}", file=sys.stderr)
            return 1
        print(f"Imported {n} prices from {args.csv}")
        return 0

    from .server import serve
    httpd = serve(conn, args.host, args.port)
    url = f"http://{args.host}:{args.port}/"
    print(f"FUT Dash — FC {config.GAME_YEAR}, {config.PLATFORM.upper()} market")
    print(f"Running at {url}   (ctrl-c to stop)")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
