# Datenfluss

1. `contacts.csv` wird gelesen und auf die Spalten `Name` und `Email`
   reduziert. Weitere Spalten werden ignoriert.
2. Der PDF-Ordner wird nach `*.pdf` durchsucht.
3. Passende Dateinamen werden mit `MM YYYY Lohnabrechnung NAME.pdf` erkannt.
4. Das optionale Suffix ` - Korrektur.pdf` markiert Korrekturausdrucke.
5. Der Name aus dem Dateinamen wird normalisiert und gegen die Kontaktliste
   gematcht.
6. Nicht matchbare Dokumente werden im Plan ausgewiesen und nicht versendet.
7. Matchbare Dokumente werden pro E-Mail-Adresse gruppiert.
8. Aus der Gruppe werden Betreff, Mailtext und PDF-Anhaenge erstellt.
9. Standard ist Dry-Run. SMTP-Versand startet nur mit `--send`.

Die Demo-Dateien sind reine synthetische Platzhalter. Produktive PDF-Inhalte,
Bankdaten, echte Kontakte und Versandlogs gehoeren nicht in dieses Repository.
