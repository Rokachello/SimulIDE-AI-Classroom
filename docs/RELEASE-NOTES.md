SimulIDE AI za Windows: sledljiva izdaja za pregled.

- `SimulIDE-AI-Windows.zip`: že preveden študentski paket; razširi in dvoklikni `ZAZENI.cmd`.
- `SimulIDE-AI-Source.zip`: javna izvorna koda; razširi in dvoklikni `ZAZENI.cmd` za lokalni prevod z obstoječimi orodji.
- `build-info.json`: točen source commit, workflow, orodja, SHA256 in podpisi posameznih EXE/DLL-jev.
- `SHA256SUMS.txt`: kontrolne vsote vseh zgornjih prenosov.

Izvorni paket vsebuje tudi `ZAZENI-STREZNIK.cmd` za učitelja; zasebni strežniški
podatki in API ključ niso vključeni. Studentov prevedeni paket strežnika ne vsebuje.
Licence in pripadajoča izvorna koda so priložene. Pred objavo preveri licenčne obveznosti.

Ta osnutek sam po sebi ne potrjuje pregleda WithSecure in javnega podpisovanja.
Pred objavo skrbnik zabeleži rezultate za točne hashe v opisu izdaje. Če DeepGuard
blokira zagon, zaščite ne izklapljaj in ne dodajaj izjem; uporabi uradni postopek
za pregled vzorca. Navodila in predloga so v izvorni kodi: `docs/WINDOWS-DEEPGUARD.md`.
