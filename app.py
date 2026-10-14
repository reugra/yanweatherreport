import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from io import BytesIO

# Version 1.3
st.set_page_config(page_title="Yan Weather Report", layout="wide")

# ---------- Red button style ----------
st.markdown("""
<style>
div.stDownloadButton > button {
    background-color: #e74c3c !important;
    color: white !important;
    border: none !important;
    font-weight: bold;
}
div.stDownloadButton > button:hover {
    background-color: #c0392b !important;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ---------- Helper: BMKG forecast extractor ----------
def get_bmkg_current(adm4):
    try:
        url = f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={adm4}"
        resp = requests.get(url, timeout=12)
        if resp.status_code != 200:
            return None, None, f"HTTP {resp.status_code}"
        data = resp.json()
        lokasi = data.get("lokasi", {})
        cuaca_days = data.get("data", [{}])[0].get("cuaca", [])
        if not cuaca_days or not cuaca_days[0]:
            return None, lokasi, "No data"
        item = cuaca_days[0][0]
        return item, lokasi, None
    except Exception as e:
        return None, None, str(e)

# ---------- Helper: Generate PDF (half-page layout) ----------
def generate_pdf(timestamp, texts, image_urls):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)  # manual control to avoid overlap
    pdf.set_margins(12, 12, 12)

    # ===== PAGE 1 =====
    pdf.add_page()

    # Top half: title + timestamp + Himawari
    pdf.set_font("Helvetica", size=13)
    pdf.set_xy(12, 12)
    pdf.cell(0, 7, "Yan Weather Report", ln=True, align="C")
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 5, timestamp, ln=True, align="C")

    try:
        img_resp = requests.get(image_urls[0][1], timeout=15)
        if img_resp.status_code == 200:
            pdf.image(BytesIO(img_resp.content), x=20, y=30, w=160)
    except Exception:
        pdf.set_xy(20, 40)
        pdf.cell(0, 5, "Himawari IR Enhanced - not available")

    # Bottom half: Citra Sebaran Asap
    try:
        img_resp = requests.get(image_urls[1][1], timeout=15)
        if img_resp.status_code == 200:
            pdf.image(BytesIO(img_resp.content), x=20, y=155, w=160)
    except Exception:
        pdf.set_xy(20, 165)
        pdf.cell(0, 5, "Citra Sebaran Asap - not available")

    # ===== PAGE 2 =====
    pdf.add_page()

    # Top half: BMKG Prakiraan Angin
    try:
        img_resp = requests.get(image_urls[2][1], timeout=15)
        if img_resp.status_code == 200:
            pdf.image(BytesIO(img_resp.content), x=20, y=15, w=160)
    except Exception:
        pdf.set_xy(20, 25)
        pdf.cell(0, 5, "BMKG Prakiraan Angin - not available")

    # Bottom half: text data
    pdf.set_xy(12, 155)
    pdf.set_font("Helvetica", size=8)
    for line in texts:
        safe = line.replace("–", "-").replace("—", "-").replace("°", " deg")
        pdf.multi_cell(0, 4, safe)
        pdf.ln(0.3)

    return bytes(pdf.output())

# ---------- Timestamp ----------
now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

# ---------- Collect data ----------
pdf_texts = []
image_list = []

himawari_url = "https://inderaja.bmkg.go.id/IMAGE/HIMA/H08_EH_Indonesia.png"
asap_url = "https://inderaja.bmkg.go.id/Trajektori/Asap.png"
angin_url = "https://dataweb.bmkg.go.id/cuaca/angin/streamline-d10.jpg"

image_list.append(("Himawari IR Enhanced", himawari_url))
image_list.append(("Citra Sebaran Asap", asap_url))
image_list.append(("BMKG Prakiraan Angin", angin_url))

# WAMM
pdf_texts.append("WAMM - Sam Ratulangi International Airport (Manado)")
metar_url = "https://aviationweather.gov/api/data/metar?ids=WAMM&format=json"
try:
    m_resp = requests.get(metar_url, timeout=12)
    metar_raw = "Not available"
    if m_resp.status_code == 200:
        m_data = m_resp.json()
        if m_data and isinstance(m_data, list) and len(m_data) > 0:
            metar_raw = m_data[0].get("rawOb", "Not available")
    pdf_texts.append("METAR:")
    pdf_texts.append(metar_raw)
except Exception as e:
    metar_raw = f"Error: {e}"
    pdf_texts.append(f"METAR error: {e}")

taf_url = "https://aviationweather.gov/api/data/taf?ids=WAMM&format=json"
try:
    t_resp = requests.get(taf_url, timeout=12)
    taf_raw = "Not available"
    if t_resp.status_code == 200:
        t_data = t_resp.json()
        if t_data and isinstance(t_data, list) and len(t_data) > 0:
            taf_raw = t_data[0].get("rawTAF", "Not available")
    pdf_texts.append("TAF:")
    pdf_texts.append(taf_raw)
except Exception as e:
    taf_raw = f"Error: {e}"
    pdf_texts.append(f"TAF error: {e}")

pdf_texts.append("")

# WAFF
pdf_texts.append("WAFF - Mutiara SIS Al-Jufrie (Palu)")
waff_adm4 = "72.71.06.1001"
waff_item, waff_lokasi, waff_err = get_bmkg_current(waff_adm4)
if waff_item:
    ws_kmh = waff_item.get("ws") or 0
    ws_kt = round(float(ws_kmh) / 1.852, 1) if ws_kmh else ""
    vis = waff_item.get("vs_text") or waff_item.get("vs") or "N/A"
    waff_text = (
        f"{waff_item.get('utc_datetime', '')} UTC | "
        f"{waff_item.get('t', '')} deg C | "
        f"Wind {waff_item.get('wd', '')} {ws_kt} kt | "
        f"Clouds {waff_item.get('tcc', '')}% | "
        f"Vis {vis} | "
        f"{waff_item.get('weather_desc_en') or waff_item.get('weather_desc', '')}"
    )
    pdf_texts.append(waff_text)
else:
    waff_text = f"WAFF data not available: {waff_err}"
    pdf_texts.append(waff_text)

pdf_texts.append("")

# Sulawesi Tengah locations
pdf_texts.append("SULAWESI TENGAH LOCATIONS")
locations = {
    "Watusongu": "72.09.06.2006",
    "Wontowu": "72.09.06.2005",
    "Paramba": "72.12.09.2014",
    "Kayupoli": "72.12.08.2019",
    "Kolakolamon": "72.01.09.2037",
    "Lokait": "72.01.17.2012",
}
rows = []
for name, adm4 in locations.items():
    item, lokasi, err = get_bmkg_current(adm4)
    if item and lokasi:
        kab = lokasi.get("kotkab", "")
        kec = lokasi.get("kecamatan", "")
        desa = lokasi.get("desa", "")
        admin_col = f"{kab} - {kec} - {desa}".strip(" -")
        ws_kmh = item.get("ws") or 0
        ws_kt = round(float(ws_kmh) / 1.852, 1) if ws_kmh else ""
        vis = item.get("vs_text") or item.get("vs") or "N/A"
        rows.append({
            "Location": name,
            "Kabupaten-Kecamatan-Desa": admin_col,
            "UTC time": item.get("utc_datetime", ""),
            "Temp C": item.get("t", ""),
            "Humidity %": item.get("hu", ""),
            "Wind": f"{item.get('wd', '')} {ws_kt} kt",
            "Clouds %": item.get("tcc", ""),
            "Visibility": vis,
            "Weather": item.get("weather_desc_en") or item.get("weather_desc", ""),
        })
        pdf_texts.append(
            f"{name} | {admin_col} | {item.get('utc_datetime', '')} UTC | "
            f"{item.get('t', '')}C | Wind {item.get('wd', '')} {ws_kt} kt | "
            f"Clouds {item.get('tcc', '')}% | Vis {vis} | "
            f"{item.get('weather_desc_en') or item.get('weather_desc', '')}"
        )
    else:
        rows.append({
            "Location": name,
            "Kabupaten-Kecamatan-Desa": "N/A",
            "Error": err or "No data"
        })
        pdf_texts.append(f"{name}: Error - {err}")

pdf_bytes = generate_pdf(now, pdf_texts, image_list)

# ========== PAGE DISPLAY ==========
st.download_button(
    label="Save PDF",
    data=pdf_bytes,
    file_name=f"Yan_Weather_Report_{now.replace(' ', '_').replace(':', '')}.pdf",
    mime="application/pdf",
    key="pdf_top"
)

st.header(f"Timestamp: {now}")

st.header("Satellite Images")
st.subheader("Himawari IR Enhanced")
st.image(himawari_url, use_container_width=True)
st.caption(f"Source: {himawari_url}")

st.subheader("Citra Sebaran Asap")
st.image(asap_url, use_container_width=True)
st.caption(f"Source: {asap_url}")

st.header("BMKG Prakiraan Angin")
st.image(angin_url, use_container_width=True)
st.caption(f"Source: {angin_url}")

st.header("WAMM - Sam Ratulangi International Airport (Manado)")
st.subheader("METAR")
st.text(metar_raw)
st.caption(f"Source: {metar_url}")
st.subheader("TAF")
st.text(taf_raw)
st.caption(f"Source: {taf_url}")

st.header("WAFF - Mutiara SIS Al-Jufrie (Palu)")
if waff_item:
    st.write(waff_text)
else:
    st.warning(waff_text)
st.caption(f"Source: https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={waff_adm4}")

st.header("SULAWESI TENGAH LOCATIONS")
if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
st.caption("Source: https://api.bmkg.go.id/publik/prakiraan-cuaca")

st.header("WINDY.COM")
windy_embed = "https://embed.windy.com/embed2.html?lat=-1.0&lon=121.0&detailLat=-1.0&detailLon=121.0&width=650&height=450&zoom=6&level=surface&overlay=wind&product=ecmwf&menu=&message=&marker=&calendar=now&pressure=&type=map&location=coordinates&detail=&metricWind=default&metricTemp=default&radarRange=-1"
st.components.v1.iframe(windy_embed, height=500)
st.caption("Source: https://www.windy.com (low-level winds, central Sulawesi)")

st.download_button(
    label="Save PDF",
    data=pdf_bytes,
    file_name=f"Yan_Weather_Report_{now.replace(' ', '_').replace(':', '')}.pdf",
    mime="application/pdf",
    key="pdf_bottom"
)
