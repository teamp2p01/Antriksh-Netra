import math
import re
from datetime import datetime, timezone
from io import StringIO

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="ANTRIKSHA NETRA — Live",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SOCRATES_URL = "https://celestrak.org/SOCRATES/table-socrates.php?MAX=50&NAME=%2C&ORDER=MINRANGE"
RESOURCE_GP_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=CSV"
HEADERS = {"User-Agent": "ANTRIKSHA NETRA/3.0 (hackathon decision-support prototype)"}


def utc_now():
    return datetime.now(timezone.utc)


def fmt_dt(value):
    try:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.tz_convert("UTC").strftime("%d %b %Y, %H:%M:%S UTC")
    except Exception:
        return "Invalid timestamp"


def num(value):
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def fetch_socrates():
    """Fetch and parse the current CelesTrak SOCRATES HTML table."""
    try:
        r = requests.get(SOCRATES_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        if "SOCRATES" not in r.text.upper():
            raise ValueError("CelesTrak did not return a SOCRATES results page.")

        soup = BeautifulSoup(r.text, "html.parser")
        rows = []
        pending = None

        for tr in soup.find_all("tr"):
            cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if not cells:
                continue

            # Current SOCRATES rows are:
            # GP Data | NORAD | Name | Days | TCA | MinRange | RelativeSpeed
            if len(cells) >= 7 and cells[0].lower().startswith("gp data"):
                try:
                    primary_id = int(float(cells[1].replace(",", "")))
                except Exception:
                    continue
                tca = pd.to_datetime(cells[4], utc=True, errors="coerce")
                if pd.isna(tca):
                    continue
                pending = {
                    "primary_id": primary_id,
                    "primary": cells[2] if len(cells) > 2 else "",
                    "tca": tca.to_pydatetime(),
                    "range_km": num(cells[5]) if len(cells) > 5 else None,
                    "relative_speed": num(cells[6]) if len(cells) > 6 else None,
                }
                continue

            # Secondary row:
            # 50 km All | NORAD | Name | Days | MaxProbability | DilutionThreshold
            if pending is not None and len(cells) >= 6 and cells[0].lower().startswith("50 km"):
                try:
                    secondary_id = int(float(cells[1].replace(",", "")))
                except Exception:
                    pending = None
                    continue
                pending["secondary_id"] = secondary_id
                pending["secondary"] = cells[2]
                pending["max_probability"] = num(cells[4])
                pending["dilution_threshold_km"] = num(cells[5])
                rows.append(pending)
                pending = None

        if not rows:
            raise ValueError("SOCRATES returned a page, but no conjunction rows could be parsed.")

        result = pd.DataFrame(rows)
        result = result.dropna(subset=["range_km", "tca"]).sort_values(["range_km", "tca"]).reset_index(drop=True)

        m = re.search(r"Data current as of\s*([^<]+?)\s*Computation Interval", r.text, re.I | re.S)
        result.attrs["data_current"] = re.sub(r"\s+", " ", m.group(1)) if m else "Current CelesTrak SOCRATES run"
        return result
    except Exception as e:
        # Re-raise with more context
        raise Exception(f"Failed to fetch SOCRATES data: {str(e)}")


@st.cache_data(ttl=900, show_spinner=False)
def fetch_resource_gp():
    """Fetch current Earth Resources GP data as CSV."""
    try:
        r = requests.get(RESOURCE_GP_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        if "NORAD_CAT_ID" not in r.text:
            raise ValueError("CelesTrak GP resource feed did not return the expected CSV fields.")
        gp = pd.read_csv(StringIO(r.text))
        required = {"NORAD_CAT_ID", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION"}
        missing = required - set(gp.columns)
        if missing:
            raise ValueError(f"CelesTrak GP feed is missing fields: {', '.join(sorted(missing))}")
        for col in required:
            gp[col] = pd.to_numeric(gp[col], errors="coerce")
        return gp
    except Exception as e:
        raise Exception(f"Failed to fetch resource GP data: {str(e)}")


def derive_orbit_columns(gp):
    g = gp.copy()
    mu = 398600.4418  # km^3/s^2
    earth_radius = 6378.137
    n = g["MEAN_MOTION"] * 2 * math.pi / 86400.0
    a = (mu / (n ** 2)) ** (1 / 3)
    g["PERIGEE_KM"] = a * (1 - g["ECCENTRICITY"]) - earth_radius
    g["APOGEE_KM"] = a * (1 + g["ECCENTRICITY"]) - earth_radius
    return g


def mission_rank(gp, excluded_ids):
    g = derive_orbit_columns(gp)
    g = g.dropna(subset=["NORAD_CAT_ID", "PERIGEE_KM", "APOGEE_KM", "INCLINATION"]).copy()
    g = g[~g["NORAD_CAT_ID"].isin(excluded_ids)]

    # Transparent demonstration rule for Earth-observation missions.
    altitude = (g["PERIGEE_KM"] + g["APOGEE_KM"]) / 2
    altitude_score = (1 - (altitude - 700).abs() / 500).clip(0, 1) * 45
    inclination_score = (1 - (g["INCLINATION"] - 98).abs() / 20).clip(0, 1) * 35
    eccentricity_score = (1 - g["ECCENTRICITY"].abs() / 0.02).clip(0, 1) * 20
    g["decision_score"] = altitude_score + inclination_score + eccentricity_score
    return g[g["decision_score"] > 35].sort_values("decision_score", ascending=False).head(8)


def demo_result():
    now = utc_now()
    conj = pd.DataFrame([
        {
            "primary_id": 25544,
            "secondary_id": 69673,
            "primary": "ISS (ZARYA)",
            "secondary": "Synthetic Debris Object",
            "tca": now + pd.Timedelta(hours=2),
            "range_km": 3.8,
            "relative_speed": 7.1,
            "max_probability": 0.012,
            "dilution_threshold_km": 0.4,
        }
    ])
    gp = pd.DataFrame(columns=["NORAD_CAT_ID", "OBJECT_NAME", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION"])
    return {"conj": conj, "gp": gp, "live": False}


# ---------- UI ----------
st.markdown("""
<style>
.block-container { max-width: 1420px; padding: 2.0rem 2.4rem 4rem; }
.hero { padding: 28px 34px; border: 1px solid #263753; border-radius: 18px; background: linear-gradient(135deg,#0b1728,#101b2d); margin-bottom: 18px; }
.hero h1 { font-size: 3rem; margin: 0; letter-spacing: .02em; }
.hero p { color:#9db8dc; font-size:1.06rem; margin:8px 0 0; }
.section { padding: 24px 0 8px; border-top:1px solid #263142; margin-top:22px; }
.card { padding: 18px 20px; border:1px solid #27344b; border-radius:14px; background:#0d1522; min-height:120px; }
.small { color:#9aa9bd; font-size:.9rem; }
.source { padding: 12px 16px; border-radius: 12px; background:#12253a; color:#9cc8ff; margin: 12px 0 18px; }
div[data-testid="stMetric"] { padding: 10px 4px; }
button[kind="primary"] { min-height: 3rem; }
</style>
<div class="hero">
  <h1>🛰️ ANTRIKSHA NETRA</h1>
  <p>Live orbital conjunction intelligence → risk assessment → mission-planning recommendation</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## Control panel")
    st.caption("LIVE uses public CelesTrak data. DEMO is clearly synthetic and only for offline fallback.")
    mode = st.radio("Data source", ["LIVE — CelesTrak", "DEMO — synthetic"], index=0)
    run_label = "▶ RUN LIVE ANALYSIS" if mode.startswith("LIVE") else "▶ RUN DEMO"
    run = st.button(run_label, type="primary", width="stretch")
    st.divider()
    st.markdown("### Live sources")
    st.markdown("• CelesTrak SOCRATES Plus")
    st.markdown("• CelesTrak Earth Resources GP")
    st.caption("Live feeds are cached for 15 minutes to reduce repeated requests.")

if "result" not in st.session_state:
    st.session_state.result = None

if run:
    if mode.startswith("LIVE"):
        try:
            with st.spinner("Fetching current CelesTrak data…"):
                conj = fetch_socrates()
                gp = fetch_resource_gp()
            st.session_state.result = {"conj": conj, "gp": gp, "live": True}
            st.rerun()
        except Exception as exc:
            st.session_state.result = None
            st.error("LIVE DATA COULD NOT BE LOADED")
            st.code(str(exc))
            st.info("The public source may be temporarily unavailable. Try RUN LIVE ANALYSIS again. DEMO mode remains available as an explicitly labelled fallback.")
    else:
        st.session_state.result = demo_result()
        st.rerun()

result = st.session_state.result
if result is None:
    st.info("Ready. Click **RUN LIVE ANALYSIS** to retrieve current public CelesTrak conjunction and orbital data.")
    st.markdown("### What ANTRIKSHA NETRA does")
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        st.markdown("**01 · DETECT**")
        st.write("Finds current close-approach predictions from CelesTrak SOCRATES Plus.")
    with c2:
        st.markdown("**02 · ASSESS**")
        st.write("Shows closest separation, time of closest approach and CelesTrak screening probability.")
    with c3:
        st.markdown("**03 · DECIDE**")
        st.write("Ranks Earth-observation alternatives using current CelesTrak orbital elements.")
    st.stop()

conj, gp, live = result["conj"], result["gp"], result["live"]
first = conj.iloc[0]

if live:
    st.success("LIVE CelesTrak data loaded successfully.")
    st.markdown(f'<div class="source"><b>LIVE SOURCE:</b> CelesTrak SOCRATES Plus · {conj.attrs.get("data_current", "current run")}</div>', unsafe_allow_html=True)
else:
    st.warning("DEMO MODE — synthetic data. Not a live conjunction warning.")

# Summary
st.markdown("### Live situation")
cols = st.columns(4, gap="large")
cols[0].metric("Conjunctions loaded", len(conj))
cols[1].metric("Closest separation", f"{first['range_km']:.3f} km" if pd.notna(first['range_km']) else "N/A")
cols[2].metric("Time of closest approach", fmt_dt(first["tca"]))
cols[3].metric("CelesTrak max probability", f"{first['max_probability']:.3g}" if pd.notna(first["max_probability"]) else "—")

st.markdown('<div class="section"><h2>1 · DETECT</h2></div>', unsafe_allow_html=True)
st.write(f"**{first['primary']}** and **{first['secondary']}** are the closest event in the loaded SOCRATES results.")
show = conj.head(12).copy()
show["TCA (UTC)"] = show["tca"].apply(fmt_dt)
show["Min separation"] = show["range_km"].map(lambda x: f"{x:.3f} km")
show["Relative speed"] = show["relative_speed"].map(lambda x: "—" if pd.isna(x) else f"{x:.3f} km/s")
show["Max probability"] = show["max_probability"].map(lambda x: "—" if pd.isna(x) else f"{x:.3g}")
show = show[["primary", "primary_id", "secondary", "secondary_id", "TCA (UTC)", "Min separation", "Relative speed", "Max probability"]]
show.columns = ["Object A", "NORAD A", "Object B", "NORAD B", "TCA (UTC)", "Min separation", "Relative speed", "Max probability"]
st.dataframe(show, width="stretch", hide_index=True)

st.markdown('<div class="section"><h2>2 · ASSESS</h2></div>', unsafe_allow_html=True)
a1, a2 = st.columns(2, gap="large")
with a1:
    st.markdown(f'<div class="card"><b>Closest approach</b><h2>{first["range_km"]:.3f} km</h2><span class="small">Smallest predicted separation at the encounter.</span></div>', unsafe_allow_html=True)
with a2:
    st.markdown(f'<div class="card"><b>TCA — Time of Closest Approach</b><h2>{fmt_dt(first["tca"])}</h2><span class="small">Predicted time when the minimum separation occurs.</span></div>', unsafe_allow_html=True)
st.caption("Max Probability is CelesTrak's published screening metric. ANTRIKSHA NETRA does not claim to calculate an operator-certified collision probability.")

st.markdown('<div class="section"><h2>3 · MISSION-PLANNING RECOMMENDATION</h2></div>', unsafe_allow_html=True)
excluded = {int(first["primary_id"]), int(first["secondary_id"])}
candidates = mission_rank(gp, excluded) if live and not gp.empty else pd.DataFrame()
if not candidates.empty:
    rows = []
    for _, r in candidates.iterrows():
        rows.append({
            "Candidate": r.get("OBJECT_NAME", f"NORAD {int(r['NORAD_CAT_ID'])}"),
            "NORAD": int(r["NORAD_CAT_ID"]),
            "Orbit": f"{r['PERIGEE_KM']:.0f}–{r['APOGEE_KM']:.0f} km",
            "Inclination": f"{r['INCLINATION']:.2f}°",
            "Decision score": f"{r['decision_score']:.1f}/100",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    best = candidates.iloc[0]
    best_name = best.get("OBJECT_NAME", f"NORAD {int(best['NORAD_CAT_ID'])}")
    st.success(f"RECOMMENDATION: **{best_name}** — highest score under ANTRIKSHA NETRA's transparent Earth-observation rules.")
else:
    st.info("No live Earth-observation candidate met the demonstration rules. The live conjunction analysis is still valid.")

st.markdown('<div class="section"><h2>4 · EXPLAIN</h2></div>', unsafe_allow_html=True)
with st.expander("📘 Explain every important term", expanded=False):
    st.markdown("""
- **Conjunction:** a predicted close approach between two space objects.
- **Closest approach / minimum separation:** the smallest predicted distance between them.
- **TCA:** Time of Closest Approach — when that minimum distance occurs.
- **Relative speed:** how fast the two objects move relative to each other at TCA.
- **Max Probability:** CelesTrak's screening calculation based on assumed object sizes and position uncertainty; it is not the same as an operator's final collision probability.
- **NORAD catalog number:** the catalog identifier for a tracked space object.
- **GP / orbital elements:** published numbers describing an object's orbit.
- **Decision score:** ANTRIKSHA NETRA's own transparent ranking score for selecting an Earth-observation alternative.
- **Inclination:** the tilt of an orbit relative to Earth's equatorial plane.
- **Eccentricity:** how circular or stretched an orbit is; 0 means perfectly circular.
- **Perigee / apogee:** the lowest / highest altitude of the orbit above Earth's surface.
- **Demo mode:** synthetic data used only when live data is unavailable; it is never presented as real.
""")

st.markdown('<div class="section"></div>', unsafe_allow_html=True)
st.caption("ANTRIKSHA NETRA is a hackathon decision-support prototype. Live conjunction and Earth-observation orbital data are retrieved from public CelesTrak feeds. The mission score is our own planning logic and is not flight-certified guidance.")