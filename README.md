# ORBITGUARD — Live

Hackathon prototype for live orbital conjunction screening and explainable mission-planning recommendations.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Data

LIVE mode retrieves:
- CelesTrak SOCRATES Plus conjunction predictions
- CelesTrak Earth Resources GP orbital elements

DEMO mode uses clearly labelled synthetic data only as a fallback.

## Important

The mission-planning score is demonstration logic, not flight-certified guidance or an operator collision-probability calculation.
