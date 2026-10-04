#!/usr/bin/env python3
"""Überwacht ein IMAP-Postfach und legt Termine aus Einladungen (text/calendar
bzw. .ics-Anhänge) als Kalendereinträge in Nextcloud (CalDAV) an."""
import argparse
import email
import imaplib
import logging
import os
import sys
import time
import tomllib
from email import policy
from urllib.parse import quote

import requests
from icalendar import Calendar

log = logging.getLogger("imap2nc")


def extract_calendars(msg):
    """Liefert alle Calendar-Objekte aus text/calendar-Teilen und .ics-Anhängen."""
    cals = []
    for part in msg.walk():
        name = (part.get_filename() or "").lower()
        if part.get_content_type() not in ("text/calendar", "application/ics") \
                and not name.endswith(".ics"):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        try:
            cals.append(Calendar.from_ical(payload))
        except ValueError as e:
            log.warning("Ungültige iCalendar-Daten ignoriert: %s", e)
    return cals


def group_by_uid(cal):
    """Gruppiert VEVENTs nach UID (Serienausnahmen teilen sich die UID)."""
    groups = {}
    for ev in cal.walk("VEVENT"):
        groups.setdefault(str(ev.get("UID")), []).append(ev)
    return groups


class Nextcloud:
    def __init__(self, calendar_url, user, password):
        self.base = calendar_url.rstrip("/") + "/"
        self.s = requests.Session()
        self.s.auth = (user, password)

    def _url(self, uid):
        return f"{self.base}{quote(uid, safe='')}.ics"

    def put(self, cal, uid, events):
        out = Calendar()
        out.add("PRODID", "-//imap-to-nextcloud//DE")
        out.add("VERSION", "2.0")
        for tz in cal.walk("VTIMEZONE"):
            out.add_component(tz)
        for ev in events:
            out.add_component(ev)  # METHOD bewusst weggelassen (CalDAV-konform)
        r = self.s.put(self._url(uid), data=out.to_ical(),
                       headers={"Content-Type": "text/calendar; charset=utf-8"},
                       timeout=30)
        r.raise_for_status()
        return r.status_code  # 201 neu, 204 aktualisiert

    def delete(self, uid):
        r = self.s.delete(self._url(uid), timeout=30)
        if r.status_code != 404:
            r.raise_for_status()


def handle_message(raw, nc):
    """Verarbeitet eine Mail; gibt Anzahl bearbeiteter Termine zurück."""
    msg = email.message_from_bytes(raw, policy=policy.default)
    count = 0
    for cal in extract_calendars(msg):
        method = str(cal.get("METHOD", "PUBLISH")).upper()
        for uid, events in group_by_uid(cal).items():
            if method == "CANCEL":
                nc.delete(uid)
                log.info("Termin %s gelöscht (Absage)", uid)
            elif method in ("REQUEST", "PUBLISH", "ADD"):
                code = nc.put(cal, uid, events)
                log.info("Termin %s %s: %s", uid,
                         "angelegt" if code == 201 else "aktualisiert",
                         events[0].get("SUMMARY"))
            else:  # REPLY, COUNTER, ... sind keine Termine für uns
                continue
            count += 1
    return count


def process_mailbox(conf, nc, imap):
    imap.select(conf["folder"])
    typ, data = imap.search(None, "UNSEEN")
    for num in data[0].split():
        typ, fetched = imap.fetch(num, "(BODY.PEEK[])")
        raw = fetched[0][1]
        try:
            handle_message(raw, nc)
        except Exception:
            log.exception("Fehler bei Mail %s – bleibt ungelesen", num.decode())
            continue
        imap.store(num, "+FLAGS", "\\Seen")
        target = conf.get("processed_folder")
        if target:
            imap.copy(num, target)
            imap.store(num, "+FLAGS", "\\Deleted")
    imap.expunge()


def connect(conf):
    imap = imaplib.IMAP4_SSL(conf["host"], conf.get("port", 993))
    imap.login(conf["user"], os.environ[conf["password_env"]])
    return imap


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-c", "--config", default="config.toml")
    ap.add_argument("--once", action="store_true", help="nur ein Durchlauf")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)
    nc_cfg = cfg["nextcloud"]
    nc = Nextcloud(nc_cfg["calendar_url"], nc_cfg["user"],
                   os.environ[nc_cfg["password_env"]])
    conf = cfg["imap"]
    while True:
        try:
            imap = connect(conf)
            try:
                process_mailbox(conf, nc, imap)
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass
        except Exception:
            log.exception("Durchlauf fehlgeschlagen")
        if args.once:
            return
        time.sleep(conf.get("poll_interval", 60))


if __name__ == "__main__":
    sys.exit(main())
