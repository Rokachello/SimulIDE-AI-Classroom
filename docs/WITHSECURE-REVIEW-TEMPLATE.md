# Podatki za pregled WithSecure

Status: pripravljena predloga; vzorec še ni oddan in vzrok ni potrjen.

- Zaznava: `Suspicious:W32/Malware!DeepGuard.ag` (poročilo uporabnika).
- Izdelek WithSecure, njegova različica, stanje posodobitev in Windows različica: **dopolni**.
- Čas dogodka s časovnim pasom: **dopolni**.
- Blokirana datoteka/proces in dejanje: **dopolni iz dogodka**.
- Korak: razširjanje ZIP / priprava orodij / `-ai-check-tls` / odpiranje glavnega okna: **dopolni**.
- Točen hash blokiranega vzorca SHA256 in stanje Authenticode: **dopolni iz pasivnega inventarja**.
- ZIP SHA256, ime izdaje, source commit in povezava do CI: **priloži SHA256SUMS.txt in build-info.json**.
- Izvorna koda: `https://github.com/Rokachello/SimulIDE-AI-Classroom` in nespremenljiva povezava do commita v poročilu.
- Stara delujoča gradnja: source commit, Qt/MinGW/TLS, hashi in podpisi: **dopolni, če so na voljo; sicer označi neznano**.
- Rezultat lokalne gradnje iste kode z obstoječimi orodji: **dopolni brez posega v zaščito**.
- Sklic podpore WithSecure in ugotovitev analize: **dopolni po prejemu**.

Pričakovano delovanje: izvorni zaganjalnik pripravi orodja in lokalno prevede
SimulIDE. Prenosni paket že vsebuje program. Pred glavnim oknom isti EXE izvede
kratek lokalni `QSslSocket::supportsSsl()` pregled prek `-ai-check-tls`, izpiše
različici TLS ter se konča; šele nato se zažene glavno okno. Program za učilnico
pozneje komunicira z izbranim učiteljevim strežnikom; API ključ je na strežniku.

Priloge za pregled: točen blokirani vzorec po uradnem postopku WithSecure,
`build-info.json`, `SHA256SUMS.txt`, `current-runtime.json`, po možnosti
`previous-runtime.json` in `runtime-comparison.csv`, javna izvorna koda, dogodek
zaznave ter redigirane zadnje vrstice `setup.log` okoli TLS pregleda.
Ne dodaj strežniških podatkov, gesel, ključev ali učiteljevih gradiv.

Vprašanje za analitika: katera datoteka in vedenje sta povzročila zaznavo ter ali
gre za dejansko škodljivo vsebino ali napačno klasifikacijo pregledanega hasha?
Ne zahtevamo obhoda zaščite; želimo klasifikacijo točnega sledljivega vzorca.
