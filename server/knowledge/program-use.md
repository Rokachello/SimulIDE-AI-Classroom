# SimulIDE upravljanje: Properties, Start Simulation, Pause Simulation, Save Circuit
Preverjeno v src/components/component.cpp ter src/gui/circuitwidget/circuitwidget.cpp.
Lastnosti elementa odpreš z dvoklikom z levim gumbom na element ali prek njegovega kontekstnega menija Properties. Uporabi dejansko ime lastnosti iz kataloga ali trenutnega posnetka; ne izmišljaj polj. Katalog prikazuje neposredno deklarirane lastnosti, ne vseh podedovanih. Za trenutno vrednost ima prednost posnetek vezja.
Start Simulation na orodni vrstici zažene simulacijo; med tekom se ukaz spremeni v Stop Simulation. Pause Simulation začasno ustavi simulacijo. Vklop izhoda vira in zagon simulacije sta ločeni dejanji.
Save Circuit shrani vezje (Ctrl+S); Save Circuit As izbere novo ime (Ctrl+Shift+S). Nova vezja se shranjujejo s končnico .sim2. Open Circuit odpre vezje, Zoom to fit prilagodi pogled vsem komponentam.
AI asistent ne spreminja vezja. Pošlji + zajemi vezje zajame novo stanje ob vprašanju. Osveži pogovor obnovi zgodovino ure. Prijava / ura omogoča izbiro ure. Učiteljev API ključ je samo na strežniku; študent uporabi svoj račun.
