# Bio-Dashboard v2 -- Leandro Edition

Pharmakokinetisches Echtzeit-Dashboard mit allometrischer Skalierung, Drei-Stufen-Kaskadenmodell fuer Lisdexamfetamin, Drug-Drug-Interaction-Warnungen, HRV-basierter autonomer Ueberwachung, und Migraene-Tracking nach IHS-Kriterien.

**Benutzer-Phänotyp:** 19-jaehriger Mann, 192 cm, 96 kg, chronisches Fastenprotokoll (kein Fruehstueck/Abendessen), Nichtraucher.

---

## Architektur-Uebersicht

```
┌─────────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│   Streamlit UI      │────>│   FastAPI API     │────>│   SQLite (WAL)    │
│   Port 8501         │<────│   Port 8000       │<────│   /data/bio.db    │
│   (bio.*.tech)      │     │   (bioapi.*.tech) │     │                   │
└─────────────────────┘     └────────┬─────────┘     └───────────────────┘
                                     │
                            ┌────────▼─────────┐
                            │   Home Assistant  │
                            │   (Nabu Casa)     │
                            │   Pixel 9 Pro XL  │
                            │   HealthSync      │
                            └──────────────────┘
```

Beide Prozesse laufen im selben Docker-Container (`start.sh` startet uvicorn + streamlit parallel). Caddy routet ueber Cloudflare Tunnel:

- **Dashboard**: `https://bio.thegrandprinterofmemesandunfinitetodosservanttonox.tech` → `bio-dashboard:8501`
- **API**: `https://bioapi.thegrandprinterofmemesandunfinitetodosservanttonox.tech` → `bio-dashboard:8000`

---

## Pharmakokinetische Modelle

### Allometrische Skalierung (96 kg)

Alle Konzentrationen werden gewichtsbasiert angepasst. Standard-Populationsparameter gelten fuer 70 kg -- bei 96 kg ist das Verteilungsvolumen proportional groesser:

```
Cmax_user = Cmax_ref × (70 / 96) = Cmax_ref × 0.729
CL_user  = CL_pop × (96 / 70)^0.75          (Clearance)
Vd_user  = Vd_pop × (96 / 70)^1.0            (Verteilungsvolumen)
```

Die Y-Achse der Konzentrationskurven zeigt absolute ng/ml-Werte, nicht normierte 0-1-Einheiten.

### Substanz-Modelle

#### Elvanse (Lisdexamfetamin → d-Amphetamin): Drei-Stufen-Kaskade

Kein einfaches Bateman-Modell. LDX durchlaeuft drei verknuepfte Kompartimente:

```
Darm ──[k_abs=2.0]──> LDX im Plasma ──[k_hyd=0.78]──> d-Amph im Plasma ──[k_e=0.088]──> eliminiert
       (PEPT1)                         (Erythrozyten)                       (t½ ≈ 10-12h)
```

Analytische Loesung fuer die d-Amphetamin-Menge A(t):

```
A(t) = G₀ · k_abs · k_hyd · Σᵢ [ e^(-rᵢ·t) / Πⱼ≠ᵢ(rⱼ - rᵢ) ]

wobei r = [k_abs, k_hyd, k_e] und G₀ = F · Dosis (F = 96.4%)
```

Der Peak wird numerisch bestimmt (0-30h bei 0.01h Aufloesung, gecacht).

#### Medikinet IR / retard / Koffein / Co-Dafalgan: Bateman-Funktion

```
C(t) = (ka / (ka - ke)) · (e^(-ke·t) - e^(-ka·t))
tmax = ln(ka / ke) / (ka - ke)
```

Medikinet retard im **Fastenzustand**: Enteric Coating kollabiert (kein Nahrungsbolus → schnelle Magenentleerung durch MMC), einheitliche Absorptionskurve statt Dual-Release.

#### Superposition (Mehrfachdosen)

Lineare Ueberlagerung mit Heaviside-Sprungfunktion:

```
C_total(t) = Σᵢ Cᵢ(t - τᵢ) · H(t - τᵢ)
```

Zukunftige Einnahmen tragen 0 bei (H = 0 fuer t < τ). Gueltig fuer alle Substanzen bei nicht-saettigenden Dosen.

### PK-Parametertabelle

| Substanz | Modell | ka (h⁻¹) | ke (h⁻¹) | Cmax_ref (70kg) | Cmax_96kg | t½ | F | Quelle |
|---|---|---|---|---|---|---|---|---|
| Elvanse 40mg | 3-Stufen-Kaskade | 2.0 + 0.78 | 0.088 | 36.0 ng/ml | 26.3 ng/ml | ~10-12h | 96.4% | Hutson 2017, Ermer 2016 |
| Medikinet IR 10mg | Bateman | 1.72 | 0.28 | 6.0 ng/ml | 4.4 ng/ml | 2.5h | ~30% | Kim 2017, Markowitz 2000 |
| Med. retard 30mg (nuechtern) | Bateman (kollabiert) | 1.2 | 0.28 | 12.0 ng/ml | 8.8 ng/ml | 2.5h | ~30% | Haessler 2008 |
| Koffein (Mate) 76mg | Bateman | 2.5 | 0.16 | 1500 ng/ml | 1094 ng/ml | 4.3h | ~99% | Kamimori 2002, Seng 2009 |
| Co-Dafalgan Codein 30mg | Bateman | 1.7 | 0.23 | 100 ng/ml | 73 ng/ml | ~3h | ~90% | -- |
| Co-Dafalgan Paracetamol 500mg | Bateman | 3.0 | 0.28 | 10000 ng/ml | 7292 ng/ml | ~2.5h | ~90% | -- |

Alle PK-Parameter sind via Umgebungsvariablen ueberschreibbar (siehe `config.py`).

---

## Drug-Drug-Interaction-Warnungen (DDI)

Das System prueft bei jeder Co-Dafalgan-Einnahme und auf der DDI-Check-Seite vier Interaktionstypen:

| # | Typ | Schwere | Trigger | Risiko |
|---|---|---|---|---|
| 1 | **CYP2D6-Blockade** | KRITISCH | Codein aktiv + d-Amph aktiv (>20% Cmax) | d-Amph blockiert CYP2D6 kompetitiv → Codein wird nicht zu Morphin konvertiert → analgetisches Versagen → Patient steigert Paracetamol-Dosis |
| 2 | **Serotonin-Syndrom** | KRITISCH | Opioid + normalisierte Stimulanzien-Summe > 0.3 | Serotonerge Exzitotoxizitaet: Klonus, Hyperreflexie, Diaphorese, autonome Instabilitaet |
| 3 | **Paracetamol-Toxizitaet** | KRITISCH / Warnung | Kumul. >2000mg/24h (Fasten) oder >1000mg (Vorsicht) | Glutathion depletiert (Fasten) → NAPQI nicht neutralisierbar → Hepatotoxizitaet |
| 4 | **ZNS-Ueberlastung** | Warnung | Stimulanzien-Summe >80% ref Cmax + Koffein >800 ng/ml | Kardiovaskulaere Erschoepfung, Arrhythmie-Risiko |

---

## Bio-Score (0-100)

Zusammengesetzte Kennzahl fuer kognitive Leistungsfaehigkeit:

| Komponente | Punkte | Quelle |
|---|---|---|
| Circadian-Rhythmus | 0-60 | Tageszeit (Peak 09-12h & 15-17h, Tief 13-14:30h & Nacht) |
| Elvanse-Boost | 0-30 | d-Amph relative Level × 30 |
| Medikinet-Boost (IR + retard) | 0-25 | MPH relative Level × 25 |
| Koffein-Boost | 0-15 | Koffein relative Level × 15 |
| Schlaf-Modifier | -20 bis +10 | Schlafdauer (<5h = -20, 8-9h = +5, >9h = +10) |
| **HRV-Penalty** | 0 bis -15 | HRV < 30ms bei Stimulanzien-Peak = -10; Ruhepuls >100 = -8 |
| **Summe** | **0-100** | Geclampt |

### Phase-Bestimmung

| Phase | Bedingung |
|---|---|
| `sleep` | Stunde < 6 |
| `waking` | 6-7h |
| `peak-focus` | Stimulanz-Level ≥ 0.85 |
| `active-focus` | ≥ 0.5 |
| `declining` | ≥ 0.2 |
| `low-residual` | ≥ 0.05 |
| `midday-dip` | 12:30-14:30 |
| `wind-down` | ≥ 20h |
| `baseline` | Sonst |

---

## Migraene-Tracking (IHS-Kriterien)

Strukturierte Erfassung basierend auf den Kriterien der International Headache Society:

| Feld | Typ | Beschreibung |
|---|---|---|
| `pain_severity` | 0-10 | Maximale Schmerzintensitaet |
| `aura_duration_min` | int | Dauer visueller Stoerungen (>60 Min = Warnung: vaskulaeres Ereignis) |
| `aura_type` | Enum | zickzack, skotome, flimmern, other |
| `photophobia` | Bool | Lichtempfindlichkeit |
| `phonophobia` | Bool | Laermempfindlichkeit |

Diese Felder werden in der Korrelationsanalyse gegen Stimulanzien-Einnahme-Offset geplottet.

---

## Datenbank-Schema (SQLite, WAL-Modus)

### Tabellen

**intake_events**
```
id (PK), timestamp, substance, dose_mg, notes
CHECK: substance IN (elvanse, mate, medikinet, medikinet_retard, co_dafalgan, other)
```

**subjective_logs**
```
id (PK), timestamp, focus (1-10), mood (1-10), energy (1-10),
appetite (1-10), inner_unrest (1-10),
pain_severity (0-10), aura_duration_min, aura_type, photophobia (0/1), phonophobia (0/1),
tags (JSON)
```

**health_snapshots**
```
id (PK), timestamp, heart_rate, resting_hr, hrv, sleep_duration,
sleep_confidence, spo2, respiratory_rate, steps, calories,
source (ha/manual/watch)
```

**meal_events**
```
id (PK), timestamp, meal_type (fruehstueck/mittagessen/abendessen/snack), notes
```

Alle Tabellen haben Timestamp-Indizes. 4 Migrationen laufen automatisch beim Start (Schema-Erweiterung via `ALTER TABLE`).

---

## API-Endpunkte

Authentifizierung: `X-API-Key` Header (env `BIO_API_KEY`). `/api/status` ist oeffentlich.

### Einnahmen

| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/api/intake` | Substanzeinnahme loggen (Standarddosen automatisch, DDI-Warnungen bei Co-Dafalgan) |
| GET | `/api/intake?today=true` | Heutige Einnahmen |
| GET | `/api/intake?start=...&end=...` | Zeitraum-Abfrage |
| GET | `/api/intake/latest?substance=elvanse` | Letzte Einnahme einer Substanz |
| DELETE | `/api/intake/{id}` | Einnahme loeschen |

### Subjektive Bewertung

| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/api/log` | Fokus/Laune/Energie + Migraene-Felder loggen |
| GET | `/api/log?today=true` | Heutige Logs |
| DELETE | `/api/log/{id}` | Log loeschen |

### Mahlzeiten

| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/api/meal` | Mahlzeit loggen (fruehstueck/mittagessen/abendessen/snack) |
| GET | `/api/meal?today=true` | Heutige Mahlzeiten |
| DELETE | `/api/meal/{id}` | Mahlzeit loeschen |

### Health / Vitals

| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/api/health` | Manueller Health-Snapshot |
| GET | `/api/health?start=...&end=...` | Snapshots im Zeitraum |
| GET | `/api/health/latest` | Letzter Snapshot |

### Analyse

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/bio-score` | Aktueller Bio-Score (nutzt HRV + Schlaf aus letztem Health-Snapshot) |
| GET | `/api/bio-score/curve?date=...&interval=15` | Tageskurve mit 15-Min-Intervall |
| GET | `/api/ddi-check` | Aktive DDI-Warnungen basierend auf heutigen Einnahmen |
| GET | `/api/model/fit` | Persoenliches Modell: Pearson-Korrelation Elvanse-Level vs. Fokus (90 Tage, min. 15 Paare) |
| GET | `/api/log-reminder` | Naechster faelliger subjektiver Log (relativ zu Elvanse: Baseline, +1.5h Onset, +4h Peak, +8h Decline, 22h Schlaf) |

### System / Webhooks

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/status` | Health Check (public): Version, Benutzer-Params, Modell-Name |
| POST | `/api/webhook/ha/intake` | HA-Automations-Webhook fuer Button-Einnahmen |
| GET | `/` | Service-Info |
| GET | `/docs` | OpenAPI Swagger UI |

---

## Dashboard UI (Streamlit)

Mobile-first, Dark Theme, Deutsch, keine Emojis. 6 Seiten via Sidebar-Navigation:

### 1. Logging (Hauptseite)

- **DDI-Warnungen** prominent oben (rot = kritisch, orange = warnung)
- **Log-Reminder**: Fortschrittsbalken (Logs heute / 5 Ziel), naechster faelliger Zeitpunkt
- **Einnahme-Buttons**: Elvanse 40mg, Lamate 76mg, Lamate x2, Medikinet 10mg, Co-Dafalgan 1x/2x
- **Nachtragen-Expander**: Alle Substanzen, freie Dosierung, Datum/Uhrzeit
- **Befinden-Sliders**: Fokus, Laune, Energie (1-10, 3er-Grid), Appetit, Innere Unruhe (2er-Grid)
- **Tag-Multiselect**: 14 Optionen (migraene, brain-fog, produktiv, ...)
- **Migraene-Expander**: Schmerzstaerke 0-10, Aura-Dauer, Aura-Typ, Photo/Phonophobie
- **Mahlzeiten-Buttons**: Mittagessen, Fruehstueck, Abendessen, Snack + Freitextnotiz
- **Heute-Uebersicht**: Einnahmen + Logs + Mahlzeiten mit Inline-Loeschen

### 2. Kurven & Timeline

- **Tages-Bioscorescore-Chart**: Bio-Score (gruen), Circadian (grau gestrichelt), Elvanse (blau), Medikinet (lila), Koffein (orange), HRV-Penalty (rot gestrichelt), Jetzt-Marker
- **Plasmakonzentrationen (ng/ml)**: Dual-Y-Achse -- Stimulanzien links (d-Amph, MPH, Codein), Koffein rechts (hoeherer Bereich)
- **Substanz-Level (relativ 0-1)**: Normierte Kurven + CNS-Last-Summe mit 1.5-Warnschwelle
- **Einnahme-Marker** (vertikale gestrichelte Linien), **Fokus-Diamonds**, **Migraene-X-Marker**
- **Modell-Dokumentation**: Formeln, allometrische Skalierungstabelle

### 3. Vitals & Health

- **Aktuelle Metriken**: HR, Resting HR, HRV (mit Kontext-Warnung bei <30ms), Schlaf, SpO2, Schritte, Kalorien
- **Tages-Charts**: Herzfrequenz-Linie, HRV-Linie (mit kritischer Zone <30ms rot markiert), Schritte-Balken

### 4. Persoenliches Modell

- **Datenfortschritt**: Paare gesammelt vs. 15 Minimum
- **Scatter-Plot**: Fokus-Ratings vs. Stunden nach Elvanse + theoretische Kaskadenkurve
- **Bei genuegend Daten**: Pearson-Korrelation, persoenlicher Peak-Offset, Wirkschwelle

### 5. Korrelation

- **Elvanse vs. Fokus**: Scatter (Offset in h seit Einnahme)
- **Schlaf vs. Fokus**: Scatter (Vornacht-Schlafdauer)
- **Migraene & Stimulanzien**: Scatter (Schmerzstaerke vs. Stimulanz-Offset)
- **Zaehler-Metriken**: Anzahl Intakes, Logs, Health-Snapshots

### 6. System

- **Service-Status**: Version, Modell-Name, Benutzer-Config (Gewicht, Groesse, Alter, Fasten-Status)
- **Letzte Einnahmen**: Pro Substanz (inkl. Co-Dafalgan)
- **DDI-Status**: Aktive Warnungen oder "Keine aktiven Interaktionswarnungen"
- **Log-Schedule**: Checklist aller Tageszeitpunkte
- **Allometrische Skalierungstabelle**: Referenz vs. angepasste Werte
- **API-Verbindungsinfo**

---

## Home Assistant Integration

**Polling**: APScheduler pollt alle 15 Minuten (konfigurierbar) ueber die HA REST API.

**Sensoren** (Pixel 9 Pro XL via HealthSync):

| Sensor | Entity ID | Verwendung |
|---|---|---|
| Herzfrequenz | `sensor.pixel_9_pro_xl_heart_rate_2` | Vitals-Anzeige |
| Ruhepuls | `sensor.pixel_9_pro_xl_resting_heart_rate_2` | Bio-Score HRV-Penalty |
| HRV | `sensor.pixel_9_pro_xl_heart_rate_variability_2` | **Bio-Score HRV-Penalty** (autonome Ueberwachung) |
| Schlafdauer | `sensor.pixel_9_pro_xl_sleep_duration_2` | Bio-Score Schlaf-Modifier |
| SpO2 | `sensor.pixel_9_pro_xl_oxygen_saturation_2` | Vitals-Anzeige |
| Atemfrequenz | `sensor.pixel_9_pro_xl_respiratory_rate_2` | Vitals-Anzeige |
| Schritte | `sensor.pixel_9_pro_xl_daily_steps_2` | Vitals-Anzeige |
| Kalorien | `sensor.pixel_9_pro_xl_active_calories_burned_2` | Vitals-Anzeige |
| Schlafmodus | `input_boolean.sleepmode` | Status |
| Im Bett | `input_boolean.inbed` | Status |

**Webhook**: HA-Automationen koennen Einnahmen direkt via `POST /api/webhook/ha/intake` loggen.

---

## Tech Stack

| Komponente | Version / Tool |
|---|---|
| Python | 3.12 (slim) |
| FastAPI | 0.115.0 |
| Uvicorn | 0.30.0 |
| Streamlit | 1.38.0 |
| Plotly | 5.24.0 |
| Pandas | 2.2.0 |
| Pydantic | 2.9.0 |
| httpx | 0.27.0 |
| APScheduler | 3.10.4 |
| SQLite | WAL-Modus, thread-local Connections |
| Docker | python:3.12-slim Base |
| Caddy | Reverse Proxy (auto_https off, Tunnel macht TLS) |
| Cloudflare Tunnel | Externer Zugang |
| Home Assistant | Nabu Casa Cloud API |

---

## Deployment

```bash
# Build + Deploy
docker compose build bio-dashboard
docker compose up bio-dashboard -d

# Logs pruefen
docker logs bio-dashboard --tail 30

# API testen
curl -H "x-api-key: $BIO_API_KEY" http://localhost:8000/api/bio-score
```

### Umgebungsvariablen (.env)

| Variable | Beschreibung | Default |
|---|---|---|
| `BIO_API_KEY` | API-Authentifizierung | (leer = kein Auth) |
| `HA_URL` | Home Assistant URL | `http://homeassistant.local:8123` |
| `HA_TOKEN` | HA Long-Lived Access Token | (pflicht fuer HA-Import) |
| `HA_POLL_INTERVAL_SEC` | Polling-Intervall | 900 (15 Min) |
| `USER_WEIGHT_KG` | Koerpergewicht (Allometrie) | 96 |
| `USER_HEIGHT_CM` | Koerpergroesse | 192 |
| `USER_AGE` | Alter | 19 |
| `USER_IS_FASTING` | Fastenprotokoll aktiv | true |
| `USER_IS_SMOKER` | Raucherstatus (CYP1A2) | false |
| `ELVANSE_KA`, `ELVANSE_KE`, ... | PK-Parameter (ueberschreibbar) | Siehe config.py |
| `BIO_DATA_DIR` | Datenverzeichnis | /data |
| `TZ` | Zeitzone | Europe/Zurich |

### Container-Architektur

```
bio-dashboard Container
├── uvicorn (FastAPI) :8000  ──> Caddy ──> bioapi.*.tech
├── streamlit :8501          ──> Caddy ──> bio.*.tech
└── /data/bio.db (SQLite, named volume bio_data)
```

---

## Datei-Struktur

```
bio-dashboard/
├── Dockerfile
├── start.sh                    # Startet uvicorn + streamlit parallel
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── config.py               # Alle Konfiguration + PK-Parameter + HA-Sensoren
│   ├── main.py                 # FastAPI-App, Lifespan, APScheduler
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py           # 20+ Endpunkte, Pydantic-Modelle, DDI-Check
│   ├── core/
│   │   ├── __init__.py
│   │   ├── bio_engine.py       # PK-Modelle (Kaskade + Bateman), Allometrie, DDI, Bio-Score
│   │   ├── database.py         # Schema, Migrationen (4x), CRUD
│   │   └── ha_importer.py      # HA REST API Polling, Sensor-Parsing
│   └── dashboard/
│       ├── __init__.py
│       └── streamlit_app.py    # 6-Seiten-UI, Plotly-Charts, DDI-Warnungen
└── data/                       # Lokales Dev-Datenverzeichnis
```
