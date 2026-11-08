#!/usr/bin/env python3
"""Decide whether this workflow run should build an edition.

Manual runs (workflow_dispatch) always build. Scheduled runs build only when
  1. Europe/Berlin time is Friday 09:00 or later (a late run - GitHub may delay cron by hours -
     still builds, even after midnight into the weekend), and
  2. no edition for the current ISO calendar week exists in archive/ yet.
A skip is a normal green outcome; it is reported in the run summary.
Test locally: GUARD_NOW=2026-11-13T15:42 GITHUB_EVENT_NAME=schedule python scripts/guard.py
"""
import glob, os, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BERLIN = ZoneInfo("Europe/Berlin")


def decide(event, now, archive=ROOT / "archive"):
    iso = now.isocalendar()
    kw = f"{iso[0]}-KW{iso[1]:02d}"
    if event != "schedule":
        return True, f"manual run ({event}) - always builds", kw
    wd = now.weekday()  # Mon=0 ... Fri=4
    if not (wd > 4 or (wd == 4 and now.hour >= 9)):
        return False, f"too early: it is {now:%a %H:%M} Berlin, waiting for Friday 09:00", kw
    if glob.glob(str(archive / f"{kw}-v*.html")):
        return False, f"edition for {kw} is already published", kw
    return True, f"due: {now:%a %H:%M} Berlin and no edition for {kw} yet", kw


def main():
    now = (datetime.fromisoformat(os.environ["GUARD_NOW"]).replace(tzinfo=BERLIN)
           if os.environ.get("GUARD_NOW") else datetime.now(BERLIN))
    run, reason, kw = decide(os.environ.get("GITHUB_EVENT_NAME", "manual"), now)
    print(f"guard: run={run} - {reason}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"run={'true' if run else 'false'}\n")
    if os.environ.get("GITHUB_STEP_SUMMARY") and not run:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"## AI Pulse Weekly\n\nSkipped (not an error): {reason}.\n")
    if not run:
        print(f"::notice::Skipped: {reason}")


if __name__ == "__main__":
    main()
