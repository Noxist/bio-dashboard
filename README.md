# Life Manager -- Leandro Edition

Quantified-Self System mit pharmakokinetischem Modell (Bateman-Funktionen), Health-Tracking via Home Assistant, und adaptivem Modell-Training.

## Module

### Etappe 1: Bio-Dashboard (aktiv)
- **FastAPI** Backend (Port 8000) + **Streamlit** Frontend (Port 8501)
- Pharmakokinetik-Modellierung: Elvanse, Medikinet IR/retard, Koffein (Bateman-Funktionen)
- Bio-Score: Circadian-Rhythmus + Substanz-Boosts + Schlaf-Modifier
- Home Assistant Integration (Pixel Watch Health-Sensoren)
- Subjektive Bewertung (Fokus, Laune, Energie, Appetit, Innere Unruhe)
- Mahlzeiten-Tracking
- Adaptives Modell-Training (Elvanse-Wirkungskurve personalisieren)
- Log-Reminder (5x/Tag optimaler Schedule)
- CNS-Last Warnung

### Etappe 2: Auto-Barber (geplant)
### Etappe 3: Super Mega Ultra Planer (geplant)
### Etappe 4: Daily Briefing (geplant)

## Tech Stack
- Python 3.11, FastAPI, Streamlit, Plotly
- SQLite (WAL mode), APScheduler
- Docker, Caddy Reverse Proxy, Cloudflare Tunnel
- Home Assistant (Nabu Casa)

## Deployment
```bash
docker compose build bio-dashboard
docker compose up bio-dashboard -d
```

## PK-Modell
Bateman-Funktion: `C(t) = (ka / (ka - ke)) * (exp(-ke*t) - exp(-ka*t))`

| Substanz | ka (h-1) | ke (h-1) | Tmax | t1/2 | Quelle |
|----------|----------|----------|------|------|--------|
| Elvanse | 0.78 | 0.088 | 3.8h | ~10h | Hutson 2017 |
| Medikinet IR | 1.72 | 0.28 | 1.5h | 2.5h | Kim 2017 |
| Med. retard (nuechtern) | 1.2 | 0.28 | 2h | 2.5h | Haessler 2008 |
| Koffein | 2.5 | 0.16 | 0.75h | 4.3h | Kamimori 2002 |
