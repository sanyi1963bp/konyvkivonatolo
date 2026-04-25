# KönyvtárAI — A projekt születése

## Honnan indultunk

A kiindulási helyzet három különálló "világ" volt, amelyek nem tudtak egymásról.

**Fizikai könyvek a gépen** — egy nagy könyvtárstruktúra rengeteg fájllal, különböző forrásokból összegyűjtve az évek során. EPUB, PDF, MOBI, AZW3, FB2 formátumokban, nagyjából 100 ezer fájl körüli mennyiség. A fájlnevekben semmiféle egységes logika nem volt — hol "Szerző - Cím", hol pontokkal elválasztott torrent-stílus, hol z-library formátum, hol kisbetűs-aláhúzásos változat.

**Egy SQLite adatbázis** — amelyet egy nagy magyar könyv-katalógusból gyűjtöttek össze. Ez az adatbázis **66 876 könyvet** tartalmazott, gazdagon: cím, szerző, kiadó, kiadási év, ISBN, leírás, cimkék, sorozat, borítókép-URL. Rengeteg értékes metaadat, de fogalma sem volt arról, hogy ezekből a könyvekből melyik van ténylegesen letöltve a gépen.

**Moly.hu** — a legnagyobb magyar könyvközösségi oldal, tele értékelésekkel, ajánlókkal, sorozatinformációkkal. Értékes kiegészítő forrás, de egyelőre teljesen kiaknázatlan.

A cél: összekapcsolni ezt a három világot, és egy egységes, intelligens könyvtárkezelőt építeni belőlük.

---

## 1. lépés — Az adatbázis feltérképezése

Mielőtt bármibe belekezdtünk, meg kellett érteni mit tartalmaz az adatbázis. Megírtuk az első szkriptet (`fazis1_meta_elemzo.py`), amely egyszer lefut indításkor, és teljes statisztikát készít:

- Összes könyv: **66 876**
- Egyedi szerzők száma
- Top 50 szerző, top 30 cimke, top 30 kiadó, kiadási évek eloszlása
- Formátumok megoszlása
- Adatgazdagság mezőnként (hány százaléknál van valódi adat)
- Sorozatok listája

Az eredményt egy `meta.json` fájlba menti, amelyet a főprogram minden indításkor beolvas — így azonnal "tudja" milyen adatok vannak a könyvtárban, anélkül hogy minden alkalommal végigszámlálná az egészet.

---

## 2. lépés — A fájlfelismerő motor

Ez volt a projekt legösszetettebb és legintelligensebb darabja (`fazis1_fajlfelismero.py`). A feladat: végigmenni az összes fizikai fájlon, és megpróbálni minden egyes fájlt párosítani egy adatbázis-bejegyzéssel.

**A kihívás:** a 66 ezer könyv szerzőneveit és cím-változatait nem lehet fájlonként egyenként végigpróbálgatni — az 100 ezres fájlállománynál órákat vett volna igénybe.

**A megoldás:** az egész adatbázist egyszer betöltjük memóriába, és két gyors keresési indexet építünk belőle:
- Minden szerző minden szavához → melyik szerzőkhöz tartozik (O(1) szótár-keresés)
- Szerző → könyveinek listája

Ezekkel az indexekkel egyetlen fájl azonosítása ezredmásodpercek alatt megtörténik, így a teljes 100 ezres állomány 5-12 perc alatt feldolgozható.

**A négy fájlnév-minta** amelyet felismertünk, miután megnéztük a valódi fájlneveket:

| Minta | Példa |
|-------|-------|
| Alap | `Rejtő Jenő - Piszkos Fred a kapitány.epub` |
| Torrent | `Rejto.Jeno.Piszkos.Fred.a.kapitany.HUN.EPUB.eBook-Group.epub` |
| Z-Library | `Piszkos Fred a kapitány (Rejtő Jenő) (z-lib.org).epub` |
| Kisbetűs | `rejto_jeno_piszkos_fred_a_kapitany.epub` |

**Az egyezési szintek** amelyeket a rendszer megkülönböztet:
- **pontos**: szerző + cím is megtalálva, magas hasonlósági pontszámmal
- **fuzzy**: közelítő szöveghasonlósággal megtalálva (rapidfuzz könyvtár)
- **szerzo_ismert**: a szerzőt azonosította, de a konkrét könyvet nem
- **ismeretlen**: sem szerző, sem cím nem volt azonosítható

Az eredmény egy új tábla az adatbázisban (`fizikai_fajlok`), ahol minden fizikai fájlhoz tároljuk az útvonalat, formátumot, az egyezési szintet, a talált szerző és cím nevét, és ha sikerült, a kapcsolódó könyv azonosítóját.

**Eredmény az első futás után:**
- Pontos + fuzzy egyezés: ~21%
- Csak szerző ismert: ~15% (10 276 fájl)
- Ismeretlen: ~64% — de ez nem meglepő, mert a könyvtár vegyes: van benne digitalizált régi anyag, folyóirat-oldalak, technikai dokumentumok, nem csak szépirodalom

---

## 3. lépés — Moly.hu adatgyűjtő

A "csak szerző ismert" kategória 10 276 fájlból áll — tudjuk ki írta, de nem tudjuk melyik könyve. Ezekhez a moly.hu adatbázisából próbálunk cím-információt szerezni (`fazis2_moly_scraper.py`).

**Miért scraping és nem API?** A moly.hu API-ja jelenleg nem elérhető a nyilvánosság számára.

**Mit csinál a scraper:**
1. Bejelentkezik a moly.hu-ra (CSRF token + POST)
2. Minden egyedi szerzőre rákeres
3. Kinyeri a találatokból: könyv azonosító, URL, szerző, cím, értékelés, sorozat
4. Elmenti az adatbázisba
5. Naplózza melyik szerzőt már lekérte — így folytatható ha megszakítják

**Tempó:** szerzőnként 1-3 lekérés, 1.2-2.8 másodperc várakozással közöttük, hogy ne terheljük az oldalt. 2752 szerzőnél ez néhány óra — de a program a háttérben fut, és folytatható bármikor.

---

## 4. lépés — A főprogram

A három adatforrást egységes, szép felületen mutatja meg (`konyvtar_gui.py`). PyQt6-alapú natív Windows alkalmazás, sötét témával.

**Bal oldalsáv:** keresés, státusz szűrő, formátum, cimkék, szerzők, jelmagyarázat

**Középső rész:** könyvkártyák rácsa borítóképekkel, lapozóval (48 könyv/oldal), tömeges kijelöléssel. Minden kártya bal szélén egy színes sáv mutatja az egyezési szintet — zöldtől pirosig.

**Jobb oldal felső:** könyv részletei — cím, szerző, kiadó, sorozat, moly.hu értékelés, fájl státusz, leírás

**Jobb oldal közép:** AI panel — összefoglaló, vélemény, hasonló könyvek, saját kérdés, modellváltó. Helyi Ollama modellekkel működik, nincs szükség internet-kapcsolatra.

**Jobb oldal alsó:** telefon fájlkezelő — meghajtó választó, mappastruktúra böngésző, új/átnevez/töröl műveletek, könyvek másolása folyamatjelzővel.

---

## Az eredmény

Egy magánember, egy gép, nyílt eszközök — és egy könyvtár amely a legnagyobb hazai portálokkal vetekszik. Borítóképes ráccsal, intelligens kereséssel, AI asszisztenssel és telefon-szinkronizálással.

Mindez teljesen offline, teljesen ingyenes, és teljesen a sajátod.
