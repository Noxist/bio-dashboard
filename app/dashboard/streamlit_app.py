"""
Streamlit Bio-Dashboard -- Leandro Edition.
Views: Quick-Log, Timeline, Korrelation, Status.
Mobile-first, no emojis.
"""

import json
from datetime import datetime, timedelta, time as dt_time

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# --- Config ---
import os

API_BASE = os.getenv("BIO_API_URL", "http://localhost:8000")
API_KEY = os.getenv("BIO_API_KEY", "")
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}


def api_get(path: str, params: dict | None = None) -> dict | list:
    try:
        r = httpx.get(f"{API_BASE}{path}", params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return {}


def api_post(path: str, data: dict) -> dict:
    try:
        r = httpx.post(f"{API_BASE}{path}", json=data, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return {}


def api_delete(path: str) -> dict:
    try:
        r = httpx.delete(f"{API_BASE}{path}", headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return {}


# --- Page Config ---
st.set_page_config(
    page_title="Bio-Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Mobile-first CSS (Pixel 9 Pro XL optimized)
st.markdown("""
<style>
    /* Tighter top padding */
    .block-container {
        padding-top: 0.5rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
        max-width: 100%;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background-color: #1e1e2e;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 10px 12px;
    }
    div[data-testid="stMetric"] label {
        font-size: 0.75rem;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.4rem;
    }

    /* Bigger touch targets for buttons */
    .stButton > button {
        min-height: 48px;
        font-size: 0.95rem;
        border-radius: 8px;
    }

    /* Sidebar compact */
    section[data-testid="stSidebar"] {
        width: 200px !important;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    /* Expander headers */
    .streamlit-expanderHeader {
        font-size: 0.95rem;
    }

    /* Dividers -- less spacing on mobile */
    hr {
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
    }

    /* Columns gap tighter */
    [data-testid="column"] {
        padding: 0 4px;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
    }
    .stTabs [data-baseweb="tab"] {
        min-height: 44px;
        padding: 8px 12px;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Tab Navigation (mobile-friendly, no sidebar needed) ---
tab_quicklog, tab_timeline, tab_korrelation, tab_modell, tab_status = st.tabs([
    "Quick-Log", "Timeline", "Korrelation", "Modell", "Status"
])

# ============================
# TAB: Quick-Log
# ============================
with tab_quicklog:
    st.header("Quick-Log")

    # --- Log Reminder Banner ---
    reminder = api_get("/api/log-reminder")
    if isinstance(reminder, dict) and reminder.get("next_due"):
        next_due = reminder["next_due"]
        logs_done = reminder.get("logs_today", 0)
        target = reminder.get("target_logs", 5)
        schedule = reminder.get("schedule", [])

        progress = min(logs_done / max(target, 1), 1.0)
        st.progress(progress, text=f"Logs heute: {logs_done}/{target}")

        if next_due["status"] == "due":
            st.warning(f"Log faellig: {next_due['label']} ({next_due['target_time']})")
        else:
            st.info(f"Naechster Log: {next_due['label']} um {next_due['target_time']}")

        with st.expander("Tages-Schedule"):
            for s in schedule:
                icon = "[x]" if s["status"] == "done" else (">>>" if s["status"] == "due" else "[ ]")
                st.text(f"{icon} {s['target_time']} {s['label']}")

    # --- Quick Buttons ---
    st.subheader("Jetzt loggen")
    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        if st.button("Elvanse 40mg", use_container_width=True, type="primary"):
            result = api_post("/api/intake", {"substance": "elvanse", "dose_mg": 40})
            if result.get("status") == "ok":
                st.success("Elvanse 40mg geloggt")
                st.rerun()

    with btn_col2:
        if st.button("Lamate 76mg", use_container_width=True, type="primary"):
            result = api_post("/api/intake", {"substance": "mate", "dose_mg": 76})
            if result.get("status") == "ok":
                st.success("Lamate geloggt")
                st.rerun()

    btn_col3, btn_col4 = st.columns(2)

    with btn_col3:
        if st.button("Medikinet IR 10mg", use_container_width=True):
            result = api_post("/api/intake", {"substance": "medikinet", "dose_mg": 10})
            if result.get("status") == "ok":
                st.success("Medikinet IR 10mg geloggt")
                st.rerun()

    with btn_col4:
        if st.button("Med. retard 30mg", use_container_width=True):
            result = api_post("/api/intake", {"substance": "medikinet_retard", "dose_mg": 30})
            if result.get("status") == "ok":
                st.success("Medikinet retard 30mg geloggt")
                st.rerun()

    btn_col5, btn_col6 = st.columns(2)

    with btn_col5:
        if st.button("Lamate x2 (152mg)", use_container_width=True):
            result = api_post("/api/intake", {"substance": "mate", "dose_mg": 152})
            if result.get("status") == "ok":
                st.success("Doppel-Lamate geloggt")
                st.rerun()

    with btn_col6:
        pass  # placeholder for future

    # --- Bio-Score ---
    st.divider()
    bio = api_get("/api/bio-score")
    if isinstance(bio, dict) and "score" in bio:
        score = bio["score"]
        phase = bio.get("phase", "?")
        elvanse_lvl = bio.get("elvanse_level", 0)
        caffeine_lvl = bio.get("caffeine_level", 0)
        medikinet_lvl = bio.get("medikinet_level", 0)

        if score >= 75:
            score_label = "Hoch"
        elif score >= 50:
            score_label = "Mittel"
        elif score >= 30:
            score_label = "Niedrig"
        else:
            score_label = "Tief"

        m1, m2 = st.columns(2)
        m1.metric("Bio-Score", f"{score:.0f}/100", help=score_label)
        m2.metric("Phase", phase)

        m3, m4, m5 = st.columns(3)
        m3.metric("Elvanse", f"{elvanse_lvl:.0%}")
        m4.metric("Medikinet", f"{medikinet_lvl:.0%}")
        m5.metric("Koffein", f"{caffeine_lvl:.0%}")

        # CNS Stimulant Load warning
        cns_load = bio.get("cns_load", 0)
        if cns_load > 2.0:
            st.warning(f"CNS-Last: {cns_load:.1f} -- Hohe Stimulanzien-Belastung!")
        elif cns_load > 1.5:
            st.info(f"CNS-Last: {cns_load:.1f} -- Erhoehte Stimulanzien-Belastung")

    # --- Meal Tracking ---
    st.divider()
    with st.expander("Mahlzeit loggen"):
        meal_notes = st.text_input("Notizen (optional)", key="meal_notes", placeholder="z.B. Pizza, Salat...")

        meal_cols = st.columns(2)
        with meal_cols[0]:
            if st.button("Fruehstueck", use_container_width=True):
                result = api_post("/api/meal", {"meal_type": "fruehstueck", "notes": meal_notes})
                if result.get("status") == "ok":
                    st.success("Fruehstueck geloggt")
                    st.rerun()
            if st.button("Mittagessen", use_container_width=True):
                result = api_post("/api/meal", {"meal_type": "mittagessen", "notes": meal_notes})
                if result.get("status") == "ok":
                    st.success("Mittagessen geloggt")
                    st.rerun()
        with meal_cols[1]:
            if st.button("Abendessen", use_container_width=True):
                result = api_post("/api/meal", {"meal_type": "abendessen", "notes": meal_notes})
                if result.get("status") == "ok":
                    st.success("Abendessen geloggt")
                    st.rerun()
            if st.button("Snack", use_container_width=True):
                result = api_post("/api/meal", {"meal_type": "snack", "notes": meal_notes})
                if result.get("status") == "ok":
                    st.success("Snack geloggt")
                    st.rerun()

        # Today's meals
        meals_today = api_get("/api/meal", {"today": "true"})
        if isinstance(meals_today, list) and meals_today:
            st.caption("Heutige Mahlzeiten:")
            for meal in meals_today:
                ts = meal.get("timestamp", "")
                ts_short = ts[11:16] if len(ts) > 16 else ts
                mtype = meal.get("meal_type", "?")
                mnotes = meal.get("notes", "")
                mnotes_str = f" - {mnotes}" if mnotes else ""
                meal_id = meal.get("id")

                entry_col, del_col = st.columns([5, 1])
                with entry_col:
                    st.text(f"{ts_short}  {mtype}{mnotes_str}")
                with del_col:
                    if st.button("X", key=f"del_meal_{meal_id}", help="Loeschen"):
                        result = api_delete(f"/api/meal/{meal_id}")
                        if result.get("status") == "ok":
                            st.rerun()

    # --- Historical Entry ---
    with st.expander("Historischen Eintrag nachtragen"):
        h_col1, h_col2 = st.columns(2)

        with h_col1:
            hist_substance = st.selectbox(
                "Substanz", ["elvanse", "mate", "medikinet", "medikinet_retard", "other"],
                key="hist_substance"
            )
        with h_col2:
            default_dose = {
                "elvanse": 40.0, "mate": 76.0,
                "medikinet": 10.0, "medikinet_retard": 30.0, "other": 0.0,
            }
            hist_dose = st.number_input(
                "Dosis (mg)", min_value=0.0, step=10.0,
                value=default_dose.get(hist_substance, 0.0),
                key="hist_dose"
            )

        hist_notes = st.text_input("Notizen", key="hist_notes")

        d_col1, d_col2 = st.columns(2)
        with d_col1:
            hist_date = st.date_input("Datum", value=datetime.now().date(), key="hist_date")
        with d_col2:
            hist_time = st.time_input("Uhrzeit", value=datetime.now().time().replace(second=0, microsecond=0), key="hist_time")

        if st.button("Historisch loggen", type="primary", use_container_width=True):
            ts = datetime.combine(hist_date, hist_time).isoformat()
            payload = {
                "substance": hist_substance,
                "dose_mg": hist_dose if hist_dose > 0 else None,
                "notes": hist_notes,
                "timestamp": ts,
            }
            result = api_post("/api/intake", payload)
            if result.get("status") == "ok":
                st.success(f"{hist_substance} {hist_dose}mg am {hist_date} um {hist_time} geloggt")
                st.rerun()

    # --- Subjective Log ---
    with st.expander("Subjektive Bewertung"):
        s_col1, s_col2, s_col3 = st.columns(3)

        with s_col1:
            focus = st.slider("Fokus", 1, 10, 5, key="focus_slider")
        with s_col2:
            mood = st.slider("Laune", 1, 10, 5, key="mood_slider")
        with s_col3:
            energy = st.slider("Energie", 1, 10, 5, key="energy_slider")

        s_col4, s_col5 = st.columns(2)
        with s_col4:
            appetite = st.slider("Appetit", 1, 10, 5, key="appetite_slider")
        with s_col5:
            inner_unrest = st.slider("Innere Unruhe", 1, 10, 1, key="unrest_slider")

        tag_options = [
            "migraene", "kopfschmerzen", "uebelkeit",
            "muede", "unruhig", "motiviert",
            "klar", "brain-fog", "angespannt", "entspannt",
            "kreativ", "gereizt", "produktiv", "abgelenkt",
        ]
        tags = st.multiselect("Tags", tag_options, key="tags_select")

        if st.button("Bewertung speichern", type="primary", use_container_width=True):
            result = api_post("/api/log", {
                "focus": focus, "mood": mood, "energy": energy,
                "appetite": appetite, "inner_unrest": inner_unrest,
                "tags": tags,
            })
            if result.get("status") == "ok":
                st.success("Bewertung gespeichert")
                st.rerun()

    # --- Today's Log with delete ---
    st.divider()
    st.subheader("Heutiger Verlauf")

    t_col1, t_col2 = st.columns(2)

    with t_col1:
        st.caption("**Intakes**")
        intakes = api_get("/api/intake", {"today": True})
        if isinstance(intakes, list) and intakes:
            for i in intakes:
                ts = i.get("timestamp", "")
                ts_short = ts[11:16] if len(ts) > 16 else ts
                sub = i.get("substance", "?")
                dose = i.get("dose_mg", "")
                dose_str = f" {dose}mg" if dose else ""
                intake_id = i.get("id")
                notes = i.get("notes", "")
                notes_str = f" ({notes})" if notes else ""

                label = {"elvanse": "ELV", "mate": "MAT", "medikinet": "MED", "medikinet_retard": "MR"}.get(sub, sub.upper()[:3])

                entry_col, del_col = st.columns([5, 1])
                with entry_col:
                    st.text(f"{ts_short}  [{label}]{dose_str}{notes_str}")
                with del_col:
                    if st.button("X", key=f"del_intake_{intake_id}", help="Loeschen"):
                        result = api_delete(f"/api/intake/{intake_id}")
                        if result.get("status") == "ok":
                            st.rerun()
        else:
            st.info("Noch keine Intakes heute")

    with t_col2:
        st.caption("**Subjektive Logs**")
        logs = api_get("/api/log", {"today": True})
        if isinstance(logs, list) and logs:
            for log_entry in logs:
                ts = log_entry.get("timestamp", "")
                ts_short = ts[11:16] if len(ts) > 16 else ts
                f_val = log_entry.get("focus", "?")
                m_val = log_entry.get("mood", "?")
                e_val = log_entry.get("energy", "?")
                a_val = log_entry.get("appetite", "-")
                u_val = log_entry.get("inner_unrest", "-")
                log_id = log_entry.get("id")
                tags_raw = log_entry.get("tags", "[]")
                if isinstance(tags_raw, str):
                    tags_list = json.loads(tags_raw)
                else:
                    tags_list = tags_raw
                tags_str = f" [{', '.join(tags_list)}]" if tags_list else ""

                entry_col, del_col = st.columns([5, 1])
                with entry_col:
                    st.text(f"{ts_short}  F:{f_val} M:{m_val} E:{e_val} A:{a_val} U:{u_val}{tags_str}")
                with del_col:
                    if st.button("X", key=f"del_log_{log_id}", help="Loeschen"):
                        result = api_delete(f"/api/log/{log_id}")
                        if result.get("status") == "ok":
                            st.rerun()
        else:
            st.info("Noch keine Logs heute")


# ============================
# TAB: Timeline
# ============================
with tab_timeline:
    st.header("Tages-Timeline")

    date = st.date_input("Datum", value=datetime.now().date(), key="timeline_date")
    date_str = date.isoformat()

    curve_data = api_get("/api/bio-score/curve", {"date": date_str, "interval": 15})

    if isinstance(curve_data, dict) and "points" in curve_data:
        points = curve_data["points"]
        df = pd.DataFrame(points)

        if not df.empty:
            df["time"] = pd.to_datetime(df["timestamp"])

            now = datetime.now()
            is_today = date == now.date()

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=df["time"], y=df["score"],
                mode="lines", name="Bio-Score",
                line=dict(color="#4CAF50", width=3),
                fill="tozeroy", fillcolor="rgba(76,175,80,0.1)",
            ))

            fig.add_trace(go.Scatter(
                x=df["time"], y=df["circadian"],
                mode="lines", name="Circadian Base",
                line=dict(color="#9E9E9E", width=1, dash="dot"),
            ))

            fig.add_trace(go.Scatter(
                x=df["time"], y=df["elvanse_boost"],
                mode="lines", name="Elvanse Boost",
                line=dict(color="#2196F3", width=2),
            ))

            # Medikinet boost trace
            if "medikinet_boost" in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["time"], y=df["medikinet_boost"],
                    mode="lines", name="Medikinet Boost",
                    line=dict(color="#AB47BC", width=2),
                ))

            fig.add_trace(go.Scatter(
                x=df["time"], y=df["caffeine_boost"],
                mode="lines", name="Koffein Boost",
                line=dict(color="#FF9800", width=2),
            ))

            # Helper: vertical line + annotation (avoids plotly add_vline bug with Timestamps)
            def _add_vmarker(fig, x_val, color, dash, width, text, pos="top right"):
                fig.add_shape(
                    type="line", x0=x_val, x1=x_val, y0=0, y1=1,
                    yref="paper", line=dict(color=color, width=width, dash=dash),
                )
                fig.add_annotation(
                    x=x_val, y=1, yref="paper", text=text,
                    showarrow=False, font=dict(color=color, size=10),
                    xanchor="left" if "left" in pos else "right",
                    yanchor="bottom",
                )

            # Now marker
            if is_today:
                _add_vmarker(fig, now, "#F44336", "solid", 2, "Jetzt", "top left")

            # Intake markers
            intakes = api_get("/api/intake", {"start": f"{date_str}T00:00:00", "end": f"{date_str}T23:59:59"})
            if isinstance(intakes, list):
                for intake in intakes:
                    t = intake["timestamp"]
                    sub = intake.get("substance", "?")
                    dose = intake.get("dose_mg", "")
                    color_map = {
                        "elvanse": "#2196F3",
                        "mate": "#FF9800",
                        "medikinet": "#AB47BC",
                        "medikinet_retard": "#7B1FA2",
                    }
                    color = color_map.get(sub, "#9C27B0")
                    label_map = {"elvanse": "ELV", "mate": "MAT", "medikinet": "MED", "medikinet_retard": "MR"}
                    label = label_map.get(sub, sub[:3].upper())
                    _add_vmarker(fig, t, color, "dash", 1, f"{label} {dose}mg")

            # Subjective log markers
            logs = api_get("/api/log", {"start": f"{date_str}T00:00:00", "end": f"{date_str}T23:59:59"})
            if isinstance(logs, list):
                for log_entry in logs:
                    t = pd.to_datetime(log_entry["timestamp"])
                    focus = log_entry.get("focus", 5)
                    fig.add_trace(go.Scatter(
                        x=[t], y=[focus * 10],
                        mode="markers", name="Fokus-Rating",
                        marker=dict(size=12, color="#E91E63", symbol="diamond"),
                        showlegend=False,
                        hovertext=f"Fokus: {focus}/10",
                    ))

            fig.update_layout(
                title=f"Bio-Score Verlauf -- {date_str}",
                xaxis_title="Uhrzeit",
                yaxis_title="Score",
                yaxis=dict(range=[0, 105]),
                height=450,
                template="plotly_dark",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(l=40, r=20, t=60, b=40),
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Keine Daten fuer dieses Datum")

    # Health data
    st.subheader("Gesundheitsdaten")
    health = api_get("/api/health", {"start": f"{date_str}T00:00:00", "end": f"{date_str}T23:59:59"})
    if isinstance(health, list) and health:
        hdf = pd.DataFrame(health)
        hdf["time"] = pd.to_datetime(hdf["timestamp"])

        h1, h2 = st.columns(2)
        with h1:
            if "heart_rate" in hdf.columns and hdf["heart_rate"].notna().any():
                fig_hr = go.Figure()
                fig_hr.add_trace(go.Scatter(
                    x=hdf["time"], y=hdf["heart_rate"],
                    mode="lines+markers", name="Heart Rate",
                    line=dict(color="#F44336"),
                ))
                fig_hr.update_layout(
                    title="Herzfrequenz", yaxis_title="bpm",
                    height=280, template="plotly_dark",
                    margin=dict(l=40, r=20, t=40, b=30),
                )
                st.plotly_chart(fig_hr, use_container_width=True)

        with h2:
            if "hrv" in hdf.columns and hdf["hrv"].notna().any():
                fig_hrv = go.Figure()
                fig_hrv.add_trace(go.Scatter(
                    x=hdf["time"], y=hdf["hrv"],
                    mode="lines+markers", name="HRV",
                    line=dict(color="#3F51B5"),
                ))
                fig_hrv.update_layout(
                    title="HRV", yaxis_title="ms",
                    height=280, template="plotly_dark",
                    margin=dict(l=40, r=20, t=40, b=30),
                )
                st.plotly_chart(fig_hrv, use_container_width=True)
    else:
        st.info("Keine Gesundheitsdaten fuer dieses Datum")


# ============================
# TAB: Korrelation
# ============================
with tab_korrelation:
    st.header("Korrelationsanalyse")

    days_back = st.slider("Tage zurueck", 7, 90, 30, key="corr_days")
    now = datetime.now()
    start = (now - timedelta(days=days_back)).isoformat()
    end = now.isoformat()

    intakes = api_get("/api/intake", {"start": start, "end": end})
    logs = api_get("/api/log", {"start": start, "end": end})
    health = api_get("/api/health", {"start": start, "end": end})

    if not isinstance(intakes, list) or not isinstance(logs, list):
        st.warning("Nicht genuegend Daten fuer Korrelationsanalyse")
    else:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Elvanse-Offset vs. Fokus")
            st.caption("Zeitabstand zwischen Elvanse und Fokus-Rating")

            pairs = []
            elvanse_intakes = [i for i in intakes if i.get("substance") == "elvanse"]

            for log_entry in logs:
                log_time = datetime.fromisoformat(log_entry["timestamp"])
                focus = log_entry.get("focus")
                if focus is None:
                    continue

                best_offset = None
                for ei in elvanse_intakes:
                    ei_time = datetime.fromisoformat(ei["timestamp"])
                    offset_h = (log_time - ei_time).total_seconds() / 3600
                    if 0 <= offset_h <= 16:
                        if best_offset is None or offset_h < best_offset:
                            best_offset = offset_h

                if best_offset is not None:
                    pairs.append({"offset_h": best_offset, "focus": focus})

            if pairs:
                pdf = pd.DataFrame(pairs)
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=pdf["offset_h"], y=pdf["focus"],
                    mode="markers",
                    marker=dict(size=8, color="#2196F3", opacity=0.7),
                ))
                fig.update_layout(
                    xaxis_title="Stunden nach Elvanse",
                    yaxis_title="Fokus (1-10)",
                    height=350, template="plotly_dark",
                    margin=dict(l=40, r=20, t=30, b=40),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Noch keine Paare (Elvanse + Fokus-Log)")

        with col2:
            st.subheader("Schlaf vs. Naechster-Tag-Fokus")

            if isinstance(health, list) and health:
                sleep_by_day = {}
                for h in health:
                    day = h["timestamp"][:10]
                    sd = h.get("sleep_duration")
                    if sd is not None:
                        sleep_by_day[day] = sd

                sleep_focus_pairs = []
                for log_entry in logs:
                    log_day = log_entry["timestamp"][:10]
                    prev_day = (datetime.fromisoformat(log_day) - timedelta(days=1)).strftime("%Y-%m-%d")
                    focus = log_entry.get("focus")
                    if focus and prev_day in sleep_by_day:
                        sleep_focus_pairs.append({
                            "sleep_h": sleep_by_day[prev_day] / 60.0,
                            "focus": focus,
                        })

                if sleep_focus_pairs:
                    sdf = pd.DataFrame(sleep_focus_pairs)
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=sdf["sleep_h"], y=sdf["focus"],
                        mode="markers",
                        marker=dict(size=8, color="#4CAF50", opacity=0.7),
                    ))
                    fig.update_layout(
                        xaxis_title="Schlaf (Stunden, Vornacht)",
                        yaxis_title="Fokus naechster Tag",
                        height=350, template="plotly_dark",
                        margin=dict(l=40, r=20, t=30, b=40),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Noch keine Schlaf-Fokus-Paare")
            else:
                st.info("Keine Gesundheitsdaten vorhanden")

        st.divider()
        st.subheader("Zusammenfassung")

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Intakes", len(intakes) if isinstance(intakes, list) else 0)
        mc2.metric("Subj. Logs", len(logs) if isinstance(logs, list) else 0)
        mc3.metric("Health Snaps", len(health) if isinstance(health, list) else 0)

        elvanse_count = len([i for i in intakes if i.get("substance") == "elvanse"]) if isinstance(intakes, list) else 0
        mate_count = len([i for i in intakes if i.get("substance") == "mate"]) if isinstance(intakes, list) else 0
        mc4.metric("ELV / MAT", f"{elvanse_count} / {mate_count}")


# ============================
# TAB: Modell (Adaptive PK Fitting)
# ============================
with tab_modell:
    st.header("Persoenliches Modell")
    st.caption(
        "Analysiert deine Fokus-Ratings und Elvanse-Einnahmen, "
        "um deine persoenliche Wirkungskurve zu berechnen. "
        "Je mehr Daten, desto praeziser."
    )

    model_data = api_get("/api/model/fit")

    if isinstance(model_data, dict):
        m_status = model_data.get("status", "error")
        pairs_count = model_data.get("pairs", 0)
        required = model_data.get("required", 15)

        st.progress(min(pairs_count / max(required, 1), 1.0), text=f"Datenpunkte: {pairs_count}/{required}")

        if m_status == "insufficient_data":
            st.warning(model_data.get("message", "Nicht genug Daten."))

            if pairs_count > 0:
                st.subheader("Bisherige Datenpunkte")
                collected = model_data.get("collected_pairs", [])
                if collected:
                    cpdf = pd.DataFrame(collected)
                    fig_m = go.Figure()
                    fig_m.add_trace(go.Scatter(
                        x=cpdf["offset_h"], y=cpdf["focus"],
                        mode="markers",
                        marker=dict(size=10, color="#2196F3", opacity=0.7),
                        name="Fokus-Rating",
                    ))
                    fig_m.add_trace(go.Scatter(
                        x=cpdf["offset_h"], y=cpdf["predicted_level"].apply(lambda x: x * 10),
                        mode="lines",
                        line=dict(color="#FF9800", width=2, dash="dash"),
                        name="Theoretische Kurve (skaliert)",
                    ))
                    fig_m.update_layout(
                        xaxis_title="Stunden nach Elvanse",
                        yaxis_title="Fokus (1-10) / Level x10",
                        height=350, template="plotly_dark",
                        margin=dict(l=40, r=20, t=30, b=40),
                    )
                    st.plotly_chart(fig_m, use_container_width=True)

        elif m_status == "ok":
            st.success("Modell erfolgreich berechnet!")

            r1, r2, r3 = st.columns(3)
            r1.metric("Korrelation", f"{model_data.get('correlation', 0):.2f}")
            r2.metric("Persoenl. Peak", f"{model_data.get('personal_peak_offset_h', '?')}h")
            threshold = model_data.get("personal_threshold")
            r3.metric("Wirkschwelle", f"{threshold:.2f}" if threshold else "?")

            st.info(model_data.get("recommendation", ""))

            collected = model_data.get("collected_pairs", [])
            if collected:
                cpdf = pd.DataFrame(collected)
                fig_m = go.Figure()
                fig_m.add_trace(go.Scatter(
                    x=cpdf["offset_h"], y=cpdf["focus"],
                    mode="markers",
                    marker=dict(size=10, color="#2196F3", opacity=0.7),
                    name="Deine Fokus-Ratings",
                ))
                fig_m.add_trace(go.Scatter(
                    x=cpdf["offset_h"], y=cpdf["predicted_level"].apply(lambda x: x * 10),
                    mode="lines",
                    line=dict(color="#FF9800", width=2),
                    name="Modell-Vorhersage (skaliert)",
                ))
                if threshold:
                    fig_m.add_hline(
                        y=7, line=dict(color="#4CAF50", width=1, dash="dash"),
                        annotation_text="Fokus >= 7 (Ziel)",
                    )
                fig_m.update_layout(
                    xaxis_title="Stunden nach Elvanse",
                    yaxis_title="Fokus (1-10) / Predicted Level x10",
                    height=400, template="plotly_dark",
                    margin=dict(l=40, r=20, t=30, b=40),
                )
                st.plotly_chart(fig_m, use_container_width=True)

    st.divider()
    st.subheader("PK-Parameter (aktuell)")
    st.caption("Literaturbasiert (Gemini Deep Research). Werden mit genuegend Daten individuell angepasst.")

    pk_data = {
        "Elvanse": {"ka": "0.78 h-1", "ke": "0.088 h-1", "Tmax": "3.8h", "t1/2": "~10h", "Dauer": "14h"},
        "Medikinet IR": {"ka": "1.72 h-1", "ke": "0.28 h-1", "Tmax": "1.5h", "t1/2": "2.5h", "Dauer": "3-4h"},
        "Med. retard": {"ka": "1.2 h-1 (nuechtern)", "ke": "0.28 h-1", "Tmax": "2h", "t1/2": "2.5h", "Dauer": "4-6h"},
        "Koffein": {"ka": "2.5 h-1", "ke": "0.16 h-1", "Tmax": "0.75h", "t1/2": "4.3h", "Dauer": "~6h"},
    }
    st.dataframe(pd.DataFrame(pk_data).T, use_container_width=True)


# ============================
# TAB: Status
# ============================
with tab_status:
    st.header("System Status")

    status = api_get("/api/status")
    if isinstance(status, dict):
        s1, s2 = st.columns(2)
        with s1:
            st.metric("Service", status.get("service", "?"))
        with s2:
            st.metric("Status", status.get("status", "?"))
        st.caption(f"Server-Zeit: {status.get('timestamp', '?')}")

        user_info = status.get("user", {})
        if user_info:
            u1, u2, u3 = st.columns(3)
            u1.metric("Gewicht", f"{user_info.get('weight_kg', '?')} kg")
            u2.metric("Groesse", f"{user_info.get('height_cm', '?')} cm")
            u3.metric("Fasten", "Ja" if user_info.get("fasting") else "Nein")

    st.divider()
    st.subheader("Letzter Health Snapshot")
    latest_health = api_get("/api/health/latest")
    if isinstance(latest_health, dict) and latest_health.get("found"):
        h_cols = st.columns(4)
        fields = [
            ("heart_rate", "HR", "bpm"),
            ("resting_hr", "Resting HR", "bpm"),
            ("hrv", "HRV", "ms"),
            ("sleep_duration", "Schlaf", "min"),
            ("spo2", "SpO2", "%"),
            ("steps", "Schritte", ""),
            ("calories", "Kalorien", "kcal"),
        ]
        for idx, (key, label, unit) in enumerate(fields):
            val = latest_health.get(key)
            if val is not None:
                h_cols[idx % 4].metric(label, f"{val} {unit}")

        st.caption(f"Quelle: {latest_health.get('source', '?')} | Zeit: {latest_health.get('timestamp', '?')}")
    else:
        st.info("Noch keine Gesundheitsdaten")

    st.divider()
    st.subheader("Letzte Intakes")

    for sub_name, sub_label in [("elvanse", "Elvanse"), ("medikinet", "Medikinet IR"), ("medikinet_retard", "Medikinet retard")]:
        latest = api_get("/api/intake/latest", {"substance": sub_name})
        if isinstance(latest, dict) and latest.get("found"):
            ts = latest.get("timestamp", "?")
            dose = latest.get("dose_mg", "?")
            try:
                intake_time = datetime.fromisoformat(ts)
                delta = datetime.now() - intake_time
                hours = delta.total_seconds() / 3600
                st.text(f"{sub_label}: {dose}mg -- vor {hours:.1f}h ({ts[11:16]})")
            except Exception:
                st.text(f"{sub_label}: {dose}mg @ {ts}")
        else:
            st.text(f"{sub_label}: --")

    st.divider()
    st.subheader("Debug-Info")
    st.code(f"API_BASE: {API_BASE}\nAPI_KEY: {'***' + API_KEY[-4:] if len(API_KEY) > 4 else '(nicht gesetzt)'}")
