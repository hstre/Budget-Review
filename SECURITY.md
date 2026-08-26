# Security

## API-Schlüssel

- `DEEPSEEK_API_KEY` ausschließlich als Umgebungsvariable oder GitHub
  Repository Secret setzen.
- Keine Schlüssel in `.env`, Test-Fixtures, Issues, Dossiers oder Logs committen.
- Pull-Request-Workflows erhalten keinen Schlüssel und führen keine Live-Calls aus.
- Transportfehler werden ohne Header, Body oder Secretwert ausgegeben.

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
