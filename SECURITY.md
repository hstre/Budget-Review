# Security

## API-Schlüssel

- CLI und GitHub Actions verwenden `DEEPSEEK_API_KEY` beziehungsweise ein
  GitHub Repository Secret. Die lokale Weboberfläche kann alternativ einen
  benutzerspezifischen Schlüssel unter `~/.config/content-review/settings.json`
  speichern. Die Datei wird atomar geschrieben und auf POSIX-Systemen auf
  `0600` gesetzt. Windows kennt keine Entsprechung; dort schützt allein die
  ACL des Benutzerprofils.
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
verwenden ein pro Serverstart erzeugtes CSRF-Token; auch der Sprachwechsel ist
ein Token-geschütztes POST, kein zustandsänderndes GET. Weiterleitungen gehen
ausschließlich an bekannte eigene Pfade. Antworten werden mit
`Cache-Control: no-store`, `Referrer-Policy: no-referrer` und einer restriktiven
Content Security Policy gesendet.

Es gibt keine Host-Header-Prüfung. Bei DNS-Rebinding kann eine fremde Seite
gegenüber dem Browser same-origin werden. Für die lokale Ein-Benutzer-Alpha ist
das hingenommen; vor einer Freigabe über `--allow-network` muss eine
Authentifizierung vorgeschaltet werden.

Jede über die Weboberfläche gestartete Prüfung schreibt ihr vollständiges
Dossier nach `./review-output/web/<dokument>-<zeitstempel>/`, relativ zum
Arbeitsverzeichnis des Servers. `dossier.json` enthält den Originalwortlaut
aller zugelassenen Claims.

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
