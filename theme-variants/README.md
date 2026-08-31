# Theme-Varianten (Staging, nicht Teil des Live-Themes)

Dieser Ordner ist **kein** Bestandteil des produktiven Dawn-Themes — er dient nur als
Übergabe-Ablage für zwei neue Theme-Varianten ("Futuristisch" und "Stylisch"), die auf
Shopify als eigene (unveröffentlichte) Themes angelegt werden sollen, per Duplikat des
aktuellen Live-Themes.

## Was noch zu tun ist

1. `themes`-Query ausführen, Rolle `MAIN` finden (aktuelles Live-Theme).
2. `themeDuplicate` **zweimal** auf diesem Theme ausführen → zwei neue UNPUBLISHED Themes
   ("Neonlight – Futuristisch", "Neonlight – Stylisch").
3. Auf jedem der beiden neuen (unveröffentlichten) Themes `themeFilesUpsert` mit den
   Dateien aus dem jeweiligen Unterordner ausführen, gemäss folgender Pfad-Zuordnung:

   **futuristisch/ → Theme "Neonlight – Futuristisch"**
   | Datei hier | Ziel-Pfad im Theme |
   |---|---|
   | `hero-futuristisch.liquid` | `sections/hero-futuristisch.liquid` |
   | `futuristisch-theme.css` | `assets/futuristisch-theme.css` |
   | `theme.liquid` | `layout/theme.liquid` (überschreibt die Kopie im neuen Theme) |
   | `settings_data.json` | `config/settings_data.json` |
   | `index.json` | `templates/index.json` |

   **stylisch/ → Theme "Neonlight – Stylisch"**
   | Datei hier | Ziel-Pfad im Theme |
   |---|---|
   | `hero-stylisch.liquid` | `sections/hero-stylisch.liquid` |
   | `stylisch-theme.css` | `assets/stylisch-theme.css` |
   | `theme.liquid` | `layout/theme.liquid` (überschreibt die Kopie im neuen Theme) |
   | `settings_data.json` | `config/settings_data.json` |
   | `index.json` | `templates/index.json` |

4. Preview-Links der beiden neuen Themes an den User schicken (nicht veröffentlichen —
   das entscheidet der User selbst).
5. Diesen `theme-variants/`-Ordner danach aus dem Branch entfernen (war nur Übergabe-Staging).

## Wichtige Vorgaben (bereits umgesetzt)

- **Stylisch**: Der pinke Hero-Bereich (`.hs-hero__block` in `hero-stylisch.liquid`) ist
  bewusst **voll blickdicht** (`background:#FF2E8A; opacity:1`) — explizite Anforderung
  des Users, abweichend vom letzten Mockup-Stand (dort war der Bereich halbtransparent
  mit Foto-Durchschein).
- Beide Varianten nutzen die reale `featured-collection`-Section (echte Produkte) statt
  der im Mockup gezeigten Fake-"Sortiment"-Karten mit erfundenen Preisen. Die im Mockup
  gezeigte Instagram-Mosaik-Section wurde ebenfalls bewusst weggelassen (kein echter
  `@neonlight.ch`-Account bestätigt).
- Farbschemata und `buttons_radius` in `settings_data.json`:
  - Futuristisch: dunkel `#05060C` / Cyan `#3FE0E6`, hell `#EEF0FB` / Violett `#6C4FE0`,
    `buttons_radius: 6`.
  - Stylisch: dunkel `#0B0B0F` / Lime `#D4FF3D`, hell `#FFE6F1` / Pink `#FF2E8A`,
    `buttons_radius: 999`.

## Kontext

Ausgangspunkt: das aktuelle Live-Theme auf Branch `claude/neonlight-startup-planning-ulq2s1`
(Dawn-Theme, Neonlight-Branding, Konfigurator-Section `neon-configurator.liquid`).
`themeFilesUpsert` funktioniert nur auf unveröffentlichten Themes — daher zuerst
duplizieren, dann Dateien hochladen.
