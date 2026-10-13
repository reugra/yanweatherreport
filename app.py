import streamlit as st
import requests
from datetime import datetime
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="Yan Weather Report", layout="wide")
st.title("Yan Weather Report - Sulawesi VFR")
st.caption("One-click aviation weather for central & north Sulawesi")

if st.button("Get Weather", type="primary"):
    with st.spinner("Fetching latest data..."):
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        st.write(f"**Report generated:** {now}")

        report_texts = []
        image_urls = []

        # ---------- WAMM (NOAA) ----------
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

        # ---------- WAFF via BMKG official API ----------
        st.header("WAFF area - BMKG official forecast API (Palu)")
        adm4 = "72.71.06.1001"  # Kota Palu – Nunu / Tatanga area (change if preferred)
        api_url = f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={adm4}"
        st.caption(f"Source: {api_url}")
        report_texts.append(f"WAFF/Palu BMKG API: {api_url}")

        try:
            resp = requests.get(api_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                cuaca_days = data.get("data", [{}])[0].get("cuaca", [])
                if cuaca_days:
                    st.subheader("BMKG 3-hourly forecast")
                    shown = 0
                    for day in cuaca_days:
                        for item in day:
                            if shown >= 8:
                                break
                            local = item.get("local_datetime", "")
                            temp = item.get("t", "")
                            ws = item.get("ws", "")
                            wd = item.get("wd", "")
                            tcc = item.get("tcc", "")
                            desc = item.get("weather_desc_en") or item.get("weather_desc", "")
                            line = f"{local} | {temp}°C | Wind {wd} {ws} km/h | Clouds {tcc}% | {desc}"
                            st.write(line)
                            report_texts.append(line)
                            shown += 1
                        if shown >= 8:
                            break
                else:
                    st.warning("BMKG API returned no forecast data")
            else:
                st.warning(f"BMKG API status {resp.status_code}")
        except Exception as e:
            st.warning(f"BMKG API error: {e}")

        # Open-Meteo fallback
        try:
            om_url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": -0.918,
                "longitude": 119.910,
                "current": "temperature_2m,wind_speed_10m,wind_direction_10m,visibility,pressure_msl,cloud_cover",
                "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m,visibility,cloud_cover",
                "forecast_days": 1,
                "wind_speed_unit": "kn",
                "timezone": "Asia/Makassar",
            }
            om = requests.get(om_url, params=params, timeout=15).json()
            curr = om.get("current", {})
            st.subheader("Open-Meteo current (fallback)")
            st.write(f"**Temp:** {curr.get('temperature_2m')} °C")
            st.write(f"**Wind:** {curr.get('wind_direction_10m')}° at {curr.get('wind_speed_10m')} kt")
            st.write(f"**Visibility:** {curr.get('visibility')} m")
            st.write(f"**Cloud cover:** {curr.get('cloud_cover')} %")
            report_texts.append(
                f"WAFF Open-Meteo: Temp {curr.get('temperature_2m')}C, "
                f"Wind {curr.get('wind_direction_10m')}°/{curr.get('wind_speed_10m')}kt, "
                f"Vis {curr.get('visibility')}m"
            )
        except Exception as e:
            st.error(f"Open-Meteo error: {e}")

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

        # BMKG Prakiraan Angin image
        st.subheader("BMKG Prakiraan Angin (3000 feet streamline)")
        angin_url = "https://dataweb.bmkg.go.id/cuaca/angin/streamline-d10.jpg"
        try:
            img_resp = requests.get(angin_url, timeout=15)
            if img_resp.status_code == 200 and "image" in img_resp.headers.get("Content-Type", "").lower():
                st.image(img_resp.content, use_container_width=True)
                image_urls.append(("BMKG Prakiraan Angin", angin_url))
            else:
                st.warning(f"BMKG Prakiraan Angin not accessible – status {img_resp.status_code}")
        except Exception as e:
            st.warning(f"BMKG Prakiraan Angin not accessible: {e}")

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
