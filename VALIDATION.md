# V0.12 – preverjanje (10. 10. 2026)

- 51 strežniških testov uspešnih: avtorizacija, CSRF, kvizi, oddaje, pomoč, RAG in pregled ure. Kopija ure ostane zaprta, kviz je osnutek, osebna zgodovina se ne kopira.
- Qt/Linux prevod uspešen. Dejanski SimulIDE: prijava, pogovor, pomoč in izziv preverjeni; kviz dodatno preverjen po zadnji spremembi. Odgovori se obnovijo po ponovnem zagonu, zaklep asistenta ostane aktiven, potrjena oddaja odklene pogovor. Prenos oddaje in ročna ocena uspešna.
- Chromium/Playwright: prijava učitelja, pregled dejavnosti, kopiranje, urejanje in shranjevanje ure, odpiranje ure, predogled in objava kviza uspešni. Mobilni prikaz 390 px brez prelivanja strani; brez JavaScript napak. Posnetki uporabljeni za interni vizualni pregled.
- PowerShell zaganjalniki sintaktično preverjeni.

## Omejitve

Windows prevod in zagon v tem okolju nista bila izvedena. Resnični OpenAI klici niso bili preizkušeni: integracija uporablja simulirane odgovore v testih. RAG se pripravi z uporabnikovim ključem ob zagonu strežnika.
Osnutki pogovora in kviza se shranijo na istem računalniku/uporabniškem profilu; niso še oddaja učitelju. Vezje shrani s Ctrl+S. Učiteljski obrazci opozarjajo na neshranjene spremembe, nimajo samodejnega shranjevanja.
Pregled kaže zabeleženo dejavnost, ne trenutne spletne prisotnosti. Scaffolding krmilnik in sistematično spremljanje napačnih predstav še nista implementirana. Časovno vzorčenje ni nadomestilo za osciloskop.
