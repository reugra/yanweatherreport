# Version 2.14 – PDF page 2 text start raised by ~5 lines
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
from io import BytesIO
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="Yan Weather Brief", layout="wide")

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

# ---------- Helper: Scrape airport current conditions from bandara page ----------
def scrape_bandara(icao):
    url = f"https://www.bmkg.go.id/cuaca/bandara/{icao}"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

        result = {}

        short_weather = {
            "berasap", "cerah", "berawan", "cerah berawan", "cerah - berawan",
            "udara kabur", "kabut/asap", "hujan ringan", "hujan", "cerah-berawan"
        }

        for i, line in enumerate(lines):
            low = line.lower()

            if re.search(r"\d{1,2}\s+[A-Za-z]+\s+\d{4}", line) and ("wita" in low or "wib" in low or "wit" in low or "•" in line):
                if "datetime" not in result:
                    result["datetime"] = line.strip()

            if re.search(r"\d+\s*°C", line) and "titik" not in low and "embun" not in low:
                if "temp" not in result:
                    result["temp"] = re.search(r"(\d+\s*°C)", line).group(1).strip()

            if line.lower() in short_weather or line in ["Berasap", "Cerah", "Berawan", "Cerah - Berawan"]:
                if "weather" not in result or len(line) < len(result.get("weather", "")):
                    result["weather"] = line.strip()

            if "jarak pandang" in low:
                m = re.search(r"(\d+(?:[.,]\d+)?)\s*km", line, re.I)
                if m:
                    result["visibility"] = m.group(0).strip()
                elif i + 1 < len(lines):
                    m = re.search(r"(\d+(?:[.,]\d+)?)\s*km", lines[i+1], re.I)
                    if m:
                        result["visibility"] = m.group(0).strip()

            if "kecepatan angin" in low or re.search(r"\d+(?:[.,]\d+)?\s*km/jam", low):
                m = re.search(r"(\d+(?:[.,]\d+)?)\s*km/jam", line, re.I)
                if m:
                    result["wind_speed"] = m.group(0).replace(",", ".").strip()
                elif i + 1 < len(lines):
                    m = re.search(r"(\d+(?:[.,]\d+)?)\s*km/jam", lines[i+1], re.I)
                    if m:
                        result["wind_speed"] = m.group(0).replace(",", ".").strip()

            if "arah angin" in low:
                full_dirs = [
                    "barat daya", "barat laut", "timur laut", "tenggara",
                    "utara", "timur", "selatan", "barat", "variabel"
                ]
                for d in full_dirs:
                    if d in low:
                        result["wind_dir"] = d.title()
                        break
                if "wind_dir" not in result and i + 1 < len(lines):
                    next_low = lines[i+1].lower()
                    for d in full_dirs:
                        if d in next_low:
                            result["wind_dir"] = d.title()
                            break

            if "tekanan" in low or "hpa" in low:
                m = re.search(r"(\d+[.,]\d+)\s*hpa", line, re.I)
                if m:
                    result["pressure"] = m.group(0).replace(",", ".").strip()

            if "titik embun" in low:
                m = re.search(r"(\d+)\s*°C", line)
                if m:
                    result["dewpoint"] = m.group(0).strip()
                elif i + 1 < len(lines):
                    m = re.search(r"(\d+)\s*°C", lines[i+1])
                    if m:
                        result["dewpoint"] = m.group(0).strip()

        result = {k: v for k, v in result.items() if v}
        return result if result else None, None

    except Exception as e:
        return None, str(e)

def format_airport_text(data):
    if not data:
        return "Not available"
    dir_map = {
        "utara": "N",
        "timur laut": "NE",
        "timur": "E",
        "tenggara": "SE",
        "selatan": "S",
        "barat daya": "SW",
        "barat": "W",
        "barat laut": "NW",
        "variabel": "VRB",
    }
    parts = []
    if data.get("datetime"):
        parts.append(data["datetime"])
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
            kmh_str = re.search(r"[\d.]+", data["wind_speed"])
            if kmh_str:
                kmh = float(kmh_str.group())
                kt = round(kmh / 1.852, 1)
                wind_parts.append(f"{kt} kt")
        except Exception:
            wind_parts.append(data["wind_speed"])
    if wind_parts:
        parts.append("Wind " + " ".join(wind_parts))

    if data.get("pressure"):
        parts.append(data["pressure"])
    if data.get("dewpoint"):
        parts.append(f"Dewpoint {data['dewpoint']}")

    return " | ".join(parts) if parts else "Parsed but empty"

# ---------- Helper: Open-Meteo 80 m wind (current + hourly) ----------
def get_openmeteo_wind(lat, lon):
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "wind_speed_80m,wind_direction_80m",
            "hourly": "wind_speed_80m,wind_direction_80m",
            "wind_speed_unit": "kn",
            "timezone": "UTC",
            "forecast_days": 1,
        }
        resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=12)
        if resp.status_code != 200:
            return None, None, f"HTTP {resp.status_code}"
        data = resp.json()
        return data.get("current", {}), data.get("hourly", {}), None
    except Exception as e:
        return None, None, str(e)

def round_to_nearest_30(dt):
    """Round datetime to nearest 30 minutes."""
    minutes = dt.minute
    if minutes < 15:
        return dt.replace(minute=0, second=0, microsecond=0)
    elif minutes < 45:
        return dt.replace(minute=30, second=0, microsecond=0)
    else:
        return (dt + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

def format_time_header(dt):
    """Format as 24MAY/0200 UTC"""
    return dt.strftime("%d%b/%H%M UTC").upper()

def get_wind_at_offset(hourly, current_time_str, hours_offset):
    """Return (speed, direction) closest to current + offset hours."""
    if not hourly or not hourly.get("time"):
        return None, None
    try:
        base = datetime.fromisoformat(current_time_str.replace("Z", ""))
        target = base + timedelta(hours=hours_offset)
        target_rounded = round_to_nearest_30(target)

        times = [datetime.fromisoformat(t.replace("Z", "")) for t in hourly["time"]]
        speeds = hourly.get("wind_speed_80m", [])
        dirs = hourly.get("wind_direction_80m", [])

        # Find closest hourly slot to the rounded target
        best_idx = min(range(len(times)), key=lambda i: abs((times[i] - target_rounded).total_seconds()))
        if best_idx < len(speeds) and best_idx < len(dirs):
            return speeds[best_idx], dirs[best_idx]
    except Exception:
        pass
    return None, None

def format_wind_pair(speed, direction):
    """Format as direction/speed kt e.g. 240/2.2 kt"""
    if speed is None or direction is None:
        return "N/A"
    try:
        return f"{int(round(direction))}/{float(speed):.1f} kt"
    except Exception:
        return "N/A"

# ---------- Helper: Generate PDF (half-page layout) ----------
def generate_pdf(timestamp, texts, image_urls):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(12, 12, 12)

    # ===== PAGE 1 =====
    pdf.add_page()
    pdf.set_font("Helvetica", size=13)
    pdf.set_xy(12, 12)
    pdf.cell(0, 7, "Yan Weather Brief", ln=True, align="C")
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 5, timestamp, ln=True, align="C")

    try:
        img_resp = requests.get(image_urls[0][1], timeout=15)
        if img_resp.status_code == 200:
            pdf.image(BytesIO(img_resp.content), x=20, y=30, w=160)
    except Exception:
        pdf.set_xy(20, 40)
        pdf.cell(0, 5, "Himawari IR Enhanced - not available")

    try:
        img_resp = requests.get(image_urls[1][1], timeout=15)
        if img_resp.status_code == 200:
            pdf.image(BytesIO(img_resp.content), x=20, y=155, w=160)
    except Exception:
        pdf.set_xy(20, 165)
        pdf.cell(0, 5, "Citra Sebaran Asap - not available")

    # ===== PAGE 2 =====
    pdf.add_page()
    try:
        img_resp = requests.get(image_urls[2][1], timeout=15)
        if img_resp.status_code == 200:
            pdf.image(BytesIO(img_resp.content), x=20, y=15, w=160)
    except Exception:
        pdf.set_xy(20, 25)
        pdf.cell(0, 5, "BMKG Prakiraan Angin - not available")

    # Text starts ~5 lines higher on page 2 only (was 155, now 134)
    pdf.set_xy(12, 134)
    pdf.set_font("Helvetica", size=8)
    for line in texts:
        safe = (line
                .replace("–", "-")
                .replace("—", "-")
                .replace("°", " deg")
                .replace("•", " - ")
                .encode("ascii", "ignore")
                .decode("ascii"))
        try:
            pdf.multi_cell(0, 4, safe)
            pdf.ln(0.3)
        except Exception:
            pdf.multi_cell(0, 4, "[text encoding error]")
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
taf_url = "https://aviationweather.gov/api/data/taf?ids=WAMM&format=json"
try:
    m_resp = requests.get(metar_url, timeout=12)
    metar_raw = "Not available"
    if m_resp.status_code == 200:
        m_data = m_resp.json()
        if m_data and isinstance(m_data, list) and len(m_data) > 0:
            metar_raw = m_data[0].get("rawOb", "Not available")
except Exception as e:
    metar_raw = f"Error: {e}"

try:
    t_resp = requests.get(taf_url, timeout=12)
    taf_raw = "Not available"
    if t_resp.status_code == 200:
        t_data = t_resp.json()
        if t_data and isinstance(t_data, list) and len(t_data) > 0:
            taf_raw = t_data[0].get("rawTAF", "Not available")
except Exception as e:
    taf_raw = f"Error: {e}"

pdf_texts.append(taf_raw)
pdf_texts.append(metar_raw)
pdf_texts.append("")

# WAMM BMKG bandara
wamm_bmkg_data, wamm_bmkg_err = scrape_bandara("WAMM")
wamm_bmkg_text = format_airport_text(wamm_bmkg_data) if wamm_bmkg_data else f"Not available ({wamm_bmkg_err})"
pdf_texts.append(wamm_bmkg_text)
pdf_texts.append("")

# WAFF
pdf_texts.append("WAFF - Mutiara SIS Al-Jufrie (Palu)")
waff_data, waff_err = scrape_bandara("WAFF")
waff_text = format_airport_text(waff_data) if waff_data else f"Not available ({waff_err})"
pdf_texts.append(waff_text)
pdf_texts.append("")

# WAFW
pdf_texts.append("WAFW - Syukuran Aminuddin Amir Airport (Luwuk)")
wafw_data, wafw_err = scrape_bandara("WAFW")
wafw_text = format_airport_text(wafw_data) if wafw_data else f"Not available ({wafw_err})"
pdf_texts.append(wafw_text)
pdf_texts.append("")

# WAFP
pdf_texts.append("WAFP - Kasiguncu Airport (Poso)")
wafp_data, wafp_err = scrape_bandara("WAFP")
wafp_text = format_airport_text(wafp_data) if wafp_data else f"Not available ({wafp_err})"
pdf_texts.append(wafp_text)
pdf_texts.append("")

# WAEE
pdf_texts.append("WAEE - Sultan Babullah Airport (Ternate)")
waee_data, waee_err = scrape_bandara("WAEE")
waee_text = format_airport_text(waee_data) if waee_data else f"Not available ({waee_err})"
pdf_texts.append(waee_text)
pdf_texts.append("")

# YAN Locations
pdf_texts.append("YAN LOCATIONS")
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

# ---------- Open-Meteo Wind Locations ----------
openmeteo_locations = {
    "Wontowu": (-1.221833, 121.646667),
    "Paramba": (-1.3715, 121.782833),
    "Padalempe": (-1.396167, 121.6735),
    "Kolakolamon": (-1.116667, 122.116167),
    "Moitoitom": (-0.911117, 122.29),
    "Waimiha": (-1.899667, 124.720333),
    "Lili": (1.265833, 128.703),
}

pdf_texts.append("")
pdf_texts.append("OPEN-METEO WIND (80 m AGL)")
openmeteo_rows = []
time_headers = ["Current", "—", "—"]  # will be updated on first successful call

for name, (lat, lon) in openmeteo_locations.items():
    current, hourly, err = get_openmeteo_wind(lat, lon)
    if not current or not current.get("time"):
        openmeteo_rows.append({
            "Location": name,
            "Lat/Lon": f"{lat:.4f}, {lon:.4f}",
            "Current": "N/A",
            "—": "N/A",
            "— ": "N/A",
            "Error": err or "No data"
        })
        pdf_texts.append(f"{name} ({lat:.4f}, {lon:.4f}): Not available")
        continue

    current_time_str = current.get("time")
    try:
        base_dt = datetime.fromisoformat(current_time_str.replace("Z", ""))
        t2 = round_to_nearest_30(base_dt + timedelta(hours=2))
        t4 = round_to_nearest_30(base_dt + timedelta(hours=4))
        if time_headers[1] == "—":
            time_headers = [
                "Current",
                format_time_header(t2),
                format_time_header(t4)
            ]
    except Exception:
        t2 = t4 = None

    # Current (from current endpoint)
    cur_spd = current.get("wind_speed_80m")
    cur_dir = current.get("wind_direction_80m")
    cur_str = format_wind_pair(cur_spd, cur_dir)

    # +2 h and +4 h from hourly
    spd2, dir2 = get_wind_at_offset(hourly, current_time_str, 2)
    spd4, dir4 = get_wind_at_offset(hourly, current_time_str, 4)
    str2 = format_wind_pair(spd2, dir2)
    str4 = format_wind_pair(spd4, dir4)

    openmeteo_rows.append({
        "Location": name,
        "Lat/Lon": f"{lat:.4f}, {lon:.4f}",
        time_headers[0]: cur_str,
        time_headers[1]: str2,
        time_headers[2]: str4,
    })

    pdf_texts.append(
        f"{name} ({lat:.4f}, {lon:.4f}) | "
        f"Current: {cur_str} | "
        f"{time_headers[1]}: {str2} | "
        f"{time_headers[2]}: {str4}"
    )

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
st.text(taf_raw)
st.text(metar_raw)
st.write("")  # line space
st.write(wamm_bmkg_text)
st.caption("Sources: https://aviationweather.gov/api/ (TAF/METAR) and https://www.bmkg.go.id/cuaca/bandara/WAMM")

st.header("WAFF - Mutiara SIS Al-Jufrie (Palu)")
st.write(waff_text)
st.caption("Source: https://www.bmkg.go.id/cuaca/bandara/WAFF")

st.header("WAFW - Syukuran Aminuddin Amir Airport (Luwuk)")
st.write(wafw_text)
st.caption("Source: https://www.bmkg.go.id/cuaca/bandara/WAFW")

st.header("WAFP - Kasiguncu Airport (Poso)")
st.write(wafp_text)
st.caption("Source: https://www.bmkg.go.id/cuaca/bandara/WAFP")

st.header("WAEE - Sultan Babullah Airport (Ternate)")
st.write(waee_text)
st.caption("Source: https://www.bmkg.go.id/cuaca/bandara/WAEE")

st.header("YAN LOCATIONS")
if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
st.caption("Source: https://api.bmkg.go.id/publik/prakiraan-cuaca")

st.header("OPEN-METEO WIND")
if openmeteo_rows:
    # Ensure consistent columns even if some failed
    om_df = pd.DataFrame(openmeteo_rows)
    # Drop any temporary error columns if present for display
    display_cols = [c for c in om_df.columns if c not in ("Error", "—", "— ")]
    st.dataframe(om_df[display_cols], use_container_width=True, hide_index=True)
st.caption("Forecast wind at 80 m AGL. Source: https://api.open-meteo.com/v1/forecast")

st.header("WINDY.COM")
windy_embed = "https://embed.windy.com/embed2.html?lat=-1.0&lon=121.0&detailLat=-1.0&detailLon=121.0&width=650&height=450&zoom=6&level=surface&overlay=rain&product=ecmwf&menu=&message=&marker=&calendar=now&pressure=&type=map&location=coordinates&detail=&metricWind=default&metricTemp=default&radarRange=-1"
st.components.v1.iframe(windy_embed, height=500)
st.caption("Source: https://www.windy.com (cannot be saved to PDF)")

st.download_button(
    label="Save PDF",
    data=pdf_bytes,
    file_name=f"Yan_Weather_Brief_{now.replace(' ', '_').replace(':', '')}.pdf",
    mime="application/pdf",
    key="pdf_bottom"
)
