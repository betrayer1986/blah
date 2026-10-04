# IMAP → Nextcloud-Kalender

Fragt ein IMAP-Postfach ab (ungelesene Mails) und überträgt Termine aus
Einladungen (`text/calendar` / `.ics`-Anhang) per CalDAV in einen Nextcloud-Kalender.

- `METHOD:REQUEST/PUBLISH` → Termin anlegen bzw. aktualisieren (UID = Dateiname, daher idempotent)
- `METHOD:CANCEL` → Termin löschen
- Verarbeitete Mails werden als gelesen markiert (optional in Ordner verschoben); bei Fehlern bleiben sie ungelesen und werden erneut versucht.

## Einrichtung
```
pip install -r requirements.txt
cp config.example.toml config.toml   # anpassen
export IMAP_PASSWORD=... NEXTCLOUD_APP_PASSWORD=...
python imap_to_nextcloud.py --once   # Test
python imap_to_nextcloud.py          # Dauerbetrieb (Polling)
```
Für Nextcloud ein App-Passwort (Einstellungen → Sicherheit) verwenden.
Hinweis: Mails ohne ICS-Anhang (reiner Text) werden nicht erkannt.
