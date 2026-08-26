# Security

## API-Schlüssel

- CLI und GitHub Actions verwenden `DEEPSEEK_API_KEY` beziehungsweise ein
  GitHub Repository Secret. Die lokale Weboberfläche kann alternativ einen
  benutzerspezifischen Schlüssel unter `~/.config/content-review/settings.json`
  mit Dateirechten `0600` speichern.
- Keine Schlüssel in `.env`, Test-Fixtures, Issues, Dossiers oder Logs committen.
- Die Weboberfläche zeigt gespeicherte Schlüssel nicht erneut an und schreibt
  sie nicht in den Browser-Speicher. Eine leere Eingabe behält den vorhandenen
  Schlüssel bei; zum Löschen dient die ausdrückliche Entfernen-Option.
- Pull-Request-Workflows erhalten keinen Schlüssel und führen keine Live-Calls aus.
- Transportfehler werden ohne Header, Body oder Secretwert ausgegeben.

## Weboberfläche

Der Server bindet standardmäßig nur an `127.0.0.1`. Eine Freigabe im Netzwerk
erfordert `--allow-network` und ist ohne vorgeschaltete Benutzeranmeldung nicht
für eine gemeinsam genutzte Installation vorgesehen. Schreibende Formulare
verwenden ein pro Serverstart erzeugtes CSRF-Token; Antworten werden mit
`Cache-Control: no-store` und einer restriktiven Content Security Policy gesendet.

## Dokumente

Anträge können personenbezogene und vertrauliche Daten enthalten. Ein
Live-Lauf sendet den eingelesenen Inhalt an die konfigurierte DeepSeek API.
Offline-Replay und deterministische Prüfungen verlassen den Rechner nicht.
Vor einem Live-Lauf müssen Auftragsverarbeitung, Rechtsgrundlage,
Vertraulichkeit und Löschregeln durch die betreibende Stelle geklärt sein.

## Meldungen

Bitte Sicherheitsprobleme nicht mit realen vertraulichen Dokumenten reproduzieren. Eine
Meldung sollte einen synthetischen Minimalfall und die betroffene Version
enthalten.
