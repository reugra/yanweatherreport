import streamlit as st
import requests
from datetime import datetime
from fpdf import FPDF
from bs4 import BeautifulSoup
import io

st.set_page_config(page_title="Yan Weather Report", layout="wide")

st.title("Yan Weather Report – Sulawesi VFR")
st.caption("One-click aviation weather for central & north Sulawesi")

# Browser-like headers to reduce 403 blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bmkg.go.id/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

if st.button("Get Weather", type="primary"):
    with st.spinner("Fetching latest data..."):
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        st.write(f"**Report generated:** {now}")

        # ---------- WAMM (NOAA) ----------
        st.header("WAMM – Sam Ratulangi (Manado)")
        metar_url = "https://aviationweather.gov/api/data/metar?ids=WAMM&format=json"
        taf_url = "https://aviationweather.gov/api/data/taf?ids=WAMM&format=json"
        st.caption(f"Sources: {metar_url} and {taf_url}")

        try:
            metar_resp = requests.get(metar_url, timeout=10)
            taf_resp = requests.get(taf_url, timeout=10)
            metar = metar_resp.json() if metar_resp.status_code == 200 else []
            taf = taf_resp.json() if taf_resp.status_code == 200 else []

            if metar:
                st.subheader("METAR")
                st.code(metar[0].get("rawOb", "Not available"))
            else:
                st.warning("WAMM METAR not available")

            if taf:
                st.subheader("TAF")
                st.code(taf[0].get("rawTAF", "Not available"))
            else:
                st.warning("WAMM TAF not available")
        except Exception as e:
            st.error(f"WAMM data error: {e}")

        st.divider()

        # ---------- WAFF (BMKG page) ----------
        st.header("WAFF – Mutiara SIS Al-Jufrie (Palu)")
        waff_url = "https://www.bmkg.go.id/cuaca/bandara/WAFF"
        st.caption(f"Source: {waff_url}")
        try:
            r = requests.get(waff_url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            full_text = soup.get_text(separator="\n", strip=True)
            # Show a cleaned relevant portion
            lines = [line.strip() for line in full_text.split("\n") if line.strip()]
            relevant = "\n".join(lines[:40])  # first ~40 non-empty lines usually cover the weather
            st.subheader("Current conditions & short forecast (BMKG)")
            st.text(relevant)
            with st.expander("Full extracted text"):
                st.text(full_text[:3000])
        except Exception as e:
            st.error(f"WAFF data error: {e}")
            st.info("If this persists, please copy the main weather text from the page and paste it here so we can adjust the extraction.")

        st.divider()

        # ---------- Satellite images ----------
        st.header("Satellite")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Himawari IR Enhanced")
            st.image("https://inderaja.bmkg.go.id/IMAGE/HIMA/H08_EH_Indonesia.png", use_container_width=True)
        with col2:
            st.subheader("Citra Sebaran Asap")
            st.image("https://inderaja.bmkg.go.id/Trajektori/Asap.png", use_container_width=True)

        st.divider()

        # ---------- Winds ----------
        st.header("Low-level Winds")

        # Primary: Windy embed
        st.subheader("Windy (primary – interactive)")
        windy_html = '''
        <iframe src="https://embed.windy.com/embed2.html?lat=-1.5&lon=121.5&zoom=6&level=surface&overlay=wind&menu=&message=true&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=-1.5&detailLon=121.5&metricWind=kt&metricTemp=%C2%B0C&radarRange=-1"
                width="100%" height="500" frameborder="0"></iframe>
        '''
        st.components.v1.html(windy_html, height=520)

        # BMKG wind charts (attempt with headers)
        st.subheader("BMKG Wind Charts (850 hPa & 700 hPa)")
        bmkg_winds = [
            ("850 hPa", "https://web-aviation.bmkg.go.id/model/windtemp/850_00.png"),
            ("700 hPa", "https://web-aviation.bmkg.go.id/model/windtemp/700_00.png"),
        ]
        wind_headers = HEADERS.copy()
        wind_headers["Referer"] = "https://web-aviation.bmkg.go.id/"

        for label, url in bmkg_winds:
            try:
                resp = requests.get(url, headers=wind_headers, timeout=10)
                if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", "").lower():
                    st.write(f"**{label}**")
                    st.image(resp.content, use_container_width=True)
                else:
                    st.warning(f"Wind data from BMKG not accessible ({label}) – status {resp.status_code}")
            except Exception as e:
                st.warning(f"Wind data from BMKG not accessible ({label})")

        # ---------- PDF ----------
        st.divider()
        st.subheader("Download PDF")

        # Build simple ASCII-only summary for PDF
        pdf_text = f"Yan Weather Report - {now}\n"
        pdf_text += "WAMM and WAFF data + satellite + winds\n"
        pdf_text += "Full interactive version available in the web app.\n"
        pdf_text += "Windy is the primary wind source.\n"

        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            for line in pdf_text.split("\n"):
                pdf.cell(0, 10, line, ln=True)
            pdf_bytes = pdf.output(dest="S").encode("latin-1", errors="replace")
            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=f"YanWeather_{now.replace(' ', '_').replace(':', '')}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error(f"PDF generation failed: {e}")
