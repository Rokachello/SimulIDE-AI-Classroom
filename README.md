# SimulIDE AI učilnica

SimulIDE with an optional teacher-controlled AI tutor for classroom electronics activities. The desktop app sends circuit/simulation context to the teacher's classroom server; the OpenAI key stays on that server.

## Start here
- Teacher setup and classroom use: [README_AI.md](README_AI.md)
- Current release test record and limitations: [VALIDATION.md](VALIDATION.md)
- Build and one-click launch scripts: `scripts/` and `server/`

## Windows: izvorna koda

Kloniraj repozitorij ali razširi **celoten izvorni ZIP** v zapisljivo mapo. Potrebuješ
64-bitni Windows 10/11 z vgrajenim Windows PowerShell 5.1. Ukazov PowerShell ni treba
vpisovati ročno.

- **Prvi zagon:** dvoklikni `ZAZENI.cmd` v korenu. Zaganjalnik uporabi obstoječa orodja
  v `%LOCALAPPDATA%\SimulIDE-AI-V0.2\tools`; manjkajoče Python, Qt 5.15.2, MinGW 8.1
  in TLS knjižnice prenese iz python.org, PyPI oziroma uradnega repozitorija Qt.
  Prenosi ohranijo preverjanje TLS in kontrolnih vsot. Nato prevede kodo iz te mape
  in odpre njen SimulIDE. Prvi zagon zahteva internet in lahko traja več minut.
- **Naslednji zagon:** znova dvoklikni `ZAZENI.cmd`. Nespremenjena koda se odpre hitro;
  sprememba vsebine izvornih datotek, virov ali gradilnih skript sproži gradnjo.
  Stara oznaka `ready-v012.txt` se ne uporablja. Naslov okna in **O programu** pokažeta
  različico AI in Git commit; lokalne spremembe imajo oznako `dirty`. Izvorni ZIP
  brez `.git` pokaže `unknown`.
- **Posodobitev Git klona:** zapri SimulIDE in dvoklikni `POSODOBI.cmd`. Potrebuješ
  Git for Windows in nastavljeno oddaljeno vejo. Skript ob lokalnih spremembah ali
  novih nesledenih datotekah ustavi posodobitev. Uporabi `git pull --ff-only` in po
  uspehu izvede gradnjo. Ne briše sprememb in ne menja veje. Izvorni ZIP posodobiš
  s prenosom nove celotne kopije.
- **Učiteljski strežnik:** dvoklikni `ZAZENI-STREZNIK.cmd` v korenu. Strežnik se naloži
  iz `server/` tega repozitorija in ponovno uporabi obstoječo podatkovno mapo
  `%LOCALAPPDATA%\SimulIDE-AI-V0.2\classroom-data`. Če je nastavljen `SIMULIDE_DATA`,
  ohrani to izbiro; prepozna tudi obstoječo bazo v `server/data/`. Ob več bazah se
  ustavi, da ne izbere napačne. Računi, pogovori, gradiva in RAG nastavitve ostanejo
  v isti mapi. Nov učiteljski račun zahteva le, če učitelja še ni. API ključ vnesi
  v strežniškem oknu; ostane v pomnilniku strežnika. Na študentski računalnik ga ne
  prenašaj. Strežniško okno pusti odprto.

Ob napaki okno ostane odprto. Podrobnosti priprave in gradnje so v `setup.log` v
korenu projekta; vnos API ključa in vsebina pogovorov se v ta dnevnik ne zapisujeta.
Če javnih virov ne najdeš, razširi celoten projekt; ne kopiraj jih iz stare namestitve.
`resources/data/` in `build_XX/SimulIDE_Build.pro` sta vključena iz upstream revizije
`fc5da465bb15e80b6307f0c9564f5241567f7d86`.

## Windows: že prevedeni študentski paket

Windows GitHub Actions izdela **SimulIDE-AI-Windows.zip**. Razširi celoten paket in
dvoklikni njegov `ZAZENI.cmd`. Paket vsebuje prevedeni program, Qt/MinGW/TLS knjižnice,
vtičnike in licenčna obvestila; orodij za prevajanje ne namešča. V prijavi uporabi
naslov strežnika in račun, ki ju določi učitelj.

To je drugače kot izvorni ZIP: študentski paket nima strežnika, API ključa, učiteljevih
nastavitev ali baze in se posodobi s prenosom novega prevedenega paketa. Za razvoj ali
učiteljski strežnik uporabi izvorni repozitorij. Izvorna koda ustrezne izdaje je
navedena v paketovem `PREBERI.txt`.

## Razvojno preverjanje

Strežniški testi: `python -m unittest discover -s server -p 'test_*.py'` po namestitvi
`server/requirements.txt`. Testi ne potrebujejo živega OpenAI ključa.
Linux gradnja: `BUILD_JOBS=4 bash scripts/build-linux.sh CONFIG+=ai_test`.
Windows kontrolni testi: `powershell -NoProfile -File tests/windows/launcher-tests.ps1`.
Kaj je bilo dejansko preverjeno, je zapisano v [VALIDATION.md](VALIDATION.md).

The release ZIP includes one-click Windows setup. The server may also run on Ubuntu. Do not place student records, local databases, API keys, or teacher-uploaded private documents in this repository.

This project is based on SimulIDE. See the included GPL/AGPL license files and upstream notices before redistribution.
