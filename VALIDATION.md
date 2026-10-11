# V0.12 – preverjanje (11. 10. 2026)

## Windows zaganjalniki in posodobitev izvorne kode

- V Linux okolju s PowerShell 7.5.4 in v Windows CI s PowerShell 5.1 je bilo
  uspešno izvedenih **43 kontrolnih preverjanj**, vključno s preprečitvijo nove
  prazne baze ob napačni izrecni izbiri podatkovne mape:
  prva gradnja, hiter zagon brez sprememb, sprememba vsebine ob istem času datoteke,
  dodajanje/odstranjevanje virov, manjkajoča izvršljiva datoteka ali vtičnik,
  napaka prevajalnika/TLS brez veljavne oznake pripravljenosti, pravilna arhitektura
  CRT/TLS, kontrolne vsote arhivov, spremembe priložene kode zlib, stara oznaka
  `ready-v012.txt`, izbor podatkovne mape in izolacija študentskega
  ZIP-a. Prevajalnik in Windows izvršljiva datoteka sta pri teh kontrolnih testih
  simulirana; kontrola vsebine datotek, Git in sestavljanje ZIP-a so dejanski.
- Dejanski začasni Git repozitoriji preverijo uspešen `pull --ff-only`, lokalne
  spremembe, nesledene datoteke, razvejano zgodovino in nedosegljiv remote. Ob napaki
  lokalne datoteke in HEAD ostanejo ohranjeni. ZIP v drugi Git mapi ne prevzame
  napačnega commita.
- Vseh **182 obnovljenih javnih datotek** v `resources/data/` in `build_XX/` se po
  Git hashih ujema z upstream commitom `fc5da465bb15e80b6307f0c9564f5241567f7d86`.
- **Čista lokalna Git kopija brez gradilnih izhodov:** Linux/Qt 5.15.15 gradnja z
  `CONFIG+=ai_test` uspešna; javni viri pridejo iz samega repozitorija. Ponovni
  `make` brez sprememb ne spremeni programa. Po začasni spremembi `src/main.cpp`
  dejanski `make` ponovno prevede kodo in spremeni izvršljivo datoteko. Testna
  sprememba je nato odstranjena in originalna koda ponovno prevedena.
- Uspešni so TLS pregled, izvorni test meritev vezja ter `test_native.py` in
  `test_native_quiz.py` z dejanskim Qt programom in Flask/Waitress strežnikom na
  Linuxu. Prijava, pogovor, pomoč, oddaja, obnovitev kviza po ponovnem zagonu,
  prenos vezja in učiteljevo ocenjevanje so preverjeni v demo načinu.
- Strežniška zbirka iz čiste kopije: **51 testov, OK**. PowerShell skripti so
  sintaktično preverjeni; končna konfiguracija `qmake` je preverjena tudi po
  spremembi Git oznake programa.

**Windows gradnja in zagon paketa sta uspešno preverjena:**
[Windows CI](https://github.com/Rokachello/SimulIDE-AI-Classroom/actions/runs/38093980638)
na Windows Server 2022 je uspešno opravil vseh 43 kontrolnih testov, prenos in
pripravo orodij, gradnjo iz čiste kopije, TLS, preskok gradnje brez sprememb ter
ponovno gradnjo po spremembi vsebine z ohranjenim časom izvorne datoteke. Po
odstranitvi testne spremembe je ponovno prevedel originalno kodo in sestavil
`SimulIDE-AI-Windows.zip` z licenčnimi obvestili. Dejanski `ZAZENI.cmd` iz
razširjenega ZIP-a je odprl Windows SimulIDE; test je preveril naslov okna z
različico **AI 0.12** in Git oznako **e66e2247e307**. To je GitHubov testni merge
commita veje `566050309b12` z `main`, ki ga Actions uporabi za preverjanje PR-ja.
Vsi koraki so zaključeni z `success`; paket in `setup.log` sta na voljo med
artefakti tega zagona.

## Predhodno preverjanje učilnice

- 51 strežniških testov uspešnih: avtorizacija, CSRF, kvizi, oddaje, pomoč, RAG in pregled ure. Kopija ure ostane zaprta, kviz je osnutek, osebna zgodovina se ne kopira.
- Qt/Linux prevod uspešen. Dejanski SimulIDE: prijava, pogovor, pomoč in izziv preverjeni; kviz dodatno preverjen po zadnji spremembi. Odgovori se obnovijo po ponovnem zagonu, zaklep asistenta ostane aktiven, potrjena oddaja odklene pogovor. Prenos oddaje in ročna ocena uspešna.
- Chromium/Playwright: prijava učitelja, pregled dejavnosti, kopiranje, urejanje in shranjevanje ure, odpiranje ure, predogled in objava kviza uspešni. Mobilni prikaz 390 px brez prelivanja strani; brez JavaScript napak. Posnetki uporabljeni za interni vizualni pregled.
- PowerShell zaganjalniki sintaktično preverjeni.

## Omejitve

Windows prevod in dejanski zagon namiznega programa sta preverjena v Windows CI.
Ročni dvoklik na uporabnikovem računalniku in interaktivni zagon Windows strežnika
nista bila izvedena; izbor in ohranitev podatkovne mape preverjajo kontrolni testi,
strežniško delovanje pa navedeni Linux testi.
Resnični OpenAI klici niso bili preizkušeni: integracija uporablja simulirane odgovore v testih. RAG se pripravi z uporabnikovim ključem ob zagonu strežnika.
Osnutki pogovora in kviza se shranijo na istem računalniku/uporabniškem profilu; niso še oddaja učitelju. Vezje shrani s Ctrl+S. Učiteljski obrazci opozarjajo na neshranjene spremembe, nimajo samodejnega shranjevanja.
Pregled kaže zabeleženo dejavnost, ne trenutne spletne prisotnosti. Scaffolding krmilnik in sistematično spremljanje napačnih predstav še nista implementirana. Časovno vzorčenje ni nadomestilo za osciloskop.
