import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="Yan Weather Report", layout="wide")

# ---------- Helper: BMKG forecast extractor ----------
def get_bmkg_current(adm4):
    try:
        url = f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={adm4}"
        resp = requests.get(url, timeout=12)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        data = resp.json()
        cuaca_days = data.get("data", [{}])[0].get("cuaca", [])
        if not cuaca_days or not cuaca_days[0]:
            return None, "No data"
        item = cuaca_days[0][0]  # first / most recent period
        return item, None
    except Exception as e:
        return None, str(e)

# ---------- Helper: Generate PDF ----------
def generate_pdf(timestamp, texts, image_urls):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=14)
    pdf.cell(0, 10, "Yan Weather Report", ln=True, align="C")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 8, timestamp, ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", size=9)
    for line in texts:
        # replace problematic characters
        safe = line.replace("–", "-").replace("—", "-").replace("°", " deg")
        pdf.multi_cell(0, 5, safe)
        pdf.ln(1)

    # Embed images
    for title, url in image_urls:
        try:
            img_resp = requests.get(url, timeout=15)
            if img_resp.status_code == 200:
                pdf.add_page()
                pdf.set_font("Helvetica", size=12)
                pdf.cell(0, 10, title, ln=True)
                pdf.image(BytesIO(img_resp.content), x=10, y=30, w=190)
        except Exception:
            pdf.add_page()
            pdf.cell(0, 10, f"{title} - image not available", ln=True)

    return bytes(pdf.output())

# ---------- Timestamp ----------
now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

# ---------- Collect data for display + PDF ----------
pdf_texts = [f"Yan Weather Report - {now}", ""]
image_list = []

# ========== TOP PDF BUTTON ==========
# (will be re-created after data is ready)

# ========== TIMESTAMP ==========
st.header(f"Timestamp: {now}")
pdf_texts.append(f"Timestamp: {now}")

# ========== SATELLITE IMAGES ==========
st.header("Satellite Images")
pdf_texts.append("\n=== Satellite Images ===")

himawari_url = "https://inderaja.bmkg.go.id/IMAGE/HIMA/H08_EH_Indonesia.png"
asap_url = "https://inderaja.bmkg.go.id/Trajektori/Asap.png"

st.subheader("Himawari IR Enhanced")
st.image(himawari_url, use_container_width=True)
st.caption(f"Source: {himawari_url}")
pdf_texts.append("Himawari IR Enhanced")
pdf_texts.append(f"Source: {himawari_url}")
image_list.append(("Himawari IR Enhanced", himawari_url))

st.subheader("Citra Sebaran Asap")
st.image(asap_url, use_container_width=True)
st.caption(f"Source: {asap_url}")
pdf_texts.append("Citra Sebaran Asap")
pdf_texts.append(f"Source: {asap_url}")
image_list.append(("Citra Sebaran Asap", asap_url))

# ========== BMKG PRAKIRAAN ANGIN ==========
st.header("BMKG Prakiraan Angin")
angin_url = "https://dataweb.bmkg.go.id/cuaca/angin/streamline-d10.jpg"
st.image(angin_url, use_container_width=True)
st.caption(f"Source: {angin_url}")
pdf_texts.append("\n=== BMKG Prakiraan Angin ===")
pdf_texts.append(f"Source: {angin_url}")
image_list.append(("BMKG Prakiraan Angin", angin_url))

# ========== WAMM ==========
st.header("WAMM")
pdf_texts.append("\n=== WAMM ===")

# METAR
metar_url = "https://aviationweather.gov/api/data/metar?ids=WAMM&format=json"
try:
    m_resp = requests.get(metar_url, timeout=12)
    metar_raw = "Not available"
    if m_resp.status_code == 200:
        m_data = m_resp.json()
        if m_data and isinstance(m_data, list) and len(m_data) > 0:
            metar_raw = m_data[0].get("rawOb", "Not available")
    st.subheader("METAR")
    st.text(metar_raw)
    st.caption(f"Source: {metar_url}")
    pdf_texts.append("METAR:")
    pdf_texts.append(metar_raw)
    pdf_texts.append(f"Source: {metar_url}")
except Exception as e:
    st.error(f"METAR error: {e}")
    pdf_texts.append(f"METAR error: {e}")

# TAF
taf_url = "https://aviationweather.gov/api/data/taf?ids=WAMM&format=json"
try:
    t_resp = requests.get(taf_url, timeout=12)
    taf_raw = "Not available"
    if t_resp.status_code == 200:
        t_data = t_resp.json()
        if t_data and isinstance(t_data, list) and len(t_data) > 0:
            taf_raw = t_data[0].get("rawTAF", "Not available")
    st.subheader("TAF")
    st.text(taf_raw)
    st.caption(f"Source: {taf_url}")
    pdf_texts.append("TAF:")
    pdf_texts.append(taf_raw)
    pdf_texts.append(f"Source: {taf_url}")
except Exception as e:
    st.error(f"TAF error: {e}")
    pdf_texts.append(f"TAF error: {e}")

# ========== WAFF ==========
st.header("WAFF - Mutiara SIS Al-Jufrie (Palu)")
waff_adm4 = "72.71.06.1001"  # Nunu, Tatanga, Kota Palu
waff_item, waff_err = get_bmkg_current(waff_adm4)
waff_source = f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={waff_adm4}"
pdf_texts.append("\n=== WAFF ===")

if waff_item:
    waff_text = (
        f"{waff_item.get('local_datetime', '')} | "
        f"{waff_item.get('t', '')}°C | "
        f"Wind {waff_item.get('wd', '')} {waff_item.get('ws', '')} km/h | "
        f"Clouds {waff_item.get('tcc', '')}% | "
        f"{waff_item.get('weather_desc_en') or waff_item.get('weather_desc', '')}"
    )
    st.write(waff_text)
    pdf_texts.append(waff_text)
else:
    st.warning(f"WAFF data not available: {waff_err}")
    pdf_texts.append(f"WAFF data not available: {waff_err}")

st.caption(f"Source: {waff_source}")
pdf_texts.append(f"Source: {waff_source}")

# ========== SULAWESI TENGAH LOCATIONS ==========
st.header("SULAWESI TENGAH LOCATIONS")
pdf_texts.append("\n=== SULAWESI TENGAH LOCATIONS ===")

locations = {
    "Watusongu": "72.09.06.2006",
    "Wontowu": "72.09.06.2005",
    "Paramba": "72.12.09.2014",
    "Kayupoli": "72.12.08.2019",
    "Kolakolamon": "72.01.09.2037",
    "Lokait": "72
