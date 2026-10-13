import streamlit as st
import requests
from datetime import datetime
from fpdf import FPDF
from io import BytesIO
import base64

st.set_page_config(page_title="Sulawesi VFR Weather", layout="wide")
st.title("Sulawesi VFR Weather Report")
st.caption("One-click briefing for VFR operations below 10,000 ft around Central & North Sulawesi")

if st.button("Get Weather", type="primary"):
    with st.spinner("Fetching latest data..."):
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        st.success(f"Report generated: {timestamp}")

        # 1. METAR & TAF
        st.header("1. METAR & TAF — WAMM & WAFF")
        metar_url = "https://aviationweather.gov/api/data/metar?ids=WAMM,WAFF&format=json"
        taf_url = "https://aviationweather.gov/api/data/taf?ids=WAMM,WAFF&format=json"
        
        try:
            metars = requests.get(metar_url, timeout=15).json()
            tafs = requests.get(taf_url, timeout=15).json()
        except Exception as e:
            st.error(f"Could not fetch METAR/TAF: {e}")
            metars, tafs = [], []

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("WAMM")
            wamm_m = next((m for m in metars if m.get("icaoId") == "WAMM"), None)
            wamm_t = next((t for t in tafs if t.get("icaoId") == "WAMM"), None)
            if wamm_m:
                st.code(wamm_m.get("rawOb", "No METAR"), language=None)
                st.write(f"Flight Category: **{wamm_m.get('fltCat', 'N/A')}** | Temp: {wamm_m.get('temp')}°C | Wind: {wamm_m.get('wspd')} kt | Vis: {wamm_m.get('visib')}")
            else:
                st.warning("No METAR available")
            if wamm_t:
                st.code(wamm_t.get("rawTAF", "No TAF"), language=None)
            else:
                st.warning("No TAF available")

        with col2:
            st.subheader("WAFF")
            waff_m = next((m for m in metars if m.get("icaoId") == "WAFF"), None)
            waff_t = next((t for t in tafs if t.get("icaoId") == "WAFF"), None)
            if waff_m:
                st.code(waff_m.get("rawOb", "No METAR"), language=None)
                st.write(f"Flight Category: **{waff_m.get('fltCat', 'N/A')}** | Temp: {waff_m.get('temp')}°C | Wind: {waff_m.get('wspd')} kt | Vis: {waff_m.get('visib')}")
            else:
                st.warning("No METAR available")
            if waff_t:
                st.code(waff_t.get("rawTAF", "No TAF"), language=None)
            else:
                st.warning("No TAF available")

        # 2 & 3. Satellites
        st.header("2. Himawari IR Enhanced (BMKG)")
        himawari = "https://inderaja.bmkg.go.id/IMAGE/HIMA/H08_EH_Indonesia.png"
        st.image(himawari, caption="Himawari-9 IR Enhanced — Indonesia (source: BMKG)", use_container_width=True)

        st.header("3. Citra Sebaran Asap (BMKG)")
        asap = "https://inderaja.bmkg.go.id/Trajektori/Asap.png"
        st.image(asap, caption="Smoke/Haze Distribution (source: BMKG)", use_container_width=True)

        # 5. Low-level wind charts (BOM Area E — covers all of Indonesia)
        st.header("5. Low-Level Wind/Temp Charts (BOM ICAO Area E — FL050 / 850 hPa)")
        st.caption("Official WAFS charts covering the entire Indian Ocean region including all of Indonesia. Choose the most recent valid time.")
        
        wind_charts = {
            "00Z": "https://www.bom.gov.au/fwo/aviation/IDY01419.png",
            "06Z": "https://www.bom.gov.au/fwo/aviation/IDY01420.png",
            "12Z": "https://www.bom.gov.au/fwo/aviation/IDY01421.png",
            "18Z": "https://www.bom.gov.au/fwo/aviation/IDY01422.png",
            "+30 hrs": "https://www.bom.gov.au/fwo/aviation/IDY01423.png",
        }
        
        selected_time = st.selectbox("Select chart time", list(wind_charts.keys()), index=0)
        st.image(wind_charts[selected_time], caption=f"BOM Area E FL050 Wind/Temp — Valid {selected_time}", use_container_width=True)

        # 4 & 6. Radar + other useful
        st.header("4 & 6. Radar, Interactive Winds & Other VFR Resources")
        st.markdown("""
        **Radar covering Central/North Sulawesi:**  
        - [Windy Radar + Wind](https://www.windy.com/?120.0,0.9,7) (interactive — best real-time option)  
        - [RainViewer](https://www.rainviewer.com/)  

        **Other useful free resources:**  
        - [BMKG Cuaca Map](https://cuaca.bmkg.go.id/map) (wind layers at surface / 850 hPa etc.)  
        - [Aviation Weather Center](https://aviationweather.gov/) (SIGMETs, more)  
        - [BOM full Area E charts](https://www.bom.gov.au/aviation/charts/wind-temperature/)  
        """)

        # PDF generation
        def create_pdf():
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "Sulawesi VFR Weather Report", ln=True, align="C")
            pdf.set_font("Helvetica", size=10)
            pdf.cell(0, 8, f"Generated: {timestamp}", ln=True, align="C")
            pdf.ln(5)

            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "METAR & TAF", ln=True)
            pdf.set_font("Helvetica", size=9)
            
            for label, m, t in [("WAMM", wamm_m, wamm_t), ("WAFF", waff_m, waff_t)]:
                pdf.cell(0, 6, f"{label}:", ln=True)
                if m:
                    pdf.multi_cell(0, 5, m.get("rawOb", "No METAR"))
                    pdf.cell(0, 5, f"Cat: {m.get('fltCat','N/A')} | Temp: {m.get('temp')}°C | Wind: {m.get('wspd')}kt | Vis: {m.get('visib')}", ln=True)
                if t:
                    pdf.multi_cell(0, 5, t.get("rawTAF", "No TAF"))
                pdf.ln(3)

            # Images
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Himawari IR Enhanced (BMKG)", ln=True)
            try:
                pdf.image(himawari, w=180)
            except:
                pdf.cell(0, 5, "Image unavailable", ln=True)

            pdf.add_page()
            pdf.cell(0, 8, "Citra Sebaran Asap (BMKG)", ln=True)
            try:
                pdf.image(asap, w=180)
            except:
                pdf.cell(0, 5, "Image unavailable", ln=True)

            pdf.add_page()
            pdf.cell(0, 8, f"BOM Area E FL050 Wind/Temp ({selected_time})", ln=True)
            try:
                pdf.image(wind_charts[selected_time], w=180)
            except:
                pdf.cell(0, 5, "Image unavailable", ln=True)

            pdf.add_page()
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(0, 6, "Radar & other resources:\n- Windy: https://www.windy.com/?120.0,0.9,7\n- BMKG Cuaca Map: https://cuaca.bmkg.go.id/map\n- Full BOM charts: https://www.bom.gov.au/aviation/charts/wind-temperature/")

            return bytes(pdf.output())

        pdf_bytes = create_pdf()
        st.download_button(
            label="Download PDF Report",
            data=pdf_bytes,
            file_name=f"Sulawesi_VFR_Weather_{datetime.utcnow().strftime('%Y%m%d_%H%M')}_UTC.pdf",
            mime="application/pdf"
        )

st.markdown("---")
st.caption("Data sources: NOAA Aviation Weather Center, BMKG, BOM Australia. Always cross-check official sources before flight. For VFR use only.")
