"""
Streamlit Bio-Dashboard — Leandro Edition v3.
Hauptseite: Schnelle Inputs (Einnahme, Befinden, Essen, Hydration).
Sidebar (Hamburger): Kurven, Vitals, Modell, Korrelation, System.
Mobile-first, proper German, no emojis.
"""

import math
from datetime import datetime, timedelta

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import os

# --- Config ---
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


def _get_dash_weight() -> float:
    """Get current user weight from API for display."""
    w = api_get("/api/weight/latest")
    if isinstance(w, dict) and w.get("found"):
        return float(w.get("weight_kg", 96.0))
    return 96.0


# --- Plotly mobile-friendly helper ---
PLOTLY_MOBILE_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "staticPlot": False,
    "responsive": True,
}

PLOTLY_MOBILE_LAYOUT = dict(
    dragmode=False,
    template="plotly_dark",
    margin=dict(l=40, r=20, t=40, b=35),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    xaxis=dict(fixedrange=True),
    yaxis=dict(fixedrange=True),
)


def mobile_chart(fig, height=350, **kwargs):
    """Render a Plotly chart with mobile-friendly settings (no accidental zoom/pan)."""
    fig.update_layout(**PLOTLY_MOBILE_LAYOUT, height=height, **kwargs)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_MOBILE_CONFIG)


# --- Page Config ---
st.set_page_config(
    page_title="Bio-Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Mobile-first CSS
st.markdown("""
<style>
    .block-container {
        padding-top: 0.3rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
        max-width: 100%;
    }
    div[data-testid="stMetric"] {
        background-color: #1e1e2e;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 8px 10px;
    }
    div[data-testid="stMetric"] label { font-size: 0.7rem; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { font-size: 1.3rem; }
    .stButton > button {
        min-height: 52px;
        font-size: 1rem;
        border-radius: 10px;
    }
    section[data-testid="stSidebar"] { width: 280px !important; }
    hr { margin-top: 0.4rem; margin-bottom: 0.4rem; }
    [data-testid="column"] { padding: 0 3px; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR — Navigation + Quick-Status
# =========================================================
PAGES = [
    "Logging",
    "Hydration",
    "Kurven & Timeline",
    "Vitals & Health",
    "Persönl. Modell",
    "Korrelation",
    "System",
]
PAGE_MAP = {
    "Logging": "main",
    "Hydration": "hydration",
    "Kurven & Timeline": "kurven",
    "Vitals & Health": "vitals",
    "Persönl. Modell": "modell",
    "Korrelation": "korrelation",
    "System": "system",
}

with st.sidebar:
    st.header("Bio-Dashboard")
    sidebar_page = st.radio("Navigation", PAGES, index=0, label_visibility="collapsed")
    st.divider()
    # Quick Bio-Score
    bio_sidebar = api_get("/api/bio-score")
    if isinstance(bio_sidebar, dict) and "score" in bio_sidebar:
        sc = bio_sidebar["score"]
        ph = bio_sidebar.get("phase", "?")
        st.metric("Bio-Score", f"{sc:.0f}/100")
        st.caption(f"Phase: {ph}")
        cns = bio_sidebar.get("cns_load", 0)
        if cns > 0:
            color = "normal" if cns < 1.5 else "inverse"
            st.metric(
                "ZNS-Belastung",
                f"{cns:.1f}",
                delta="OK" if cns < 1.5 else "Erhöht!",
                delta_color=color,
            )
            st.caption(
                "Summe aller aktiven Substanz-Level. "
                "Unter 1.0 = entspannt, 1.0–1.5 = normal, über 1.5 = hohe Belastung."
            )
    # Quick water status
    ws = api_get("/api/water/status")
    if isinstance(ws, dict) and "intake_ml" in ws:
        goal = ws.get("goal", {}).get("goal_ml", 3200)
        intake = ws.get("intake_ml", 0)
        pct = int(intake / goal * 100) if goal > 0 else 0
        st.metric("Wasser", f"{intake} / {goal} ml", delta=f"{pct}%")

current_page = PAGE_MAP.get(sidebar_page, "main")


# =========================================================
# PAGE: Main Logging (default)
# =========================================================
if current_page == "main":
    # --- Log Reminder ---
    reminder = api_get("/api/log-reminder")
    if isinstance(reminder, dict) and reminder.get("next_due"):
        next_due = reminder["next_due"]
        logs_done = reminder.get("logs_today", 0)
        target_logs = reminder.get("target_logs", 5)

        progress = min(logs_done / max(target_logs, 1), 1.0)
        st.progress(progress, text=f"Logs: {logs_done}/{target_logs}")

        if next_due["status"] == "due":
            st.warning(f"Log fällig: {next_due['label']} ({next_due['target_time']})")
        else:
            st.info(f"Nächster Log: {next_due['label']} um {next_due['target_time']}")

    # ---- SECTION 1: Einnahme ----
    st.subheader("1 — Einnahme")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Elvanse 40mg", use_container_width=True, type="primary"):
            r = api_post("/api/intake", {"substance": "elvanse", "dose_mg": 40})
            if r.get("status") == "ok":
                st.success("Elvanse geloggt")
                st.rerun()
    with b2:
        if st.button("Lamate 76mg", use_container_width=True, type="primary"):
            r = api_post("/api/intake", {"substance": "mate", "dose_mg": 76})
            if r.get("status") == "ok":
                st.success("Lamate geloggt")
                st.rerun()

    b3, b4 = st.columns(2)
    with b3:
        if st.button("Lamate x2", use_container_width=True):
            r = api_post("/api/intake", {"substance": "mate", "dose_mg": 152})
            if r.get("status") == "ok":
                st.success("Doppel-Lamate geloggt")
                st.rerun()
    with b4:
        if st.button("Medikinet 10mg", use_container_width=True):
            r = api_post("/api/intake", {"substance": "medikinet", "dose_mg": 10})
            if r.get("status") == "ok":
                st.success("Medikinet geloggt")
                st.rerun()

    with st.expander("Nachtragen / Andere"):
        hc1, hc2 = st.columns(2)
        with hc1:
            hist_sub = st.selectbox("Substanz", ["elvanse", "mate", "medikinet", "medikinet_retard", "other"], key="hsub")
        with hc2:
            dmap = {"elvanse": 40.0, "mate": 76.0, "medikinet": 10.0, "medikinet_retard": 30.0, "other": 0.0}
            hist_dose = st.number_input("mg", min_value=0.0, step=10.0, value=dmap.get(hist_sub, 0.0), key="hdose")
        dc1, dc2 = st.columns(2)
        with dc1:
            hdate = st.date_input("Datum", value=datetime.now().date(), key="hdate")
        with dc2:
            htime = st.time_input("Uhrzeit", value=datetime.now().time().replace(second=0, microsecond=0), key="htime")
        if st.button("Nachtragen", type="primary", use_container_width=True):
            ts = datetime.combine(hdate, htime).isoformat()
            r = api_post("/api/intake", {"substance": hist_sub, "dose_mg": hist_dose or None, "timestamp": ts})
            if r.get("status") == "ok":
                st.success("Nachgetragen")
                st.rerun()

    # ---- SECTION 2: Wie fühlst du dich? ----
    st.divider()
    st.subheader("2 — Wie fühlst du dich?")

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        focus = st.slider("Fokus", 1, 10, 5, key="f")
    with fc2:
        mood = st.slider("Laune", 1, 10, 5, key="m")
    with fc3:
        energy = st.slider("Energie", 1, 10, 5, key="e")

    fc4, fc5 = st.columns(2)
    with fc4:
        appetite = st.slider("Appetit", 1, 10, 5, key="a")
    with fc5:
        inner_unrest = st.slider("Innere Unruhe", 1, 10, 1, key="u")

    tag_options = [
        "migräne", "kopfschmerzen", "übelkeit",
        "müde", "unruhig", "motiviert",
        "klar", "brain-fog", "angespannt", "entspannt",
        "kreativ", "gereizt", "produktiv", "abgelenkt",
    ]
    tags = st.multiselect("Tags (optional)", tag_options, key="tags")

    if st.button("Bewertung speichern", type="primary", use_container_width=True):
        r = api_post("/api/log", {
            "focus": focus, "mood": mood, "energy": energy,
            "appetite": appetite, "inner_unrest": inner_unrest,
            "tags": tags,
        })
        if r.get("status") == "ok":
            st.success("Gespeichert")
            st.rerun()

    # ---- SECTION 3: Essen ----
    st.divider()
    st.subheader("3 — Essen")
    meal_notes = st.text_input("Was? (optional)", key="mnotes", placeholder="Pizza, Salat...")
    ec1, ec2 = st.columns(2)
    with ec1:
        if st.button("Mittagessen", use_container_width=True):
            r = api_post("/api/meal", {"meal_type": "mittagessen", "notes": meal_notes})
            if r.get("status") == "ok":
                st.success("Mittagessen geloggt")
                st.rerun()
        if st.button("Frühstück", use_container_width=True):
            r = api_post("/api/meal", {"meal_type": "fruehstueck", "notes": meal_notes})
            if r.get("status") == "ok":
                st.success("Frühstück geloggt")
                st.rerun()
    with ec2:
        if st.button("Abendessen", use_container_width=True):
            r = api_post("/api/meal", {"meal_type": "abendessen", "notes": meal_notes})
            if r.get("status") == "ok":
                st.success("Abendessen geloggt")
                st.rerun()
        if st.button("Snack", use_container_width=True):
            r = api_post("/api/meal", {"meal_type": "snack", "notes": meal_notes})
            if r.get("status") == "ok":
                st.success("Snack geloggt")
                st.rerun()

    # ---- Heutiger Verlauf (kompakt) ----
    st.divider()
    st.subheader("Heute")
    tc1, tc2 = st.columns(2)
    with tc1:
        st.caption("Einnahmen")
        intakes = api_get("/api/intake", {"today": True})
        if isinstance(intakes, list) and intakes:
            for i in intakes:
                ts = i.get("timestamp", "")[11:16]
                sub = i.get("substance", "?")
                dose = i.get("dose_mg", "")
                lbl = {"elvanse": "ELV", "mate": "MAT", "medikinet": "MED", "medikinet_retard": "MR"}.get(sub, sub[:3].upper())
                iid = i.get("id")
                ec, dc = st.columns([5, 1])
                with ec:
                    st.text(f"{ts} [{lbl}] {dose}mg")
                with dc:
                    if st.button("X", key=f"di_{iid}"):
                        api_delete(f"/api/intake/{iid}")
                        st.rerun()
        else:
            st.caption("—")

    with tc2:
        st.caption("Logs")
        logs = api_get("/api/log", {"today": True})
        if isinstance(logs, list) and logs:
            for lg in logs:
                ts = lg.get("timestamp", "")[11:16]
                lid = lg.get("id")
                f_val = lg.get("focus", "?")
                m_val = lg.get("mood", "?")
                e_val = lg.get("energy", "?")
                a_val = lg.get("appetite", "-")
                u_val = lg.get("inner_unrest", "-")
                ec, dc = st.columns([5, 1])
                with ec:
                    st.text(f"{ts} F:{f_val} M:{m_val} E:{e_val} A:{a_val} U:{u_val}")
                with dc:
                    if st.button("X", key=f"dl_{lid}"):
                        api_delete(f"/api/log/{lid}")
                        st.rerun()
        else:
            st.caption("—")

    # Meals today
    meals = api_get("/api/meal", {"today": "true"})
    if isinstance(meals, list) and meals:
        st.caption("Mahlzeiten")
        for meal in meals:
            ts = meal.get("timestamp", "")[11:16]
            mt = meal.get("meal_type", "?")
            mn = meal.get("notes", "")
            mid = meal.get("id")
            ns = f" ({mn})" if mn else ""
            ec, dc = st.columns([5, 1])
            with ec:
                st.text(f"{ts} {mt}{ns}")
            with dc:
                if st.button("X", key=f"dm_{mid}"):
                    api_delete(f"/api/meal/{mid}")
                    st.rerun()


# =========================================================
# PAGE: Hydration (NEU)
# =========================================================
elif current_page == "hydration":
    st.header("Hydration")

    # --- Fetch all water data ---
    ws = api_get("/api/water/status")

    if isinstance(ws, dict) and "goal" in ws:
        goal_data = ws["goal"]
        goal_ml = goal_data.get("goal_ml", 3200)
        intake_ml = ws.get("intake_ml", 0)
        assessment = ws.get("assessment", {})
        velocity = ws.get("velocity", {})
        dehydration = ws.get("dehydration", {})

        # ---- Fortschritt ----
        pct = int(intake_ml / goal_ml * 100) if goal_ml > 0 else 0
        remaining = max(0, goal_ml - intake_ml)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Getrunken", f"{intake_ml} ml")
        m2.metric("Tagesziel", f"{goal_ml} ml")
        m3.metric("Fortschritt", f"{pct}%")
        m4.metric("Verbleibend", f"{remaining} ml")

        st.progress(min(pct / 100.0, 1.0), text=f"{intake_ml} / {goal_ml} ml ({pct}%)")

        # ---- Tagesziel-Aufschlüsselung ----
        with st.expander("Tagesziel-Berechnung"):
            base = goal_data.get("base_ml", 0)
            drug = goal_data.get("drug_modifier_ml", 0)
            fasting = goal_data.get("fasting_modifier_ml", 0)
            activity = goal_data.get("activity_modifier_ml", 0)
            weight = goal_data.get("weight_kg", 96)
            steps = goal_data.get("steps", 0)

            st.markdown(f"""
| Komponente | Wert |
|---|---|
| **Basis** ({weight:.1f} kg × 33.3 ml/kg) | {base} ml |
| **Elvanse** (+110 ml REE-Steigerung) | {'+' + str(drug) if drug > 0 else '—'} ml |
| **OMAD-Fasten** (+500 ml Feuchtigkeitsdefizit) | {'+' + str(fasting) if fasting > 0 else '—'} ml |
| **Aktivität** ({steps} Schritte, +60 ml/1k über 4000) | {'+' + str(activity) if activity > 0 else '—'} ml |
| **Gesamt** | **{goal_ml} ml** |
""")

        # ---- Coaching / Status ----
        status = assessment.get("status", "on_track")
        msg = assessment.get("message", "")
        priority = assessment.get("priority", "none")

        if msg:
            if priority in ("critical", "high"):
                st.error(msg)
            elif priority == "normal":
                st.warning(msg)
            else:
                st.info(msg)

        # ---- Sicherheits-Warnungen ----
        if velocity.get("alert"):
            st.error(velocity.get("message", "Trinkgeschwindigkeit zu hoch!"))
        else:
            last60 = velocity.get("last_60min_ml", 0)
            if last60 > 0:
                max_h = velocity.get("max_hourly_ml", 800)
                vel_pct = int(last60 / max_h * 100)
                st.caption(f"Letzte 60 Min: {last60} ml / {max_h} ml Nierenlimit ({vel_pct}%)")

        if dehydration.get("alert"):
            st.error(dehydration.get("message", "Dehydrierungs-Warnung!"))

        # ---- Pacing-Monitor (Soll vs. Ist + Adaptive Catch-Up) ----
        st.divider()
        st.subheader("Pacing-Monitor")
        st.caption(
            "Soll-Kurve (blau gestrichelt) = ideales Pacing. "
            "Adaptive Kurve (orange) = realistischer Catch-Up-Plan ab jetzt. "
            "Grün = tatsächlich getrunken."
        )

        now = datetime.now()
        current_hour = now.hour + now.minute / 60.0
        wake_h = 7.0
        sleep_h = 23.0

        # Fetch instruction from API — contains expected_curve, adaptive_curve
        instr = api_get("/api/water/instruction", {
            "current_intake": intake_ml,
            "daily_goal": goal_ml,
        })

        # ── Expected (ideal) curve — from API server data ──
        # Use server's pre-computed expected_curve so dashboard always matches
        # the engine exactly. Fallback to t^0.65 local computation if offline.
        hours_range: list[float] = []
        expected_curve: list[int] = []
        hcurve = instr.get("hydration_curve") if isinstance(instr, dict) else None
        if hcurve and hcurve.get("expected_curve"):
            for pt in hcurve["expected_curve"]:
                hours_range.append(pt["hour"])
                expected_curve.append(pt["ml"])
        else:
            # Offline fallback — t^0.65 is visibly curved (not t^0.85 which looks linear)
            hours_range = [h * 0.5 for h in range(int(wake_h * 2), int(sleep_h * 2) + 1)]
            for h in hours_range:
                if h <= wake_h:
                    expected_curve.append(0)
                elif h >= sleep_h:
                    expected_curve.append(goal_ml)
                else:
                    t = (h - wake_h) / (sleep_h - wake_h)
                    expected_curve.append(int(goal_ml * (t ** 0.65)))

        fig_pace = go.Figure()

        # Expected pacing curve (dashed blue)
        fig_pace.add_trace(go.Scatter(
            x=hours_range,
            y=expected_curve,
            mode="lines",
            name="Soll (Ideal)",
            line=dict(color="#4FC3F7", width=2, dash="dash"),
            fill="tozeroy",
            fillcolor="rgba(79, 195, 247, 0.05)",
        ))

        # Actual intake events as cumulative step line
        events = api_get("/api/water/intake", {"today": "true"})
        if isinstance(events, list) and events:
            cumulative = 0
            event_hours = [wake_h]
            event_totals = [0]
            for ev in sorted(events, key=lambda e: e.get("timestamp", "")):
                ts = ev.get("timestamp", "")
                try:
                    t_ev = datetime.fromisoformat(ts)
                    h = t_ev.hour + t_ev.minute / 60.0
                except (ValueError, TypeError):
                    continue
                cumulative += ev.get("amount_ml", 0)
                event_hours.append(h)
                event_totals.append(cumulative)
            # Extend to current time
            event_hours.append(current_hour)
            event_totals.append(cumulative)

            fig_pace.add_trace(go.Scatter(
                x=event_hours,
                y=event_totals,
                mode="lines+markers",
                name="Ist (Getrunken)",
                line=dict(color="#4CAF50", width=3, shape="hv"),
                marker=dict(size=6),
            ))

        # Adaptive catch-up curve from API
        if isinstance(instr, dict) and instr.get("adaptive_curve"):
            ac = instr["adaptive_curve"]
            ac_curve = ac.get("adaptive_curve", [])
            if ac_curve:
                ac_hours = [p["hour"] for p in ac_curve]
                ac_mls = [p["ml"] for p in ac_curve]
                fig_pace.add_trace(go.Scatter(
                    x=ac_hours,
                    y=ac_mls,
                    mode="lines",
                    name="Catch-Up Plan",
                    line=dict(color="#FF9800", width=3),
                ))

            # Show catch-up rate info
            rate = ac.get("catch_up_rate_ml_h", 0)
            ac_status = ac.get("status", "on_track")
            deficit = ac.get("deficit_ml", 0)
            remaining = ac.get("remaining_ml", 0)
            remaining_h = ac.get("remaining_hours", 0)
            if rate > 0 and ac_status != "goal_reached":
                status_emoji = {"ahead": "++", "on_track": "OK", "behind": "!", "critical": "!!"}
                st.info(
                    f"[{status_emoji.get(ac_status, '?')}] "
                    f"Catch-Up-Rate: {rate:.0f} ml/h | "
                    f"Noch {remaining} ml in {remaining_h:.1f}h | "
                    f"Defizit: {deficit} ml"
                )

        # Current time marker
        fig_pace.add_vline(
            x=current_hour,
            line=dict(color="#F44336", width=2),
            annotation_text="Jetzt",
            annotation_font=dict(color="#F44336"),
        )

        # Goal line
        fig_pace.add_hline(
            y=goal_ml,
            line=dict(color="#FF9800", width=1, dash="dot"),
            annotation_text=f"Ziel: {goal_ml} ml",
            annotation_font=dict(color="#FF9800"),
        )

        fig_pace.update_layout(
            title="Trink-Pacing (Ideal vs. Catch-Up vs. Ist)",
            xaxis_title="Uhrzeit",
            yaxis_title="ml (kumuliert)",
            xaxis=dict(
                tickmode="array",
                tickvals=list(range(7, 24)),
                ticktext=[f"{h}:00" for h in range(7, 24)],
            ),
        )
        mobile_chart(fig_pace, height=400)

        # ---- Goal History (Tagesbedarf-Veränderung) ----
        st.divider()
        st.subheader("Tagesbedarf-Verlauf")
        st.caption("Wie sich dein Tagesbedarf über die letzten 7 Tage verändert hat.")
        goal_hist = api_get("/api/water/goal/history", {"days": 7})
        if isinstance(goal_hist, list) and goal_hist:
            gdf = pd.DataFrame(goal_hist)
            fig_goal = go.Figure()

            fig_goal.add_trace(go.Scatter(
                x=gdf["date"], y=gdf["goal_ml"],
                mode="lines+markers+text",
                name="Tagesziel",
                line=dict(color="#4FC3F7", width=3),
                marker=dict(size=8),
                text=[f"{g}" for g in gdf["goal_ml"]],
                textposition="top center",
                textfont=dict(size=9),
            ))

            # Breakdown stacked area
            if "base_ml" in gdf.columns:
                fig_goal.add_trace(go.Bar(
                    x=gdf["date"], y=gdf.get("base_ml", []),
                    name="Basis", marker_color="rgba(79,195,247,0.4)",
                ))
            if "drug_mod_ml" in gdf.columns:
                fig_goal.add_trace(go.Bar(
                    x=gdf["date"], y=gdf.get("drug_mod_ml", []),
                    name="Elvanse", marker_color="rgba(33,150,243,0.5)",
                ))
            if "fasting_mod_ml" in gdf.columns:
                fig_goal.add_trace(go.Bar(
                    x=gdf["date"], y=gdf.get("fasting_mod_ml", []),
                    name="OMAD", marker_color="rgba(255,152,0,0.5)",
                ))
            if "activity_mod_ml" in gdf.columns:
                fig_goal.add_trace(go.Bar(
                    x=gdf["date"], y=gdf.get("activity_mod_ml", []),
                    name="Aktivität", marker_color="rgba(76,175,80,0.5)",
                ))

            fig_goal.update_layout(
                title="Tagesbedarf (7 Tage)",
                yaxis_title="ml",
                barmode="stack",
            )
            mobile_chart(fig_goal, height=320)
        else:
            st.caption("Noch keine Ziel-Historie vorhanden.")

        # ---- Quick-Add Wasser ----
        st.divider()
        st.subheader("Wasser loggen")
        wa1, wa2, wa3, wa4 = st.columns(4)
        with wa1:
            if st.button("100 ml", use_container_width=True):
                api_post("/api/water/intake", {"amount_ml": 100})
                st.rerun()
        with wa2:
            if st.button("250 ml", use_container_width=True, type="primary"):
                api_post("/api/water/intake", {"amount_ml": 250})
                st.rerun()
        with wa3:
            if st.button("500 ml", use_container_width=True, type="primary"):
                api_post("/api/water/intake", {"amount_ml": 500})
                st.rerun()
        with wa4:
            custom_ml = st.number_input("ml", min_value=25, max_value=1500, value=330, step=25, key="wc_ml", label_visibility="collapsed")
            if st.button("Log", use_container_width=True, key="wc_log"):
                api_post("/api/water/intake", {"amount_ml": custom_ml})
                st.rerun()

        # ---- Historical water entry ----
        with st.expander("Wasser nachtragen (historisch)"):
            hw1, hw2 = st.columns(2)
            with hw1:
                hist_w_date = st.date_input("Datum", value=datetime.now().date(), key="hw_date")
            with hw2:
                hist_w_time = st.time_input("Uhrzeit", value=datetime.now().time().replace(second=0, microsecond=0), key="hw_time")
            hw3, hw4 = st.columns(2)
            with hw3:
                hist_w_ml = st.number_input("Menge (ml)", min_value=25, max_value=2000, value=250, step=25, key="hw_ml")
            with hw4:
                hist_w_src = st.selectbox("Quelle", ["manual", "watch", "ha"], key="hw_src")
            hist_w_notes = st.text_input("Notizen (optional)", key="hw_notes", placeholder="z.B. Tee, Suppe...")
            if st.button("Nachtragen", type="primary", use_container_width=True, key="hw_submit"):
                ts = datetime.combine(hist_w_date, hist_w_time).isoformat()
                r = api_post("/api/water/intake", {
                    "amount_ml": hist_w_ml,
                    "source": hist_w_src,
                    "notes": hist_w_notes,
                    "timestamp": ts,
                })
                if r.get("status") == "ok":
                    st.success(f"{hist_w_ml} ml nachgetragen ({hist_w_date} {hist_w_time.strftime('%H:%M')})")
                    st.rerun()

        # ---- Reset ----
        with st.expander("Wasser zurücksetzen"):
            st.warning("Löscht **alle** heutigen Wasser-Einträge und setzt auf 0 ml zurück.")
            if st.button("Heute zurücksetzen", type="primary", key="water_reset"):
                api_post("/api/water/reset", {})
                st.success("Wasser auf 0 ml zurückgesetzt!")
                st.rerun()

        # ---- Heutige Einträge ----
        if isinstance(events, list) and events:
            with st.expander(f"Heutige Einträge ({len(events)})"):
                for ev in reversed(events):
                    ts = ev.get("timestamp", "")[11:16]
                    ml = ev.get("amount_ml", 0)
                    src = ev.get("source", "")
                    eid = ev.get("id")
                    ec, dc = st.columns([5, 1])
                    with ec:
                        st.text(f"{ts}  +{ml} ml  ({src})")
                    with dc:
                        if st.button("X", key=f"dw_{eid}"):
                            api_delete(f"/api/water/intake/{eid}")
                            st.rerun()

        # ---- Gewicht ----
        st.divider()
        st.subheader("Gewicht")
        weight_data = api_get("/api/weight/latest")
        current_weight = 96.0
        weight_source = "config"
        if isinstance(weight_data, dict) and weight_data.get("found"):
            current_weight = float(weight_data.get("weight_kg", 96.0))
            weight_source = weight_data.get("source", "?")
            wts = weight_data.get("timestamp", "")
            wts_display = wts[0:16].replace("T", " ") if len(wts) > 16 else wts
            st.metric("Aktuelles Gewicht", f"{current_weight:.1f} kg")
            st.caption(f"Quelle: {weight_source} | Zuletzt: {wts_display}")
        else:
            st.metric("Aktuelles Gewicht", f"{current_weight:.1f} kg")
            st.caption("Quelle: Standardwert (kein Gewicht in DB)")

        # Weight chart (last 30 days)
        weight_history = api_get("/api/weight", {"days": 30})
        if isinstance(weight_history, dict) and weight_history.get("history"):
            wh = weight_history["history"]
            if len(wh) > 1:
                wdf = pd.DataFrame(wh)
                wdf["time"] = pd.to_datetime(wdf["timestamp"])
                fig_w = go.Figure()
                fig_w.add_trace(go.Scatter(
                    x=wdf["time"], y=wdf["weight_kg"],
                    mode="lines+markers",
                    line=dict(color="#AB47BC", width=2),
                    marker=dict(size=5),
                    name="Gewicht",
                ))
                fig_w.update_layout(
                    title="Gewichtsverlauf (30 Tage)",
                    yaxis_title="kg",
                    xaxis_title="",
                )
                mobile_chart(fig_w, height=250)

        wc1, wc2 = st.columns(2)
        with wc1:
            new_w = st.number_input("Neues Gewicht (kg)", min_value=50.0, max_value=200.0, value=current_weight, step=0.1, key="nw")
        with wc2:
            st.write("")
            st.write("")
            if st.button("Gewicht speichern", use_container_width=True):
                api_post("/api/weight", {"weight_kg": new_w})
                st.success(f"Gewicht {new_w} kg gespeichert")
                st.rerun()
    else:
        st.warning("Keine Wasser-Daten verfügbar. Ist das Bio-Dashboard API erreichbar?")


# =========================================================
# PAGE: Kurven & Timeline
# =========================================================
elif current_page == "kurven":
    st.header("Kurven & Timeline")

    date = st.date_input("Datum", value=datetime.now().date(), key="tl_date")
    date_str = date.isoformat()

    curve_data = api_get("/api/bio-score/curve", {"date": date_str, "interval": 15})

    if isinstance(curve_data, dict) and "points" in curve_data:
        points = curve_data["points"]
        df = pd.DataFrame(points)

        if not df.empty:
            df["time"] = pd.to_datetime(df["timestamp"])
            is_today = date == datetime.now().date()

            # -- Bio-Score + Substanz-Kurven --
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["time"], y=df["score"],
                mode="lines", name="Bio-Score",
                line=dict(color="#4CAF50", width=3),
                fill="tozeroy", fillcolor="rgba(76,175,80,0.08)",
            ))
            fig.add_trace(go.Scatter(
                x=df["time"], y=df["circadian"],
                mode="lines", name="Circadian",
                line=dict(color="#9E9E9E", width=1, dash="dot"),
            ))
            fig.add_trace(go.Scatter(
                x=df["time"], y=df["elvanse_boost"],
                mode="lines", name="Elvanse",
                line=dict(color="#2196F3", width=2),
            ))
            if "medikinet_boost" in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["time"], y=df["medikinet_boost"],
                    mode="lines", name="Medikinet",
                    line=dict(color="#AB47BC", width=2),
                ))
            fig.add_trace(go.Scatter(
                x=df["time"], y=df["caffeine_boost"],
                mode="lines", name="Koffein",
                line=dict(color="#FF9800", width=2),
            ))

            def _vmark(fig_ref, x, color, dash, w, text, anchor="left"):
                fig_ref.add_shape(
                    type="line", x0=x, x1=x, y0=0, y1=1,
                    yref="paper", line=dict(color=color, width=w, dash=dash),
                )
                fig_ref.add_annotation(
                    x=x, y=1, yref="paper", text=text,
                    showarrow=False, font=dict(color=color, size=9),
                    xanchor=anchor, yanchor="bottom",
                )

            if is_today:
                _vmark(fig, datetime.now(), "#F44336", "solid", 2, "Jetzt")

            # Intake markers
            day_intakes = api_get("/api/intake", {"start": f"{date_str}T00:00:00", "end": f"{date_str}T23:59:59"})
            if isinstance(day_intakes, list):
                cmap = {"elvanse": "#2196F3", "mate": "#FF9800", "medikinet": "#AB47BC", "medikinet_retard": "#7B1FA2"}
                lmap = {"elvanse": "ELV", "mate": "MAT", "medikinet": "MED", "medikinet_retard": "MR"}
                for itk in day_intakes:
                    t = itk["timestamp"]
                    s = itk.get("substance", "?")
                    d = itk.get("dose_mg", "")
                    _vmark(fig, t, cmap.get(s, "#9C27B0"), "dash", 1, f"{lmap.get(s, s[:3])} {d}mg")

            # Fokus diamonds
            day_logs = api_get("/api/log", {"start": f"{date_str}T00:00:00", "end": f"{date_str}T23:59:59"})
            if isinstance(day_logs, list):
                for lg in day_logs:
                    t = pd.to_datetime(lg["timestamp"])
                    foc = lg.get("focus", 5)
                    fig.add_trace(go.Scatter(
                        x=[t], y=[foc * 10], mode="markers",
                        marker=dict(size=12, color="#E91E63", symbol="diamond"),
                        showlegend=False, hovertext=f"Fokus: {foc}/10",
                    ))

            fig.update_layout(
                title=f"Tagesverlauf — {date_str}",
                xaxis_title="Uhrzeit", yaxis_title="Score / Boost",
                yaxis=dict(range=[0, 105]),
            )
            mobile_chart(fig, height=420)

            # -- Substanz-Level + ZNS-Last --
            st.subheader("Substanz-Level & ZNS-Belastung")
            st.caption(
                "Normalisierte Wirkstoff-Level (0–1). "
                "ZNS-Belastung = Summe aller aktiven Substanzen. "
                "Über 1.5 = erhöhte ZNS-Belastung (Unruhe, Herzrasen möglich)."
            )
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=df["time"], y=df["elvanse_level"],
                mode="lines", name="Elvanse",
                line=dict(color="#2196F3", width=2),
            ))
            if "medikinet_level" in df.columns:
                fig2.add_trace(go.Scatter(
                    x=df["time"], y=df["medikinet_level"],
                    mode="lines", name="Medikinet",
                    line=dict(color="#AB47BC", width=2),
                ))
            fig2.add_trace(go.Scatter(
                x=df["time"], y=df["caffeine_level"],
                mode="lines", name="Koffein",
                line=dict(color="#FF9800", width=2),
            ))
            if "cns_load" in df.columns:
                fig2.add_trace(go.Scatter(
                    x=df["time"], y=df["cns_load"],
                    mode="lines", name="ZNS-Belastung",
                    line=dict(color="#F44336", width=3, dash="dash"),
                    fill="tozeroy", fillcolor="rgba(244,67,54,0.06)",
                ))
                fig2.add_hline(
                    y=1.5, line=dict(color="#FFC107", width=1, dash="dot"),
                    annotation_text="Warnschwelle 1.5",
                )

            if is_today:
                _vmark(fig2, datetime.now(), "#F44336", "solid", 1, "Jetzt")

            fig2.update_layout(
                xaxis_title="Uhrzeit", yaxis_title="Level (0–1) / ZNS",
                yaxis=dict(range=[0, 2.5]),
            )
            mobile_chart(fig2, height=350)
        else:
            st.info("Keine Daten")

    # PK-Erklärung (aktualisiert für 3-Stage Cascade)
    st.divider()
    st.subheader("So funktioniert das Modell")
    st.markdown("""
**Elvanse (Lisdexamfetamin)** — Drei-Stufen-Kaskadenmodell:

1. **GI-Absorption** — Aufnahme über PEPT1-Transporter im Darm
2. **Erythrozyten-Hydrolyse** — Enzymatische Spaltung zu d-Amphetamin im Blut
3. **Elimination** — Renale Ausscheidung von d-Amphetamin

Jede Stufe hat eine eigene Geschwindigkeitskonstante (k_abs, k_hyd, k_e).
Die Gesamtlösung ist eine 3-Kompartiment-Kaskade:

> A(t) = G₀ · k_abs · k_hyd · Σ[ e^(−rᵢ·t) / Π(rⱼ − rᵢ) ]

Das ergibt eine breitere, flachere Kurve als ein einfaches Bateman-Modell —
typisch für Elvanse mit dem verzögerten Prodrug-Mechanismus (Tmax ≈ 3.8h statt 1–2h).

---

**Medikinet, Koffein, Co-Dafalgan** — Klassische Bateman-Funktion:

> C(t) = (ka / (ka − ke)) · (e^(−ke·t) − e^(−ka·t))

Normalisiert auf Peak = 1.0. Bei Mehrfacheinnahmen: lineare Superposition.

---

**Allometrische Skalierung** (Gewicht → 70 kg Referenz):
- Cmax\_user = Cmax\_ref × (70 / Gewicht) — Verteilungsvolumen ∝ Gewicht
- Clearance = CL\_ref × (Gewicht / 70)^0.75

**ZNS-Belastung** = Summe aller normalisierten Substanz-Level:
- < 1.0: Entspannt
- 1.0–1.5: Normaler Arbeitsbereich
- \> 1.5: Erhöhte Belastung — Unruhe, schneller Puls möglich
""")

    pk_data = {
        "Elvanse (Cascade)": {"Modell": "3-Stufen-Kaskade", "k_abs": "0.78 h⁻¹", "k_hyd": "0.78 h⁻¹", "k_e": "0.088 h⁻¹", "Tmax": "≈3.8h", "t½": "≈10h"},
        "Medikinet IR": {"Modell": "Bateman", "ka": "1.72 h⁻¹", "k_hyd": "—", "k_e": "0.28 h⁻¹", "Tmax": "≈1.5h", "t½": "≈2.5h"},
        "Med. retard": {"Modell": "Bateman (nüchtern)", "ka": "1.2 h⁻¹", "k_hyd": "—", "k_e": "0.28 h⁻¹", "Tmax": "≈2h", "t½": "≈2.5h"},
        "Koffein (Mate)": {"Modell": "Bateman", "ka": "2.5 h⁻¹", "k_hyd": "—", "k_e": "0.16 h⁻¹", "Tmax": "≈0.75h", "t½": "≈4.3h"},
    }
    st.dataframe(pd.DataFrame(pk_data).T, use_container_width=True)


# =========================================================
# PAGE: Vitals & Health
# =========================================================
elif current_page == "vitals":
    st.header("Vitals & Health")

    # Latest snapshot
    latest_h = api_get("/api/health/latest")
    if isinstance(latest_h, dict) and latest_h.get("found"):
        v1, v2, v3, v4 = st.columns(4)
        hr = latest_h.get("heart_rate")
        rhr = latest_h.get("resting_hr")
        hrv = latest_h.get("hrv")
        sleep_dur = latest_h.get("sleep_duration")
        spo2 = latest_h.get("spo2")
        steps_val = latest_h.get("steps")
        cals = latest_h.get("calories")
        src = latest_h.get("source", "?")

        if hr:
            v1.metric("HR", f"{hr:.0f} bpm")
        if rhr:
            v2.metric("Ruhe-HR", f"{rhr:.0f} bpm")
        if hrv:
            v3.metric("HRV", f"{hrv:.0f} ms")
        if sleep_dur:
            v4.metric("Schlaf", f"{sleep_dur / 60:.1f}h")

        v5, v6, v7, _ = st.columns(4)
        if spo2:
            v5.metric("SpO2", f"{spo2:.0f}%")
        if steps_val:
            v6.metric("Schritte", f"{int(steps_val)}")
        if cals:
            v7.metric("Kalorien", f"{cals:.0f} kcal")

        ts_str = latest_h.get("timestamp", "")
        src_label = {"ha": "Home Assistant", "watch": "Huawei Watch", "manual": "Manuell"}.get(src, src)
        st.caption(f"Aktualisiert: {ts_str[11:16] if len(ts_str) > 16 else ts_str} | Quelle: {src_label}")
    else:
        st.info("Noch keine Daten")

    # Day charts
    st.divider()
    date = st.date_input("Tag", value=datetime.now().date(), key="v_date")
    ds = date.isoformat()
    health = api_get("/api/health", {"start": f"{ds}T00:00:00", "end": f"{ds}T23:59:59"})
    if isinstance(health, list) and health:
        hdf = pd.DataFrame(health)
        hdf["time"] = pd.to_datetime(hdf["timestamp"])
        has_source = "source" in hdf.columns

        # Source summary
        if has_source:
            src_counts = hdf["source"].value_counts().to_dict()
            src_parts = []
            src_names = {"ha": "Home Assistant", "watch": "Huawei Watch", "manual": "Manuell"}
            for s, c in sorted(src_counts.items()):
                src_parts.append(f"{src_names.get(s, s)}: {c}")
            st.caption(f"Datenpunkte: {len(hdf)} ({', '.join(src_parts)})")

        # Color map for sources
        SRC_COLORS = {"ha": "#F44336", "watch": "#00BCD4", "manual": "#FF9800"}

        h1, h2 = st.columns(2)
        with h1:
            if "heart_rate" in hdf.columns and hdf["heart_rate"].notna().any():
                fig_hr = go.Figure()
                if has_source:
                    for src_name, grp in hdf[hdf["heart_rate"].notna()].groupby("source"):
                        label = {"ha": "HR (HA)", "watch": "HR (Watch)", "manual": "HR (Manuell)"}.get(str(src_name), f"HR ({src_name})")
                        fig_hr.add_trace(go.Scatter(
                            x=grp["time"], y=grp["heart_rate"],
                            mode="lines+markers",
                            name=label,
                            line=dict(color=SRC_COLORS.get(str(src_name), "#F44336")),
                            marker=dict(size=4),
                        ))
                else:
                    fig_hr.add_trace(go.Scatter(
                        x=hdf["time"], y=hdf["heart_rate"],
                        mode="lines+markers", line=dict(color="#F44336"),
                    ))
                fig_hr.update_layout(title="Herzfrequenz", yaxis_title="bpm")
                mobile_chart(fig_hr, height=280)
        with h2:
            if "hrv" in hdf.columns and hdf["hrv"].notna().any():
                fig_hrv = go.Figure()
                fig_hrv.add_trace(go.Scatter(
                    x=hdf["time"], y=hdf["hrv"],
                    mode="lines+markers", line=dict(color="#3F51B5"),
                ))
                fig_hrv.update_layout(title="HRV", yaxis_title="ms")
                mobile_chart(fig_hrv, height=280)

        # Resting HR comparison (watch vs HA)
        if "resting_hr" in hdf.columns and hdf["resting_hr"].notna().any() and has_source:
            rhr_df = hdf[hdf["resting_hr"].notna()]
            if len(rhr_df["source"].unique()) > 1:
                fig_rhr = go.Figure()
                for src_name, grp in rhr_df.groupby("source"):
                    label = {"ha": "Ruhe-HR (HA)", "watch": "Ruhe-HR (Watch)"}.get(str(src_name), f"Ruhe-HR ({src_name})")
                    fig_rhr.add_trace(go.Scatter(
                        x=grp["time"], y=grp["resting_hr"],
                        mode="lines+markers",
                        name=label,
                        line=dict(color=SRC_COLORS.get(str(src_name), "#9C27B0")),
                        marker=dict(size=4),
                    ))
                fig_rhr.update_layout(title="Ruhe-Herzfrequenz (Vergleich)", yaxis_title="bpm")
                mobile_chart(fig_rhr, height=250)

        if "steps" in hdf.columns and hdf["steps"].notna().any():
            # Show steps as line graph; drop midnight carryover artefacts by
            # only keeping rows where steps changed from the previous snapshot
            steps_df = hdf[hdf["steps"].notna()].copy()
            if not steps_df.empty:
                fig_steps = go.Figure()
                fig_steps.add_trace(go.Scatter(
                    x=steps_df["time"], y=steps_df["steps"],
                    mode="lines+markers",
                    line=dict(color="#4CAF50", width=2),
                    marker=dict(size=4),
                    fill="tozeroy",
                    fillcolor="rgba(76,175,80,0.08)",
                    name="Schritte",
                ))
                fig_steps.update_layout(title="Schritte", yaxis_title="Steps")
                mobile_chart(fig_steps, height=250)
    else:
        st.info("Keine Daten für diesen Tag")


# =========================================================
# PAGE: Persönliches Modell
# =========================================================
elif current_page == "modell":
    st.header("Persönliches Modell")
    st.caption(
        "Analysiert deine Fokus-Ratings relativ zu Elvanse-Einnahmen. "
        "Je mehr Daten, desto präziser die persönliche Wirkungskurve."
    )

    model_data = api_get("/api/model/fit")

    if isinstance(model_data, dict):
        ms = model_data.get("status", "error")
        pc = model_data.get("pairs", 0)
        req = model_data.get("required", 15)

        st.progress(min(pc / max(req, 1), 1.0), text=f"Datenpunkte: {pc}/{req}")

        collected = model_data.get("collected_pairs", [])

        if ms == "insufficient_data":
            st.warning(model_data.get("message", "Nicht genug Daten."))

        elif ms == "ok":
            st.success("Modell berechnet!")
            r1, r2, r3 = st.columns(3)
            r1.metric("Korrelation", f"{model_data.get('correlation', 0):.2f}")
            r2.metric("Peak", f"{model_data.get('personal_peak_offset_h', '?')}h")
            thr = model_data.get("personal_threshold")
            r3.metric("Schwelle", f"{thr:.2f}" if thr else "?")
            st.info(model_data.get("recommendation", ""))

        # Plot data regardless of status (as long as we have pairs)
        if collected:
            cpdf = pd.DataFrame(collected).sort_values("offset_h")

            fig_m = go.Figure()

            # Scatter: individual focus ratings
            fig_m.add_trace(go.Scatter(
                x=cpdf["offset_h"], y=cpdf["focus"],
                mode="markers",
                marker=dict(size=10, color="#2196F3", opacity=0.7),
                name="Fokus-Rating",
            ))

            # Smooth model curve from predicted_level
            if "predicted_level" in cpdf.columns:
                # Sort and use line to get a proper curve
                fig_m.add_trace(go.Scatter(
                    x=cpdf["offset_h"],
                    y=cpdf["predicted_level"].apply(lambda x: x * 10),
                    mode="lines",
                    line=dict(color="#FF9800", width=2, shape="spline"),
                    name="Modell-Kurve (×10)",
                ))

            if ms == "ok" and model_data.get("personal_threshold"):
                fig_m.add_hline(
                    y=7,
                    line=dict(color="#4CAF50", width=1, dash="dash"),
                    annotation_text="Fokus ≥ 7",
                )

            fig_m.update_layout(
                xaxis_title="Stunden nach Elvanse",
                yaxis_title="Fokus / Level ×10",
                yaxis=dict(range=[0, 11]),
            )
            mobile_chart(fig_m, height=400)

            with st.expander("Datenpunkte"):
                st.dataframe(
                    cpdf[["offset_h", "focus", "predicted_level"]].rename(columns={
                        "offset_h": "Stunden nach ELV",
                        "focus": "Fokus",
                        "predicted_level": "Modell-Level",
                    }),
                    use_container_width=True,
                )


# =========================================================
# PAGE: Korrelation
# =========================================================
elif current_page == "korrelation":
    st.header("Korrelationsanalyse")

    days_back = st.slider("Tage zurück", 7, 90, 30, key="corr_d")
    now_ts = datetime.now()
    start = (now_ts - timedelta(days=days_back)).isoformat()
    end = now_ts.isoformat()

    intakes_corr = api_get("/api/intake", {"start": start, "end": end})
    logs_corr = api_get("/api/log", {"start": start, "end": end})
    health_corr = api_get("/api/health", {"start": start, "end": end})

    if not isinstance(intakes_corr, list) or not isinstance(logs_corr, list):
        st.warning("Nicht genügend Daten")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Elvanse vs. Fokus")
            pairs = []
            ei_list = [i for i in intakes_corr if i.get("substance") == "elvanse"]
            for lg in logs_corr:
                lt = datetime.fromisoformat(lg["timestamp"])
                foc = lg.get("focus")
                if foc is None:
                    continue
                best = None
                for ei in ei_list:
                    et = datetime.fromisoformat(ei["timestamp"])
                    off = (lt - et).total_seconds() / 3600
                    if 0 <= off <= 16:
                        if best is None or off < best:
                            best = off
                if best is not None:
                    pairs.append({"offset_h": best, "focus": foc})

            if pairs:
                pairs_df = pd.DataFrame(pairs)
                fig_c = go.Figure()
                fig_c.add_trace(go.Scatter(
                    x=pairs_df["offset_h"], y=pairs_df["focus"],
                    mode="markers",
                    marker=dict(size=8, color="#2196F3", opacity=0.7),
                ))
                fig_c.update_layout(xaxis_title="h nach Elvanse", yaxis_title="Fokus")
                mobile_chart(fig_c, height=350)
            else:
                st.info("Noch keine Paare")

        with c2:
            st.subheader("Schlaf vs. Fokus")
            if isinstance(health_corr, list) and health_corr:
                sbd = {}
                for h in health_corr:
                    d_key = h["timestamp"][:10]
                    sd = h.get("sleep_duration")
                    if sd:
                        sbd[d_key] = sd
                sfp = []
                for lg in logs_corr:
                    ld = lg["timestamp"][:10]
                    pd_day = (datetime.fromisoformat(ld) - timedelta(days=1)).strftime("%Y-%m-%d")
                    foc = lg.get("focus")
                    if foc and pd_day in sbd:
                        sfp.append({"sleep_h": sbd[pd_day] / 60, "focus": foc})
                if sfp:
                    sdf = pd.DataFrame(sfp)
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(
                        x=sdf["sleep_h"], y=sdf["focus"],
                        mode="markers",
                        marker=dict(size=8, color="#4CAF50", opacity=0.7),
                    ))
                    fig_s.update_layout(xaxis_title="Schlaf (h Vornacht)", yaxis_title="Fokus")
                    mobile_chart(fig_s, height=350)
                else:
                    st.info("Noch keine Paare")
            else:
                st.info("Keine Health-Daten")

        st.divider()
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Einnahmen", len(intakes_corr) if isinstance(intakes_corr, list) else 0)
        mc2.metric("Logs", len(logs_corr) if isinstance(logs_corr, list) else 0)
        mc3.metric("Health", len(health_corr) if isinstance(health_corr, list) else 0)


# =========================================================
# PAGE: System
# =========================================================
elif current_page == "system":
    st.header("System")

    status_data = api_get("/api/status")
    if isinstance(status_data, dict):
        sc1, sc2 = st.columns(2)
        sc1.metric("Service", status_data.get("service", "?"))
        sc2.metric("Status", status_data.get("status", "?"))
        st.caption(f"Server: {status_data.get('timestamp', '?')}")

        ui = status_data.get("user", {})
        if ui:
            uc1, uc2, uc3, uc4 = st.columns(4)
            uc1.metric("Gewicht", f"{ui.get('weight_kg', '?')} kg")
            uc2.metric("Größe", f"{ui.get('height_cm', '?')} cm")
            uc3.metric("Alter", f"{ui.get('age', '?')}")
            uc4.metric("Fasten", "Ja" if ui.get("fasting") else "Nein")

    st.divider()
    st.subheader("Letzte Einnahmen")
    for sn, sl in [("elvanse", "Elvanse"), ("medikinet", "Medikinet IR"), ("medikinet_retard", "Med. retard")]:
        lat = api_get("/api/intake/latest", {"substance": sn})
        if isinstance(lat, dict) and lat.get("found"):
            ts_val = lat.get("timestamp", "?")
            dose_val = lat.get("dose_mg", "?")
            try:
                it = datetime.fromisoformat(ts_val)
                hrs = (datetime.now() - it).total_seconds() / 3600
                st.text(f"{sl}: {dose_val}mg — vor {hrs:.1f}h ({ts_val[11:16]})")
            except Exception:
                st.text(f"{sl}: {dose_val}mg @ {ts_val}")
        else:
            st.text(f"{sl}: —")

    st.divider()
    st.subheader("Log-Zeitplan")
    rem = api_get("/api/log-reminder")
    if isinstance(rem, dict):
        sch = rem.get("schedule", [])
        for s in sch:
            icon = "[x]" if s["status"] == "done" else (">>>" if s["status"] == "due" else "[ ]")
            label = s.get("label", "?")
            target = s.get("target_time", "?")
            st.text(f"{icon} {target} — {label}")

        st.caption(
            "Zeitplan richtet sich nach Elvanse-Einnahme: Baseline (15 Min vor), "
            "dann +1.5h (Onset), +4h (Peak), +8h (Decline), 22:00 (Vor Schlafen). "
            "Ohne Elvanse: feste Zeiten (09:00, 12:00, 15:00, 18:00, 21:00)."
        )

    st.divider()
    st.code(f"API: {API_BASE}\nKey: {'***' + API_KEY[-4:] if len(API_KEY) > 4 else '(nicht gesetzt)'}")