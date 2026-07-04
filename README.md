# Payroll PDF Mailer

Python-Projekt zur sicheren Versandplanung von Lohnabrechnungs-PDFs. Die
oeffentliche Version liest synthetische PDF-Dateinamen, matcht sie gegen eine
Kontakt-CSV, gruppiert mehrere Dokumente pro Empfaenger und erzeugt einen
Dry-Run-Plan. Produktiver SMTP-Versand ist nur mit explizitem `--send` moeglich.

Das Repository enthaelt keine echten Lohnabrechnungen, Kontakte, Logs,
Zugangsdaten, Bankdaten oder Unternehmensdaten.

## Funktionen

- PDF-Dateinamen im Format `MM YYYY Lohnabrechnung NAME.pdf` parsen.
- Korrekturausdrucke mit Suffix ` - Korrektur.pdf` erkennen.
- Kontakte aus `contacts.csv` ueber normalisiertes Token-Matching zuordnen.
- Alle Dokumente pro E-Mail-Adresse in einer Sammelmail gruppieren.
- Betreff und Mailtext mit deutschem Monatslabel erzeugen.
- Dry-Run-Vorschau als Standard; Live-SMTP nur nach explizitem `--send`.
- Optionaler Override-Empfaenger fuer sichere Testsendungen.

## Projektstruktur

- `src/payroll_pdf_mailer/` - Kernlogik, E-Mail-Erzeugung und CLI.
- `beispiele/` - synthetische Kontaktliste und Demo-PDFs.
- `tests/` - fokussierte Tests fuer Parsing, Matching, Gruppierung und Mailaufbau.
- `docs/` - technischer Datenfluss.

## Voraussetzungen

- Python 3.10 oder neuer
- Keine Laufzeitabhaengigkeiten ausser der Python-Standardbibliothek
- `pytest` nur fuer lokale Tests

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

## Konfiguration

Die Demo benoetigt keine SMTP-Konfiguration.

Fuer Live-Versand eine lokale `.env` aus `.env.example` erstellen und echte
Werte ausserhalb des Repositories pflegen:

```powershell
Copy-Item .env.example .env
```

Erwartete Variablen:

- `PAYROLL_SMTP_HOST`
- `PAYROLL_SMTP_PORT`
- `PAYROLL_SMTP_USER`
- `PAYROLL_SMTP_PASS`
- `PAYROLL_SMTP_FROM`
- `PAYROLL_SENDER_NAME`

## Ausfuehrung

Synthetische Demo als Dry-Run:

```powershell
python -m payroll_pdf_mailer --pdf-dir beispiele\payslips --contacts beispiele\contacts.csv
```

Nach Installation kann auch das Konsolen-Script genutzt werden:

```powershell
payroll-pdf-mailer --pdf-dir beispiele\payslips --contacts beispiele\contacts.csv
```

Sicherer SMTP-Test an eine einzelne Testadresse:

```powershell
python -m payroll_pdf_mailer --pdf-dir beispiele\payslips --contacts beispiele\contacts.csv --env-file .env --send --override-to test@example.test --log versand_log.csv
```

Live-Versand an die Kontakte aus der CSV:

```powershell
python -m payroll_pdf_mailer --pdf-dir eingang\lohnabrechnungen --contacts eingang\contacts.csv --env-file .env --send --log versand_log.csv
```

## Beispiel oder Demo

Die Demo verarbeitet drei synthetische PDFs:

- zwei Dokumente fuer denselben Demo-Empfaenger,
- ein Dokument fuer einen zweiten Demo-Empfaenger,
- keine echten PDF-Inhalte oder personenbezogenen Daten.

Der Dry-Run zeigt Empfaenger, Betreff und Anhaenge, versendet aber nichts.

## Tests

```powershell
python -m pytest
```

Weitere lokale Pruefungen:

```powershell
python -m compileall src tests
python -m payroll_pdf_mailer --pdf-dir beispiele\payslips --contacts beispiele\contacts.csv
```

## Einschraenkungen

Das Projekt enthaelt nicht das vorgelagerte Splitten von Sammel-PDFs,
Massenueberweisungen, produktive SMTP-Zugaenge, Keyring-Anbindung oder echte
Versandhistorie. Die oeffentliche Version demonstriert die bereinigte
Versandplanung und den kontrollierten SMTP-Versand auf Basis bereits
getrennter PDF-Dateien.

## Datenschutz

Alle Beispieldaten sind synthetisch und verwenden reservierte Demo-Domains. Das
Repository enthaelt keine echten Mitarbeitenden, E-Mail-Adressen,
Lohnabrechnungen, IBANs, Versandlogs, Bankdaten oder produktiven Zugangsdaten.
