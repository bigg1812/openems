### OpenEMS Doc

This project was generated with [Antora](https://antora.org/).

### Was hier von uns ist

Diese Dateien sind die lokalen Ergänzungen in diesem Repository:

- `README.md`
- `antora.yml`
- `build/`
- `tools/`
- `internal/`

### Was aus dem OpenEMS-Repo kommt

Die eigentlichen Dokumentationsinhalte liegen überwiegend unter `modules/ROOT/pages/` sowie in `modules/ROOT/assets/` und `modules/ROOT/nav.adoc`.

Wenn du eine Seite im Browser siehst, stammt der Inhalt also meistens aus dem OpenEMS-Dokumentationsbestand. Unsere Änderungen sitzen vor allem in den lokalen Build- und Ordnungsdateien oben.

### Building pages

Use the package-manager of your choice to install and generate the `uibundle_openems.zip`.

```bash
npx antora ./build/site.yml
```

Open the `index.html` inside it.
