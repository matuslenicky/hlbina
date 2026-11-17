# HLBINA

Koncept webu pre pramenitú vodu zo studne v kopcoch nad Myjavou, plnenú do sklenených fliaš. Značka HLBINA
je vymyslená (pracovný názov), web je ukážka návrhu a formulár nič neodosiela.

Všetky obrazy sú vyrenderované v Blenderi 5.2 skriptami v `blender/`:

- `shots.py` – fotky fliaš (Cycles): úvod, detail vypieskovaného pásu, dve veľkosti, podvečer, každá na šírku
  aj na výšku; fľaše stoja na pieskovcovom kameni nad dolinou,
- `land.py` – krajina Myjavskej pahorkatiny: terén s dolinou a vrstvami hrebeňov (na obzore Biele Karpaty),
  lesíky, osamelé stromy, kopanice so sadmi, opar v doline (priamo v materiáloch, funguje aj v lome skla),
  fyzikálna obloha so slnkom, kameň a tráva,
- `anims.py` + `render_well.py` – zostup kamerou do studne, 72 snímok prehrávaných podľa scrollu;
  `well_top.py` dopĺňa vrch studne: lúku s trsmi trávy, ďatelinou a sedmokráskami a veniec
  z pieskovcových kvádrov (svetlo otvoru svieti len do šachty),
- `lib.py` – geometria fľaše (ťažké dno, dlhé mäkké plecia), sklo, voda, dubový uzáver, svetlá;
  `make_labels.py` – vypieskovaný pás kopcov s osamelým stromom a zvislý nápis HLBINA.

Web je jeden súbor `index.html` bez knižníc. Snímky studne kreslí na `<canvas>` s prelínaním susedných
snímok, vlnky na hladine počíta WebGL nad posledným záberom zo studne.

## Zostavenie

```
cd blender
python make_labels.py                                # masky pieskovania do tex/
powershell -File render_stills.ps1 -Samples 80       # fotky do out/stills (~1,5 h na CPU)
blender -b --factory-startup -P render_well.py -- out/well 960 28 72
cd ..
python tools/prep.py                                 # WebP do assets/
```

Všetko naraz (dorenderuje len chýbajúce PNG, Blender s nižšou prioritou, čaká na 6 GB voľnej RAM, nakoniec spustí `prep.py`;
priebeh v `blender/out/rest.log`):

```
powershell -ExecutionPolicy Bypass -File blender\render_rest.ps1 -Samples 80
```

Písma Italiana a Jost sú z Google Fonts (SIL Open Font License).
