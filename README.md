# 🛰️ ANTRIKSHA NETRA

**Live Orbital Conjunction Intelligence → Risk Assessment → Mission-Planning Recommendation**

ANTRIKSHA NETRA is a hackathon decision-support prototype that retrieves public orbital data from **CelesTrak**, identifies close approaches between tracked space objects, presents key conjunction metrics, and ranks alternative Earth-observation satellites using a transparent demonstration scoring rule.

> **Important:** This is a decision-support prototype. It is **not flight-certified guidance**, does not command spacecraft, and does not claim to calculate an operator-certified collision probability.

---

## 🚀 What It Does

ANTRIKSHA NETRA follows four major steps:

### 1. DETECT
Retrieves current conjunction predictions from **CelesTrak SOCRATES Plus**.

### 2. ASSESS
Shows important conjunction information such as:

- Closest separation
- Time of Closest Approach (TCA)
- Relative speed
- Published screening probability

### 3. MISSION-PLANNING RECOMMENDATION
Uses current Earth Resources orbital data to rank alternative satellites for an Earth-observation mission.

### 4. EXPLAIN
Explains the orbital and decision-making terms in simple language so that the user can understand **why** a recommendation was made.

---

# 🌐 Data Sources

## LIVE Mode

LIVE mode retrieves public data from:

- **CelesTrak SOCRATES Plus** — conjunction / close-approach data
- **CelesTrak Earth Resources GP feed** — orbital data for Earth-resource satellites

Live requests are cached for **15 minutes**.

## DEMO Mode

DEMO mode uses a small synthetic scenario for offline demonstration.

It is clearly labelled as synthetic and must **not** be treated as real satellite or collision-warning data.

---

# 🧠 Recommendation Logic

ANTRIKSHA NETRA calculates an approximate orbital suitability score for alternative satellites.

The demonstration **Decision Score / 100** uses:

- **Altitude suitability — 45 points**
- **Inclination suitability — 35 points**
- **Eccentricity suitability — 20 points**

This scoring system is intentionally simple and transparent for the hackathon.

> It is **not an operational satellite-tasking algorithm**.

---

# 📖 Important Terms

| Term | Meaning |
|---|---|
| **Conjunction** | A predicted close approach between two space objects. |
| **Closest Approach / Minimum Separation** | The smallest predicted distance between two objects. |
| **TCA** | Time of Closest Approach — when the minimum separation is expected to occur. |
| **Relative Speed** | The speed of one object relative to another during the encounter. |
| **Max Probability** | A published CelesTrak screening metric based on object size and position uncertainty assumptions. |
| **NORAD Catalog Number** | An identification number assigned to a tracked space object. |
| **GP / Orbital Elements** | Published parameters used to describe an object's orbit. |
| **Inclination** | The tilt of an orbit relative to Earth's equatorial plane. |
| **Eccentricity** | A measure of how circular or stretched an orbit is. 0 means a circular orbit. |
| **Perigee** | The lowest point of an orbit above Earth's surface. |
| **Apogee** | The highest point of an orbit above Earth's surface. |
| **Decision Score** | ANTRIKSHA NETRA's own transparent ranking score for selecting an alternative satellite. |

---

# 🛠️ Technology Stack

- Python
- Streamlit
- Pandas
- Requests
- BeautifulSoup
- Plotly
- CelesTrak public data feeds

---

# 📁 Project Structure

```text
ANTRIKSHA-NETRA/
│
├── app.py
├── requirements.txt
└── README.md
