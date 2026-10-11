# Windows paket in zaznava DeepGuard

Zaznava, ki jo je sporočil uporabnik: **Suspicious:W32/Malware!DeepGuard.ag**.
Zaščite ne izklapljaj, ne dodajaj izjem in ne obnavljaj datotek iz karantene za
preizkušanje. Če zaščita blokira tudi lokalno gradnjo, se preizkus tam ustavi.
Obravnava pri WithSecure še ni opravljena; zaznave ne razglašamo za lažno pozitivno.

## Potrjeno iz uporabnikovega dnevnika

Uporabnik je posredoval dva neuspešna poskusa 11. 10. 2026 ob `11:46:32` in
`11:51:52` (časovni pas Windows dnevnika ni potrjen). Osebna pot je izpuščena:

```text
SimulIDE AI 0.12; mapa: <razsirjeni Windows paket>
NAPAKA: Program 'simulide.exe' failed to run: Access is denied
scripts/windows-common.ps1:19
& $Program @Arguments 2>&1 | ForEach-Object { ... }
```

V tem prenosnem paketu je prvi klic `Invoke-Checked` zagon lokalnega
`bin/simulide.exe -ai-check-tls`. Njegov poskus zagona je zavrnjen; do naslednjega
`Start-Process`, ki odpre glavno okno, skript ne pride. Nimamo potrditve uspešnega
zagona TLS procesa ali izvajanja `QSslSocket::supportsSsl()`. To je napaka pri
poskusu zagona, ne potrjena napaka TLS podpore. Odsotnost same vrstice `AI TLS`
v dnevniku ni samostojen dokaz: C++ jo lahko izpiše neposredno v konzolo.
Sam dnevnik ne določi DLL-ja ali notranjega razloga DeepGuard in ne potrdi
neškodljivosti EXE. Uporabnik revizije in orodij stare delujoče gradnje ne pozna.

## Ugotovitve iz kode in zgodovine

Primerjalna osnova je prejšnja koda repozitorija `cdd747d530c64035268c663580b80430afa77e15`
in nova izvedba zagona `a0d13c447825ed32dcf08b3a312b6f9aad0e3f0d`. To še ni primerjava
z uporabnikovim dejanskim starim EXE: njegova revizija, orodja in datoteke niso znani.

| Del | Prejšnja izvedba v repozitoriju | Nova izvedba |
| --- | --- | --- |
| Qt / prevajalnik v CI | `install-qt-action@v4`, Qt 5.15.2, MinGW 8.1 x64 | `aqtinstall==3.3.0`, iste zahtevane različice; isti bootstrap kot lokalno |
| Gradnja | `lrelease`, `qmake AI.pro`, `mingw32-make -j4` | Isti qmake projekt in optimizacije; ob spremembi vsebine še `make clean` |
| Qt / MinGW DLL-ji | Vsi `*.dll` iz obeh `bin` map in vsi Qt vtičniki | Ista široka izbira; ne trdimo, da so vsi potrebni ali da so bajti identični |
| TLS | Stari build skript jih ni priložil; pripravo je prepustil zaganjalniku zunaj tega skripta | Iz obstoječega lokalnega predpomnilnika vzame x64 OpenSSL 1.1 par; v čistem CI prevede OpenSSL 1.1.1w z MinGW iz preverjenega uradnega arhiva |
| CRT | Ni izrecnega kopiranja v starem build skriptu | Izrecno priloži x64 `vcruntime140.dll` in `vcruntime140_1.dll` iz orodij; čisti bootstrap ju pridobi iz uradnega Python embedded arhiva |
| Označevanje | Različica in datum gradnje | Dodan AI 0.12 in kratek Git commit v naslovu in O programu |
| Zagon | Starega uporabnikovega zaganjalnika nimamo | CMD → Windows PowerShell → `simulide.exe -ai-check-tls` → ob uspehu drugi proces `simulide.exe` z glavnim oknom |
| Podpisovanje | V pregledanem workflowu ni koraka podpisovanja | Prav tako ga ni; dejansko stanje posameznih EXE/DLL-jev zapiše inventar |

Čisti novi bootstrap prevede OpenSSL z `Configure mingw64 shared no-asm no-tests`
in `make -j4` (`scripts/build-tls.sh`); zastavic stare uporabnikove TLS gradnje
ne poznamo. MinGW DLL-ja zato nista nujno enaka prej priloženima knjižnicama,
tudi če je izpisana enaka različica OpenSSL. To preveri hash primerjava.

Izvorna datoteka `src/main.cpp`, tudi veja `-ai-check-tls`, se med tema revizijama
**ni spremenila**. C++ spremembe prejšnjega PR-ja so dodale oznako različice/commita
v naslov in O programu; niso odstranile TLS pregleda ali spremenile zaščite.
Ta dopolnitev prav tako ne spreminja C++, izbranih DLL-jev, optimizacij ali načina
nalaganja programa zaradi zaznave. Doda sledljivost, pasivni pregled in dnevniške oznake.

V obeh primerjanih revizijah je tudi nespremenjen AngelScript JIT:
`src/angel/JIT/virtual_asm_windows.cpp` vsebuje `VirtualAlloc` z
`PAGE_EXECUTE_READWRITE` in poznejši `VirtualProtect`; `ScriptBase` ga poveže
na x64 platformi. Prisotnost kode za izvršljiv pomnilnik je podatek za analitika,
ne dokaz, da je bila ta pot ob blokadi izvedena ali da je povzročila zaznavo.

CI za revizijo `a0d13c4` je uspešno prevedel in odprl Windows program v
[zagonu 38127849133](https://github.com/Rokachello/SimulIDE-AI-Classroom/actions/runs/38127849133).
To dokazuje delovanje v CI, **ne** uspešnega pregleda z WithSecure ali varnosti paketa.
Prenos tega prejšnjega artefakta v trenutno razvojno okolje je zavrnil omrežni proxy;
njegovih dejanskih hashov in podpisov zato tukaj še nismo pregledali. Stare uporabnikove
DLL-je je treba pregledati na njegovem računalniku oziroma primerjati njegove inventarje.

## Kaj naredi zagonski TLS pregled

1. `ZAZENI.cmd` požene PowerShell skript, ki izbere program iz te kopije projekta
   oziroma `bin/simulide.exe` iz razširjenega prenosnega paketa.
2. Pred odpiranjem glavnega okna zažene isti EXE z `-ai-check-tls`.
3. C++ najprej ustvari `QApplication`: tudi ta kratki proces potrebuje Qt GUI in
   vtičnik `qwindows.dll`. Nato `QSslSocket::supportsSsl()` naloži/razreši OpenSSL
   in izpiše Qt-jevo pričakovano ter dejansko različico knjižnice. Ne vzpostavi
   HTTPS povezave ali povezave z učilniškim strežnikom; ne preveri certifikata
   strežnika. `OK` pomeni razpoložljivost lokalnega TLS izvajanja.
4. Izhodna koda je 0 ob uspehu, 2 ob manjkajoči/nezdružljivi TLS podpori. Veja
   se konča pred nastavitvami programa, ustvarjanjem `MainWindow` in `app.exec()`.
5. Pregled se izvede po gradnji, ob hitrem zagonu brez gradnje in ob vsakem zagonu
   prevedenega paketa. Ob neuspehu se glavno okno ne zažene; oznaka pripravljenosti
   lokalne gradnje se odstrani. `-BuildOnly` prav tako opravi TLS pregled.

`setup.log` sedaj loči `TLS pregled: zacenjam ...`,
`TLS pregled: koncano, izhodna koda 0.` in `Odpiram SimulIDE iz: ...`.
Izpis `AI TLS: ...` se shrani, kadar pride v preusmerjeni stderr. Nespremenjeni
C++ ob uspešnem `AttachConsole` preusmeri stdout/stderr na `CONOUT$`, zato se
ta vrstica lahko pokaže neposredno v konzoli in je PowerShell ne zajame v dnevnik.
Novi začetni/končni oznaki piše PowerShell in nista odvisni od tega preusmerjanja.
Če ni zapisa o koncu, potrebujemo hkrati podatek DeepGuard o blokirani datoteki;
manjkajoča vrstica sama ne določi vzroka. Inventar pokaže prisotne datoteke in
njihov izvor, ne dokazuje celotnega dejanskega nabora DLL-jev, naloženih v procesu.

## Domneve, ki zahtevajo pregled

- Nova, nepodpisana CI izvršljiva datoteka lahko nima enakega ugleda kot stara
  lokalna gradnja; odločitev DeepGuard je lahko povezana z ugledom ali vedenjem.
- CI lahko vsebuje drugačne OpenSSL DLL-je od stare namestitve, čeprav sta ime
  in ABI enaka. Različice in hash primerjava to lahko potrdijo ali ovržejo.
- Argument `-ai-check-tls`, izvor datoteke in dinamično nalaganje knjižnic so
  podatki za pregled. Prvi poskus zagona je zavrnjen; ni potrjeno, da sta bila
  TLS koda ali glavni program sploh izvedena, ali da je bil blokiran DLL.
- Analitik lahko preveri tudi obstoječi JIT in njegove pomnilniške operacije.
  Njegova koda se med primerjanima revizijama ni spremenila; brez dogodka ali
  analize vzorca te poti ni mogoče povezati z novo zaznavo.

Sam naziv zaznave ne pokaže, katera domneva drži, in ne izključi resnične napake ali
kompromitirane datoteke. Brez točnega vzorca, dogodka in pregleda WithSecure vzrok
ostaja odprt. Sprememba hashov, prevajalnika ali odstranjevanje TLS pregleda zgolj
zaradi obhajanja zaznave ni rešitev. SHA256 potrdi identiteto, ne neškodljivosti.

## Najpreprostejši lokalni preizkus

Prenesi artefakt **SimulIDE-AI-Source** iz Actions oziroma `SimulIDE-AI-Source.zip`
iz sledljive izdaje, razširi notranji ZIP v **novo zapisljivo mapo** in dvoklikni
**ZAZENI.cmd**. Pri prenosu iz Actions najprej razširi tudi ovoj artefakta.

ZIP vsebuje kodo, javne vire in zaganjalnik, brez CI programa in njegovih DLL-jev.
Celoten commit je v `PREBERI-IZVOR.txt`, SHA256 izvornih datotek pa v
`SOURCE-FILES-SHA256SUMS.txt`. Git ni potreben za gradnjo. Ker ZIP nima `.git`,
program pošteno izpiše Git `unknown`; identiteto prenosa preveri v priloženem
poročilu in z zunanjo kontrolno vsoto ZIP-a.

Orodja se najprej poiščejo v `%LOCALAPPDATA%\SimulIDE-AI-V0.2\tools`; popolna
obstoječa Qt 5.15.2 / MinGW 8.1 / x64 TLS in CRT namestitev se ponovno uporabi
brez prenosa. Izbor orodij je zapisan v `setup.log`. Če del manjka, običajni
bootstrap prenese samo potrebne dele in lahko pripravi lokalni OpenSSL.
Ne kopiraj starega EXE, DLL-jev, nastavitev ali baze v projekt. Strežnika za
preverjanje gradnje in odpiranja okna ni treba zagnati. Lokalni prevod ni
zagotovilo, da ga zaščita ne bo blokirala.

Za primerjavo dvoklikni **PREGLED-DLL.cmd** v izvornem projektu. Vpiši novo mapo
s `simulide.exe` (pri paketu `bin`, pri lokalni gradnji
`build_AI\executables\SimulIDE_2.0.0-`) in po želji staro delujočo mapo.
V `dist\withsecure-review` nastanejo `current-runtime.json`, `previous-runtime.json`
in `runtime-comparison.csv`: vsaka EXE/DLL ima hash, velikost, različico, arhitekturo
in stanje Authenticode. `identical` pomeni identične bajte; `changed` pomeni
spremembo bajtov, ne sodbe o varnosti. Pregledani EXE/DLL-ji se ne izvajajo;
preverjanje certifikatov Windows lahko uporabi sistemsko preverjanje zaupanja.
Če je datoteka v karanteni ali nedostopna, se pregled ustavi brez posega v zaščito.

## Sledljiva izdaja in pregled WithSecure

Za novo izdajo uporabi pregledan commit in nov tag `v*`; obstoječih tagov in
objavljenih paketov ne zamenjuj. Workflow najprej opravi teste, nato pripravi
**osnutek GitHub Release** za pregled, ne samodejne javne objave. Vključuje:

- `SimulIDE-AI-Windows.zip`, z notranjim `build-info.json` in `FILES-SHA256SUMS.txt`;
- pripadajoči `SimulIDE-AI-Source.zip` z vsemi javnimi viri in licencami;
- zunanji `build-info.json`: celoten source commit, povezavo do izvorne kode,
  workflow/run, čas, Qt/GCC različici ter hash, podpis in izvor vsake EXE/DLL;
- `SHA256SUMS.txt` za oba ZIP-a in poročilo. Vsote se ustvarijo po pakiranju.

Actions so pripete na celotne Git SHA. Prenosi Python/OpenSSL/MSYS2 imajo pripete
kontrolne vsote, Qt arhivi preverjanje SHA256 in MSYS2 paketi preverjanje podpisov.
Obstoječa uporabnikova orodja niso ponovno overjena z izvirnimi arhivi samo zato,
ker se ponovno uporabijo; poročilo zapiše dejanske datoteke. `unmatched-existing-file`
označi DLL brez hash ujemanja s kopiranim SDK-jem. Pred objavo tak izvor razišči.
MSYS2 paketi in PyPI odvisnosti trenutno niso vsi pripeti na nespremenljive izdaje;
sledljivost te izdaje zato ni trditev o popolnoma reproducibilni gradnji. Tudi datum
gradnje in Git oznaka vplivata na bajte EXE. Qt 5.15.2 zahteva stari OpenSSL 1.1;
prehod na vzdrževano Qt/TLS različico načrtuj kot ločeno združljivostno spremembo.

Za pregled prek [uradne podpore WithSecure](https://www.withsecure.com/en/support)
pripravi [predlogo prijave](WITHSECURE-REVIEW-TEMPLATE.md), točen **blokirani vzorec**
in njegov hash, številko izdaje/run/commita, izvorni paket, inventarja nove in
stare gradnje, primerjavo ter dogodek zaznave. Dnevnik ročno preglej in odstrani
osebne poti ali zasebne naslove. Ne prilagaj API ključa, strežniške baze, pogovorov
ali učiteljevih gradiv. Če je vzorec v karanteni, uporabi uradni postopek izdelka
za oddajo v analizo oziroma pomoč skrbnika; ne izvleci ga za zagon in ne ustvarjaj
izjeme. Oddaja še ni izvedena. Pred distribucijo zabeleži odgovor/sklic WithSecure
in preveri ravno pregledane hashe. Po spremembi paketa pregled ne velja samodejno.

## Digitalno podpisovanje

Predlagamo Authenticode podpis **lastnega `simulide.exe`** in po potrebi lastnih
PowerShell skript z zaupanja vrednim certifikatom za podpisovanje kode. Podpisi
drugih izdajateljev na knjižnicah ostanejo njihovi; DLL-jev ne prepisujemo samo
zaradi zaznave. Samopodpisani certifikat ne vzpostavi javnega zaupanja. Podpis
potrdi izdajatelja in integriteto, ne zagotovi odprave DeepGuard zaznave.

Zagotoviti moramo preverljivo identiteto izdajatelja (osebo/organizacijo glede na
ponudnika), certifikat za podpisovanje kode, varen dostop do zasebnega ključa
(običajno strojni žeton/HSM ali storitev podpisovanja), ustrezno pogodbo/stroške,
Windows SDK SignTool oziroma orodje ponudnika in RFC3161 časovni žig s SHA256.
Za CI potrebujemo podprto oddaljeno podpisovanje, omejeno identiteto/dostop in
zaščiteno vejo/tag ali release environment; PR-ji iz nezaupanja vrednih vej ne smejo
dobiti dostopa do ključa. Certifikata ali ključa ne vpišemo v repozitorij.

Vrstni red izdaje: pregled kode → gradnja/testi → podpis lastnih datotek s časovnim
žigom → preverjanje podpisov → ponovna izdelava inventarja/hashov → pakiranje →
zunanje kontrolne vsote → pregled WithSecure → pregled in objava osnutka.
Trenutni workflow certifikata nima in **še ne podpisuje**. Integracijo dodamo šele
po izbiri ponudnika in načina varnega dostopa. Glej tudi
[Microsoft SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool).
