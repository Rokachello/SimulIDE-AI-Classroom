# LDR in Thermistor: svetlobno in temperaturno odvisni upori
Preverjeno: src/components/passive/resist_sensors/ldr.cpp, thermistor.cpp ter pripadajoče osnovne komponente.
LDR je upor, odvisen od osvetljenosti, ne napetostni vir. Current Value pri LDR pomeni osvetljenost v Lux; Minimum Value, Maximum Value in Dial Step določajo nastavitve vrtljivega gumba. Lastnost Gamma določa karakteristiko. Ne razlagaj Lux kot upornost v Ω.
Thermistor je temperaturno odvisni upor. Lastnosti B in R25 opisujeta model; R25 je upornost pri 25 °C. Za dejanske trenutne nastavitve temperature uporabi properties v posnetku vezja, ne ugibaj imen podedovanih polj.
Pri senzorskem delilniku najprej preveri, ali mora izhodna napetost z osvetljenostjo ali temperaturo naraščati ali padati. Učinek je odvisen od tega, ali je senzor zgoraj ali spodaj in od njegove karakteristike. Ne sklepaj o smeri samo iz besede termistor.
