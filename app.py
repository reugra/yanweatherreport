# Version 2.6 – updated YAN locations + WAFW & WAEE airports (same format as WAFF) + Windy rain overlay
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from io import BytesIO
from bs4 import BeautifulSoup
import re

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

# ---------- Helper: Airport bandara scraper (WAFF / WAFW / WAEE) ----------
def scrape_bandara(icao):
    url = f"https://www.bmkg.go.id/cuaca/bandara/{icao}"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text("\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        result = {
            "datetime": "",
            "temp": "",
            "weather": "",
            "visibility": "",
            "wind_speed": "",
            "wind_dir": "",
            "pressure": "",
            "dewpoint": "",
        }
        for i, line in enumerate(lines):
            low = line.lower()
            # datetime
            if re.search(r"\d{1,2}\s+[A-Za-z]{3,}\s+\d{4}", line) and ("wita" in low or "wib" in low or "wit" in low):
                result["datetime"] = line.strip()
            # temperature
            if re.search(r"\d+\s*°C", line) and "titik" not in low and "embun" not in low and not result["temp"]:
                m = re.search(r"(\d+\s*°C)", line)
                if m:
                    result["temp"] = m.group(1).strip()
            # short weather
            short_weather = ["berasap", "berawan", "cerah", "hujan", "kabut", "mendung"]
            if any(w in low for w in short_weather) and not result["weather"]:
                for w in short_weather:
                    if w in low:
                        result["weather"] = w.title()
                        break
            # visibility
            if "jarak pandang" in low or "visibility" in low:
                m = re.search(r"(\d+(?:[.,]\d+)?)\s*km", line, re.I)
                if m:
                    result["visibility"] = m.group(1).replace(",", ".") + " km"
            # wind speed (handles both 7,4 and 13)
            if "kecepatan angin" in low or re.search(r"\d+(?:[.,]\d+)?\s*km/jam", low):
                m = re.search(r"(\d+(?:[.,]\d+)?)\s*km/jam", line, re.I)
                if m:
                    result["wind_speed"] = m.group(1).replace(",", ".")
            # wind direction
            if "arah angin" in low:
                full_dirs = [
                    "utara", "timur laut", "timur", "tenggara", "selatan",
                    "barat daya", "barat", "barat laut", "variable"
                ]
                for d in full_dirs:
                    if d in low:
                        result["wind_dir"] = d.title()
                        break
            # pressure
            if "tekanan" in low or "hpa" in low:
                m = re.search(r"(\d+[.,]\d+)\s*hpa", line, re.I)
                if m:
                    result["pressure"] = m.group(1).replace(",", ".") + " hPa"
            # dewpoint
            if "titik embun" in low or "dew" in low:
                m = re.search(r"(\d+\s*°C)", line)
                if m:
                    result["dewpoint"] = m.group(1).strip()
        result = {k: v for k, v in result.items() if v}
        return result, None
    except Exception as e:
        return None, str(e)

def format_airport_text(data):
    if not data:
        return None
    dir_map = {
        "utara": "N", "timur laut": "NE", "timur": "E", "tenggara": "SE",
        "selatan": "S", "barat daya": "SW", "barat": "W", "barat laut": "NW",
        "variable": "VRB"
    }
    parts = []
    if data.get("datetime"):
        parts.append(data["datetime"].replace("•", " - "))
    if data.get("temp"):
        parts.append(data["temp"])
    if data.get("weather"):
        parts.append(data["weather"])
    if data.get("visibility"):
        parts.append(f"Visibility {data['visibility']}")
    wind_parts = []
    if data.get("wind_dir"):
        abbr = dir_map.get(data["wind_dir"].lower(), data["wind_dir"])
        wind_parts.append(abbr)
    if data.get("wind_speed"):
        try:
            kmh = float(data["wind_speed"].replace(",", "."))
            kt = round(kmh / 1.852, 1)
            wind_parts.append(f"{kt} kt")
        except Exception:
            wind_parts.append(data["wind_speed"] + " km/h")
    if wind_parts:
        parts.append("Wind " + " ".join(wind_parts))
    if data.get("pressure"):
        parts.append(data["pressure"])
    if data.get("dewpoint"):
        parts.append(f"Dewpoint {data['dewpoint']}")
    return " | ".join(parts)

# ---------- Helper: Generate PDF ----------
def generate_pdf(timestamp, texts, image_urls):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Yan Weather Report", ln=True, align="C")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, timestamp, ln=True, align="C")
    pdf.ln(4)

    # Page 1: Himawari + Asap
    y_start = 30
    for i, (label, url) in enumerate(image_urls[:2]):
        try:
            img_resp = requests.get(url, timeout=15)
            if img_resp.status_code == 200:
                img_bytes = BytesIO(img_resp.content)
                pdf.image(img_bytes, x=25, y=y_start + i * 90, w=160)
        except Exception:
            pass
    pdf.add_page()

    # Page 2: Angin + text
    angin_url = None
    for label, url in image_urls:
        if "angin" in label.lower() or "prakiraan" in label.lower():
            angin_url = url
            break

    y = 15
    if angin_url:
        try:
            img_resp = requests.get(angin_url, timeout=15)
            if img_resp.status_code == 200:
                img_bytes = BytesIO(img_resp.content)
                pdf.image(img_bytes, x=25, y=y, w=160)
                y = 100
        except Exception:
            pass

    pdf.set_xy(15, y + 5)
    pdf.set_font("Helvetica", size=9)
    for block in texts:
        safe = block.replace("•", " - ").encode("ascii", "ignore").decode("ascii")
        pdf.multi_cell(0, 4, safe)
        pdf.ln(2)

    return bytes(pdf.output())

# ---------- Main UI ----------
now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

st.download_button(
    label="Save PDF",
    data=b"",
    file_name=f"Yan_Weather_Report_{now.replace(' ', '_').replace(':', '')}.pdf",
    mime="application/pdf",
    key="pdf_top"
)

st.caption(f"**Timestamp:** {now}")

# Satellite images
st.header("Satellite Images")
himawari_url = "https://inderaja.bmkg.go.id/IMAGE/HIMA/H08_EH_Indonesia.png"
asap_url = "https://inderaja.bmkg.go.id/Trajektori/Asap.png"
angin_url = "https://dataweb.bmkg.go.id/cuaca/angin/streamline-d10.jpg"

col1, col2 = st.columns(2)
with col1:
    st.image(himawari_url, use_container_width=True)
    st.caption(f"Source: {himawari_url}")
with col2:
    st.image(asap_url, use_container_width=True)
    st.caption(f"Source: {asap_url}")

st.header("BMKG Prakiraan Angin")
st.image(angin_url, use_container_width=True)
st.caption(f"Source: {angin_url}")

# WAMM
st.header("WAMM - Sam Ratulangi International Airport (Manado)")
metar_url = "https://aviationweather.gov/api/data/metar?ids=WAMM&format=json"
taf_url = "https://aviationweather.gov/api/data/taf?ids=WAMM&format=json"
try:
    metar_resp = requests.get(metar_url, timeout=10)
    metar_raw = metar_resp.json()[0].get("rawOb", "Not available") if metar_resp.status_code == 200 else "Not available"
except Exception:
    metar_raw = "Not available"
try:
    taf_resp = requests.get(taf_url, timeout=10)
    taf_raw = taf_resp.json()[0].get("rawTAF", "Not available") if taf_resp.status_code == 200 else "Not available"
except Exception:
    taf_raw = "Not available"

st.subheader("METAR")
st.text(metar_raw)
st.caption(f"Source: {metar_url}")
st.subheader("TAF")
st.text(taf_raw)
st.caption(f"Source: {taf_url}")

# WAFF
st.header("WAFF - Mutiara SIS Al-Jufrie (Palu)")
waff_data, waff_err = scrape_bandara("WAFF")
waff_text = format_airport_text(waff_data)
if waff_text:
    st.write(waff_text)
else:
    st.warning(f"WAFF data not available: {waff_err}")
st.caption("Source: https://www.bmkg.go.id/cuaca/bandara/WAFF")

# WAFW
st.header("WAFW - Syukuran Aminuddin Amir Airport (Luwuk)")
wafw_data, wafw_err = scrape_bandara("WAFW")
wafw_text = format_airport_text(wafw_data)
if wafw_text:
    st.write(wafw_text)
else:
    st.warning(f"WAFW data not available: {wafw_err}")
st.caption("Source: https://www.bmkg.go.id/cuaca/bandara/WAFW")

# WAEE
st.header("WAEE - Sultan Babullah Airport (Ternate)")
waee_data, waee_err = scrape_bandara("WAEE")
waee_text = format_airport_text(waee_data)
if waee_text:
    st.write(waee_text)
else:
    st.warning(f"WAEE data not available: {waee_err}")
st.caption("Source: https://www.bmkg.go.id/cuaca/bandara/WAEE")

# YAN Locations
st.header("YAN LOCATIONS")
locations = {
    "Watusongu": "72.09.06.2006",
    "Wontowu": "72.09.06.2019",
    "Paramba": "72.12.09.2014",
    "Kayupoli": "72.12.08.2019",
    "Kolakolamon": "72.01.09.2037",
    "Moitoitom": "72.01.17.2011",
    "Waimiha": "82.08.07.2006",
    "Lili": "82.06.09.2004",
    "Eeya": "72.08.18.2003",
}
rows = []
for name, adm4 in locations.items():
    item, lokasi, err = get_bmkg_current(adm4)
    if item:
        kab = lokasi.get("kabupaten", "") if lokasi else ""
        kec = lokasi.get("kecamatan", "") if lokasi else ""
        desa = lokasi.get("desa", "") if lokasi else ""
        loc_str = f"{kab} - {kec} - {desa}".strip(" - ")
        wind_kmh = item.get("ws", 0)
        try:
            wind_kt = round(float(wind_kmh) / 1.852, 1)
        except Exception:
            wind_kt = "N/A"
        rows.append({
            "Location": name,
            "Kabupaten-Kecamatan-Desa": loc_str,
            "Time (UTC)": item.get("local_datetime", "N/A"),
            "Temp": f"{item.get('t', 'N/A')} °C",
            "Weather": item.get("weather_desc", "N/A"),
            "Wind": f"{item.get('wd', 'N/A')} {wind_kt} kt",
            "Visibility": item.get("vs", "N/A"),
            "Clouds": f"{item.get('tcc', 'N/A')}%",
        })
    else:
        rows.append({"Location": name, "Error": err or "No data"})
if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
st.caption("Source: https://api.bmkg.go.id/publik/prakiraan-cuaca")

# Windy – Rain, thunder
st.header("WINDY.COM")
windy_embed = "https://embed.windy.com/embed2.html?lat=-1.0&lon=121.0&detailLat=-1.0&detailLon=121.0&width=650&height=450&zoom=6&level=surface&overlay=rain&product=ecmwf&menu=&message=&marker=&calendar=now&pressure=&type=map&location=coordinates&detail=&metricWind=default&metricTemp=default&radarRange=-1"
st.components.v1.iframe(windy_embed, height=500)
st.caption("Source: https://www.windy.com (Rain, thunder – central Sulawesi)")

# ---------- PDF generation ----------
pdf_texts = []
pdf_texts.append(f"WAMM METAR: {metar_raw}")
pdf_texts.append(f"WAMM TAF: {taf_raw}")
pdf_texts.append(f"WAFF: {waff_text if waff_text else 'Not available'}")
pdf_texts.append(f"WAFW: {wafw_text if wafw_text else 'Not available'}")
pdf_texts.append(f"WAEE: {waee_text if waee_text else 'Not available'}")
pdf_texts.append("YAN LOCATIONS:\n" + (df.to_string(index=False) if 'df' in locals() else "No location data"))

image_list = [
    ("Himawari IR Enhanced", himawari_url),
    ("Citra Sebaran Asap", asap_url),
    ("BMKG Prakiraan Angin", angin_url),
]

pdf_bytes = generate_pdf(now, pdf_texts, image_list)

st.download_button(
    label="Save PDF",
    data=pdf_bytes,
    file_name=f"Yan_Weather_Report_{now.replace(' ', '_').replace(':', '')}.pdf",
    mime="application/pdf",
    key="pdf_bottom"
)
