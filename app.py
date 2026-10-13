import streamlit as st
import requests
from datetime import datetime
from fpdf import FPDF
from bs4 import BeautifulSoup
from io import BytesIO

# curl_cffi for better TLS fingerprinting on BMKG pages
try:
    from curl_cffi import requests as curl_requests
    CURL_AVAILABLE = True
except ImportError:
    CURL_AVAILABLE = False
    st.warning("curl_cffi not installed – BMKG attempts will use normal requests")

st.set_page_config(page_title="Yan Weather Report", layout="wide")
st.title("Yan Weather Report - Sulawesi VFR")
st.caption("One-click aviation weather for central & north Sulawesi")

if st.button("Get Weather", type="primary"):
    with st.spinner("Fetching latest data..."):
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        st.write(f"**Report generated:** {now}")

        report_texts = []
        image_urls = []

        # ---------- WAMM (NOAA – normal requests) ----------
        st.header("WAMM - Sam Ratulangi (Manado)")
        metar_url = "https://aviationweather.gov/api/data/metar?ids=WAMM&format=json"
        taf_url = "https://aviationweather.gov/api/data/taf?ids=WAMM&format=json"
        st.caption(f"Sources: {metar_url} and {taf_url}")
        report_texts.append(f"Sources: {metar_url} and {taf_url}")

        try:
            metar = requests.get(metar_url, timeout=10).json()
            taf = requests.get(taf_url, timeout=10).json()
            if metar:
                raw_metar = metar[0].get("rawOb", "Not available")
                st.subheader("METAR")
                st.code(raw_metar, language=None)
                report_texts.append(f"WAMM METAR:\n{raw_metar}")
            if taf:
                raw_taf = taf[0].get("rawTAF", "Not available")
                st.subheader("TAF")
                st.code(raw_taf, language=None)
                report_texts.append(f"WAMM TAF:\n{raw_taf}")
        except Exception as e:
            st.error(f"WAMM error: {e}")

        st.divider()

        # ---------- WAFF with curl_cffi ----------
        st.header("WAFF - Mutiara SIS Al-Jufrie (Palu)")
        waff_url = "https://www.bmkg.go.id/cuaca/bandara/WAFF"
        st.caption(f"Trying curl_cffi on: {waff_url}")
        waff_success = False

        if CURL_AVAILABLE:
            try:
                r = curl_requests.get(waff_url, impersonate="chrome", timeout=30)
                st.write(f"WAFF status: {r.status_code}")
                if r.status_code == 200 and len(r.text) > 800:
                    soup = BeautifulSoup(r.text, "html.parser")
                    full_text = soup.get_text(separator="\n", strip=True)
                    lines = [ln.strip() for ln in full_text.split("\n") if ln.strip()]
                    relevant = "\n".join(lines[:80])
                    st.subheader("BMKG current conditions (curl_cffi)")
                    st.text(relevant if relevant else "No useful text extracted")
                    report_texts.append(f"WAFF BMKG (excerpt):\n{relevant[:600]}")
                    with st.expander("Full extracted text"):
                        st.text(full_text[:5000])
                    waff_success = True
                else:
                    st.warning(f"curl_cffi got status {r.status_code} or little content")
            except Exception as e:
                st.warning(f"curl_cffi failed for WAFF: {e}")
        else:
            st.info("curl_cffi not available")

        if not waff_success:
            # Open-Meteo fallback
            try:
                om_url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": -0.918,
                    "longitude": 119.910,
                    "current": "temperature_2m,wind_speed_10m,wind_direction_10m,visibility,pressure_msl,cloud_cover,weather_code",
                    "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m,visibility,cloud_cover,precipitation",
                    "forecast_days": 1,
                    "wind_speed_unit": "kn",
                    "timezone": "Asia/Makassar",
                }
                om = requests.get(om_url, params=params, timeout=15).json()
                curr = om.get("current", {})
                st.subheader("Open-Meteo fallback (current)")
                st.write(f"**Temp:** {curr.get('temperature_2m')} °C")
                st.write(f"**Wind:** {curr.get('wind_direction_10m')}° at {curr.get('wind_speed_10m')} kt")
                st.write(f"**Visibility:** {curr.get('visibility')} m")
                st.write(f"**Cloud cover:** {curr.get('cloud_cover')} %")
                st.write(f"**Pressure:** {curr.get('pressure_msl')} hPa")
                report_texts.append(
                    f"WAFF Open-Meteo current: Temp {curr.get('temperature_2m')}C, "
                    f"Wind {curr.get('wind_direction_10m')}°/{curr.get('wind_speed_10m')}kt, "
                    f"Vis {curr.get('visibility')}m, Clouds {curr.get('cloud_cover')}%"
                )
            except Exception as e2:
                st.error(f"Open-Meteo also failed: {e2}")

        st.divider()

        # ---------- Satellites ----------
        st.header("Satellite")
        sat1 = "https://inderaja.bmkg.go.id/IMAGE/HIMA/H08_EH_Indonesia.png"
        sat2 = "https://inderaja.bmkg.go.id/Trajektori/Asap.png"
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Himawari IR Enhanced")
            st.image(sat1, use_container_width=True)
            image_urls.append(("Himawari IR Enhanced", sat1))
        with col2:
            st.subheader("Citra Sebaran Asap")
            st.image(sat2, use_container_width=True)
            image_urls.append(("Citra Sebaran Asap", sat2))

        st.divider()

        # ---------- Winds ----------
        st.header("Low-level Winds")
        st.subheader("Windy (primary - interactive)")
        windy_html = '''
        <iframe src="https://embed.windy.com/embed2.html?lat=-1.5&lon=121.5&zoom=6&level=surface&overlay=wind&menu=&message=true&type=map&location=coordinates&detailLat=-1.5&detailLon=121.5&metricWind=kt&metricTemp=%C2%B0C"
                width="100%" height="500" frameborder="0"></iframe>
        '''
        st.components.v1.html(windy_html, height=520)

        # BMKG wind charts with curl_cffi
        st.subheader("BMKG Wind Charts (curl_cffi attempt)")
        bmkg_winds = [
            ("850 hPa", "https://web-aviation.bmkg.go.id/model/windtemp/850_00.png"),
            ("700 hPa", "https://web-aviation.bmkg.go.id/model/windtemp/700_00.png"),
        ]
        for label, url in bmkg_winds:
            success = False
            if CURL_AVAILABLE:
                try:
                    resp = curl_requests.get(url, impersonate="chrome", timeout=20)
                    if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", "").lower():
                        st.write(f"**{label}**")
                        st.image(resp.content, use_container_width=True)
                        image_urls.append((f"BMKG {label}", url))
                        success = True
                    else:
                        st.warning(f"Wind data from BMKG not accessible ({label}) – status {resp.status_code}")
                except Exception as e:
                    st.warning(f"Wind data from BMKG not accessible ({label}): {e}")
            if not success:
                st.warning(f"Wind data from BMKG not accessible ({label})")

        # ---------- PDF ----------
        st.divider()
        st.subheader("Download PDF")
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=11)
            pdf.cell(0, 8, f"Yan Weather Report - {now}", ln=True)
            pdf.ln(4)
            for block in report_texts:
                # Basic ASCII-safe text
                safe_block = block.encode("latin-1", errors="replace").decode("latin-1")
                pdf.multi_cell(0, 6, safe_block)
                pdf.ln(3)

            for title, url in image_urls:
                try:
                    img_resp = requests.get(url, timeout=15)
                    if img_resp.status_code == 200:
                        pdf.add_page()
                        pdf.set_font("Helvetica", size=12)
                        pdf.cell(0, 10, title, ln=True)
                        pdf.image(BytesIO(img_resp.content), x=10, y=30, w=190)
                except Exception:
                    pass

            pdf_bytes = bytes(pdf.output())
            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=f"YanWeather_{now.replace(' ', '_').replace(':', '')}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error(f"PDF generation failed: {e}")
