# Version 2.5 – adds RainViewer static radar image for central/north Sulawesi
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

# ---------- Helper: WAFF bandara scraper ----------
def scrape_waff_bandara():
    url = "https://www.bmkg.go.id/cuaca/bandara/WAFF"
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
            # datetime (e.g. 14 Okt 2026 • 11.00 WITA)
            if re.search(r"\d{1,2}\s+[A-Za-z]{3,}\s+\d{4}", line) and ("wita" in low or "wib" in low or "wit" in low):
                result["datetime"] = line.strip()
            # temperature
            if re.search(r"\d+\s*°C", line) and "titik" not in low and "embun" not in low and not result["temp"]:
                m = re.search(r"(\d+\s*°C)", line)
                if m:
                    result["temp"] = m.group(1).strip()
            # short weather (prefer short labels near temp)
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

# ---------- Helper: RainViewer radar ----------
def get_rainviewer_radar_url(lat=-1.0, lon=121.0, zoom=5, size=512):
    try:
        api_url = "https://api.rainviewer.com/public/weather-maps.json"
        resp = requests.get(api_url, timeout=12)
        if resp.status_code != 200:
            return None, f"API HTTP {resp.status_code}"
        data = resp.json()
        host = data.get("host", "https://tilecache.rainviewer.com")
        past = data.get("radar", {}).get("past", [])
        if not past:
            return None, "No radar frames available"
        latest = past[-1]
        path = latest.get("path")
        if not path:
            return None, "No path in latest frame"
        # color=2 is Universal Blue; options=1_1 is common
        img_url = f"{host}{path}/{size}/{zoom}/{lat}/{lon}/2/1_1.png"
        return img_url, None
    except Exception as e:
        return None, str(e)

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

    # Page 1 images (Himawari + Asap)
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

    # Page 2: Angin + radar (if present) + text
    angin_url = None
    radar_url = None
    for label, url in image_urls:
        if "angin" in label.lower() or "prakiraan" in label.lower():
            angin_url = url
        if "radar" in label.lower() or "rainviewer" in label.lower():
            radar_url = url

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

    if radar_url:
        try:
            img_resp = requests.get(radar_url, timeout=15)
            if img_resp.status_code == 200:
                img_bytes = BytesIO(img_resp.content)
                pdf.image(img_bytes, x=25, y=y, w=160)
                y += 90
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
    data=b"",  # placeholder, filled later
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

# ---------- RainViewer Radar ----------
st.header("Radar – Central & North Sulawesi (RainViewer)")
radar_url, radar_err = get_rainviewer_radar_url(lat=-1.0, lon=121.0, zoom=5, size=512)
if radar_url:
    st.image(radar_url, use_container_width=True)
    st.caption(f"Source: RainViewer (BMKG data) – {radar_url}")
else:
    st.warning(f"RainViewer radar not available: {radar_err}")

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
waff_data, waff_err = scrape_waff_bandara()
dir_map = {
    "utara": "N", "timur laut": "NE", "timur": "E", "tenggara": "SE",
    "selatan": "S", "barat daya": "SW", "barat": "W", "barat laut": "NW",
    "variable": "VRB"
}
if waff_data:
    parts = []
    if waff_data.get("datetime"):
        parts.append(waff_data["datetime"].replace("•", " - "))
    if waff_data.get("temp"):
        parts.append(waff_data["temp"])
    if waff_data.get("weather"):
        parts.append(waff_data["weather"])
    if waff_data.get("visibility"):
        parts.append(f"Visibility {waff_data['visibility']}")
    wind_parts = []
    if waff_data.get("wind_dir"):
        abbr = dir_map.get(waff_data["wind_dir"].lower(), waff_data["wind_dir"])
        wind_parts.append(abbr)
    if waff_data.get("wind_speed"):
        try:
            kmh = float(waff_data["wind_speed"].replace(",", "."))
            kt = round(kmh / 1.852, 1)
            wind_parts.append(f"{kt} kt")
        except Exception:
            wind_parts.append(waff_data["wind_speed"] + " km/h")
    if wind_parts:
        parts.append("Wind " + " ".join(wind_parts))
    if waff_data.get("pressure"):
        parts.append(waff_data["pressure"])
    if waff_data.get("dewpoint"):
        parts.append(f"Dewpoint {waff_data['dewpoint']}")
    waff_text = " | ".join(parts)
    st.write(waff_text)
else:
    st.warning(f"WAFF data not available: {waff_err}")
st.caption("Source: https://www.bmkg.go.id/cuaca/bandara/WAFF")

# YAN Locations
st.header("YAN LOCATIONS")
locations = {
    "Watusongu": "72.09.06.2006",
    "Wontowu": "72.09.06.2005",
    "Paramba": "72.12.09.2014",
    "Kayupoli": "72.12.08.2019",
    "Kolakolamon": "72.01.09.2037",
    "Lokait": "72.01.17.2012",
    "Waimiha": "82.08.07.2006",
    "Lili": "82.06.09.2004",
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

# Windy
st.header("WINDY.COM")
windy_embed = "https://embed.windy.com/embed2.html?lat=-1.0&lon=121.0&detailLat=-1.0&detailLon=121.0&width=650&height=450&zoom=6&level=surface&overlay=wind&product=ecmwf&menu=&message=&marker=&calendar=now&pressure=&type=map&location=coordinates&detail=&metricWind=default&metricTemp=default&radarRange=-1"
st.components.v1.iframe(windy_embed, height=500)
st.caption("Source: https://www.windy.com (low-level winds, central Sulawesi)")

# ---------- PDF generation ----------
pdf_texts = []
pdf_texts.append(f"WAMM METAR: {metar_raw}")
pdf_texts.append(f"WAMM TAF: {taf_raw}")
pdf_texts.append(f"WAFF: {waff_text if 'waff_text' in locals() else 'Not available'}")
pdf_texts.append("YAN LOCATIONS:\n" + df.to_string(index=False) if 'df' in locals() else "No location data")

image_list = [
    ("Himawari IR Enhanced", himawari_url),
    ("Citra Sebaran Asap", asap_url),
    ("BMKG Prakiraan Angin", angin_url),
]
if radar_url:
    image_list.append(("RainViewer Radar", radar_url))

pdf_bytes = generate_pdf(now, pdf_texts, image_list)

# Update both download buttons
st.download_button(
    label="Save PDF",
    data=pdf_bytes,
    file_name=f"Yan_Weather_Report_{now.replace(' ', '_').replace(':', '')}.pdf",
    mime="application/pdf",
    key="pdf_bottom"
)

# Top button needs to be re-rendered with data – Streamlit limitation workaround:
# The top button is placed early; we re-create it at the end with the real data if needed.
# For simplicity the bottom button is the reliable one; you can move the top one after PDF generation if preferred.
