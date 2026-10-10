# SimulIDE AI – učilnica V0.12

## Nadgradnja na računalniku učitelja

1. Zapri prejšnji SimulIDE in okno strežnika.
2. Razširi celoten ZIP. Odpri novo mapo `SimulIDE-AI-V0.12`.
3. Zaženi `ZAZENI-STREZNIK.cmd`. Izberi običajno uporabo (ne demo) in vnesi OpenAI API ključ. Če dokumentacija še ni pripravljena, zaganjalnik ponudi pripravo RAG; potrdi z Enter. Že pripravljena shramba se ponovno uporabi.
4. Pusti strežniško okno odprto. V brskalniku odpri `http://127.0.0.1:8765` in se prijavi z učiteljskim računom.
5. Zaženi `ZAZENI.cmd`. Prva nadgradnja prevede spremembe z že prenesenimi orodji. V naslovu asistenta mora pisati V0.12.

Računi, pogovori, gradiva, kvizi in povezava z vektorsko shrambo ostanejo v isti mapi `%LOCALAPPDATA%/SimulIDE-AI-V0.2/classroom-data`. Ne uporabljaj bližnjice, ki še kaže na stari paket. `http://127.0.0.1:8765/health` mora pokazati `version: 12`, `release: "0.12"` in `rag_version: 1`.

Ubuntu: uporabi mapo `SimulIDE/server`, pripravi okolje z `bash setup-ubuntu.sh`, nato `bash zazen-server.sh`. Pri obstoječem strežniku ohrani isto nastavitev `SIMULIDE_DATA`. Skripti uporabljata obstoječi API ključ iz okolja ali vprašata po njem. Ključ ni del študentskega paketa.

## Učitelj

Na seznamu ur izberi **Odpri pregled ure**. Na enem mestu so priprava, dejavnost študentov, oddaje, kviz, pomoč in povezava do povzetka.

- Novo uro lahko pripraviš zaprto. **Odpri uro** omogoči vprašanja in oddaje. **Zaključi uro** ustavi nova vprašanja in oddaje nalog; že začeti kvizi se lahko dokončajo.
- **Kopiraj za novo izvedbo** prenese naslov, cilje, navodila, dodatni prompt, nastavitve in gradiva konkretne ure. Kviz s priloženim vezjem se prenese kot osnutek. Pogovori, rezultati, oddaje in opozorila se ne kopirajo. Preveri datum ter objavi kviz, ko je pripravljen.
- **Uredi pripravo** odpre pravi obrazec. Sprememba navodil velja za naslednje vprašanje; stari pogovori ohranijo prvotna navodila.
- **Predogled navodil za študenta** pokaže cilje in nalogo. Predogled kviza je na strani Priprava kviza.
- Dejavnost prikazuje študente z vprašanjem, prošnjo za pomoč, oddajo ali začetim kvizom. Ne pomeni trenutne prisotnosti ali prijave. Pregled se osvežuje vsakih 20 sekund; ob napaki je označen kot lahko zastarel.
- Število vprašanj odpre pogovor tega študenta. Oddano vezje lahko preneseš neposredno. Besedilne odgovore kviza oceniš v **Oddaje in rezultati**.
- **Povzetek ure** se ustvari na tvojo zahtevo. AI ugotovitve preveri ob dokazih. **Pomoč** združuje neposredne prošnje in predloge iz pogovora.

Učiteljevi obrazci opozarjajo pred zapustitvijo neshranjenih sprememb. To ni samodejno shranjevanje učiteljeve priprave. Vedno uporabi gumb za shranjevanje.

## Študent v SimulIDE

Prijavi se in izberi uro. Gumb **Naloga** ponovno pokaže cilje in navodila, brez iskanja po pogovoru. Zaprt asistent se odpre z gumbom AI asistent ali Ctrl+Shift+A.

Neodposlano vprašanje in osnutki odgovorov kviza se shranjujejo lokalno, ločeno po strežniku, uporabniku in uri oziroma poskusu. Po ponovni prijavi na istem računalniku in v istem uporabniškem profilu se obnovijo. Po uspešni oddaji se osnutek kviza odstrani. Osnutki se ne prenašajo med računalniki in niso oddaja učitelju. Vezje še vedno shrani s Ctrl+S.

**Oddaj nalogo** pošlje trenutno vezje, posnetek in komentar. Potrdilo vsebuje številko oddaje. **Oddaj novo različico** ustvari dodatno oddajo; prejšnja ostane shranjena.

Med kvizom pomoč asistenta in zgodovina ostaneta zaklenjeni. Ponovni zagon zaklepa ne odstrani. Učitelja lahko še vedno zaprosiš za pomoč. Po potrjeni oddaji se pomoč odklene; besedilne razlage čakajo na učiteljevo oceno.

## Dokumentacija in RAG

V paketu je strežniška priprava OpenAI vector store z 191 dokumenti. V **Gradiva** preveri stanje. Če priprava ni končana, jo ponovi ob zagonu ali z `PRIPRAVI-RAG.cmd`. Dokončani prenosi se preskočijo. Učiteljeva dodatna gradiva se še vedno iščejo lokalno po izbrani uri. API ključ ostane v pomnilniku strežniškega procesa.

Shramba vsebuje javno dokumentacijo; pogovori in posnetki vezij se vanjo ne nalagajo. Iskalna poizvedba gre OpenAI; izbrani odlomki skupaj s pogovorom in vezjem služijo odgovoru modela. Ob nedosegljivem vektorskem iskanju sistem uporabi lokalne vire in to zabeleži ob pogovoru.

## Deljenje in trenutne meje

Po prvi gradnji uporabi **USTVARI-STUDENTSKI-PAKET.cmd** in vnesi javni naslov strežnika. Za dostop od drugod potrebuješ dosegljiv HTTPS naslov; localhost velja samo za isti računalnik. Objavljanje strežnika na internet v tej izdaji ni samodejno urejeno.

Novi krmilnik scaffoldinga in sistematično poročanje o zmotnih predstavah še nista vključena. Profil znanja ostaja omejen na doslej zajete učne dokaze. Skupina je oznaka ure; vsi študentski računi tega strežnika lahko izberejo vse ure, vsak pa vidi svoje pogovore.
