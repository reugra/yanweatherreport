import streamlit as st
import requests
from datetime import datetime
from fpdf import FPDF
from bs4 import BeautifulSoup
import io

st.set_page_config(page_title="Yan Weather Report", layout="wide")

st.title("Yan Weather Report – Sulawesi VFR")
st.caption("One-click aviation weather for central & north Sulawesi")

if st.button("Get Weather", type="primary"):
    with st.spinner("Fetching latest data..."):
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        st.write(f"**Report generated:** {now}")

        # ---------- WAMM (NOAA) ----------
        st.header("WAMM – Sam Ratulangi (Manado)")
        try:
            metar_url = "https://aviationweather.gov/api/data/metar?ids=WAMM&format=json"
            taf_url = "https://aviationweather.gov/api/data/taf?ids=WAMM&format=json"
            metar = requests.get(metar_url, timeout=10).json()
            taf = requests.get(taf_url, timeout=10).json()

            if metar:
                m = metar[0]
                st.subheader("METAR (decoded)")
                st.write(f"**Issued:** {m.get('obsTime', 'N/A')}")
                st.write(f"**Wind:** {m.get('wdir', 'N/A')}° at {m.get('wspd', 'N/A')} kt")
                st.write(f"**Visibility:** {m.get('visib', 'N/A')}")
                st.write(f"**Clouds:** {m.get('clouds', 'N/A')}")
                st.write(f"**Temp/Dew:** {m.get('temp', 'N/A')}°C / {m.get('dewp', 'N/A')}°C")
                st.write(f"**QNH:** {m.get('altim', 'N/A')} hPa")
                with st.expander("Raw METAR"):
                    st.code(m.get("rawOb", "N/A"))
            else:
                st.warning("WAMM METAR not available")

            if taf:
                t = taf[0]
                st.subheader("TAF (decoded)")
                st.write(f"**Issued:** {t.get('issueTime', 'N/A')}")
                st.write(f"**Valid:** {t.get('validTimeFrom', 'N/A')} – {t.get('validTimeTo', 'N/A')}")
                st.write(f"**Base forecast:** {t.get('fcsts', [{}])[0]}")
                with st.expander("Raw TAF"):
                    st.code(t.get("rawTAF", "N/A"))
            else:
                st.warning("WAMM TAF not available")
        except Exception as e:
            st.error(f"WAMM data error: {e}")

        st.divider()

        # ---------- WAFF (BMKG page) ----------
        st.header("WAFF – Mutiara SIS Al-Jufrie (Palu)")
        try:
            waff_url = "https://www.bmkg.go.id/cuaca/bandara/WAFF"
            r = requests.get(waff_url, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            # Simple extraction of key current values (structure may vary)
            text = soup.get_text(separator=" | ")
            st.write("**Current conditions from BMKG:**")
            st.info(text[:1500])  # show relevant portion
            st.caption("Source: bmkg.go.id/cuaca/bandara/WAFF")
        except Exception as e:
            st.error(f"WAFF data error: {e}")

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

        # BMKG wind charts (attempt)
        st.subheader("BMKG Wind Charts (850 hPa & 700 hPa)")
        bmkg_winds = [
            ("850 hPa", "https://web-aviation.bmkg.go.id/model/windtemp/850_00.png"),
            ("700 hPa", "https://web-aviation.bmkg.go.id/model/windtemp/700_00.png"),
        ]
        for label, url in bmkg_winds:
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", ""):
                    st.write(f"**{label}**")
                    st.image(resp.content, use_container_width=True)
                else:
                    st.warning(f"Wind data from BMKG not accessible ({label})")
            except:
                st.warning(f"Wind data from BMKG not accessible ({label})")

        # ---------- PDF ----------
        st.divider()
        st.subheader("Download PDF")
        # Simple PDF (text summary + note about images)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, f"Yan Weather Report – {now}", ln=True)
        pdf.cell(0, 10, "WAMM and WAFF data + satellite + winds", ln=True)
        pdf.cell(0, 10, "Full interactive version available in the web app.", ln=True)
        pdf_output = io.BytesIO()
        pdf.output(pdf_output)
        st.download_button(
            "Download PDF",
            data=pdf_output.getvalue(),
            file_name=f"YanWeather_{now.replace(' ','_').replace(':','')}.pdf",
            mime="application/pdf",
        )
