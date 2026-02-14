"""
Equity Research PDF Analyzer Dashboard
"""

import streamlit as st
import pandas as pd
import re
import io
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

# PDF library import with fallback
PDF_LIBRARY = None
try:
    import pdfplumber
    PDF_LIBRARY = "pdfplumber"
except ImportError:
    try:
        from pypdf import PdfReader
        PDF_LIBRARY = "pypdf"
    except ImportError:
        try:
            import PyPDF2
            PDF_LIBRARY = "PyPDF2"
        except ImportError:
            PDF_LIBRARY = None


@dataclass
class ResearchReport:
    company_name: str = ""
    ticker: str = ""
    report_date: str = ""
    analyst_firm: str = ""
    rating: str = ""
    current_price: float = 0.0
    target_price: float = 0.0
    previous_target: float = 0.0
    upside_potential: float = 0.0
    market_cap: str = ""
    free_float: float = 0.0
    week_52_high: float = 0.0
    week_52_low: float = 0.0
    sector: str = ""
    key_highlights: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    valuation_metrics: Dict[str, Any] = field(default_factory=dict)
    esg_score: Dict[str, Any] = field(default_factory=dict)
    shareholding: Dict[str, Any] = field(default_factory=dict)


def extract_number(text):
    if not text:
        return None
    text = str(text).replace(',', '').replace('INR', '').replace('$', '').strip()
    match = re.search(r'-?\d+\.?\d*', text)
    return float(match.group()) if match else None


def extract_text_from_pdf(pdf_file):
    all_text = ""
    
    if PDF_LIBRARY == "pdfplumber":
        with pdfplumber.open(pdf_file) as pdf:
            for i, page in enumerate(pdf.pages):
                all_text += f"\n--- Page {i+1} ---\n{page.extract_text() or ''}"
    elif PDF_LIBRARY == "pypdf":
        from pypdf import PdfReader
        for i, page in enumerate(PdfReader(pdf_file).pages):
            all_text += f"\n--- Page {i+1} ---\n{page.extract_text() or ''}"
    elif PDF_LIBRARY == "PyPDF2":
        import PyPDF2
        for i, page in enumerate(PyPDF2.PdfReader(pdf_file).pages):
            all_text += f"\n--- Page {i+1} ---\n{page.extract_text() or ''}"
    
    return all_text


def parse_report(text):
    report = ResearchReport()
    
    # Company name
    for line in text.split('\n')[:30]:
        if any(x in line for x in ['Consumer', 'Ltd', 'Limited', 'Industries']):
            name = re.sub(r'[|].*', '', line).strip()
            if 3 < len(name) < 50:
                report.company_name = re.sub(r'\s+', ' ', name)
                break
    
    # Ticker
    m = re.search(r'([A-Z]{3,10})\s+IN\b', text)
    if m: report.ticker = m.group(1) + " IN"
    
    # Date
    m = re.search(r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})', text, re.I)
    if m: report.report_date = m.group(1)
    
    # Firm
    m = re.search(r'(ICICI Securities|Motilal Oswal|HDFC Securities|Kotak|JM Financial)', text, re.I)
    if m: report.analyst_firm = m.group(0)
    
    # Rating
    m = re.search(r'\b(BUY|SELL|HOLD|ADD|REDUCE|NEUTRAL)\b', text[:1000], re.I)
    if m: report.rating = m.group(1).upper()
    
    # CMP
    m = re.search(r'CMP[:\s]*(?:INR\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)', text, re.I)
    if m: report.current_price = extract_number(m.group(1)) or 0
    
    # Target
    m = re.search(r'Target\s*Price[:\s]*(?:INR\s*)?(\d+(?:,\d{3})*)', text, re.I)
    if m: report.target_price = extract_number(m.group(1)) or 0
    
    # Previous target
    m = re.search(r'Target.*?\((?:INR\s*)?(\d+)', text, re.I)
    if m: report.previous_target = extract_number(m.group(1)) or 0
    
    # Upside
    if report.current_price and report.target_price:
        report.upside_potential = ((report.target_price - report.current_price) / report.current_price) * 100
    
    # Market cap
    m = re.search(r'Market\s*Cap[^\d]*(\d+(?:\.\d+)?)\s*(bn|mn|cr)?', text, re.I)
    if m: report.market_cap = f"INR {m.group(1)}{m.group(2) or ''}"
    
    # 52W range
    m = re.search(r'52.*?Range[^\d]*(\d+)[^\d]+(\d+)', text, re.I)
    if m:
        report.week_52_high = extract_number(m.group(1)) or 0
        report.week_52_low = extract_number(m.group(2)) or 0
    
    # Free float
    m = re.search(r'Free\s*Float[^\d]*(\d+(?:\.\d+)?)', text, re.I)
    if m: report.free_float = extract_number(m.group(1)) or 0
    
    # ESG
    esg = re.search(r'ESG[\s\S]{0,400}', text, re.I)
    if esg:
        s = esg.group(0)
        for lbl, k in [('Environment', 'environment'), ('Social', 'social'), ('Governance', 'governance')]:
            m = re.search(rf'{lbl}[^\d]*(\d{{2}}\.\d)', s, re.I)
            if m and 0 < float(m.group(1)) <= 100:
                report.esg_score[k] = float(m.group(1))
    
    # Shareholding
    for p, k in [(r'Promoters?\s*[:\s]*(\d+(?:\.\d+)?)', 'Promoters'), (r'FIIs?\s*[:\s]*(\d+(?:\.\d+)?)', 'FIIs')]:
        m = re.search(p, text, re.I)
        if m: report.shareholding[k] = extract_number(m.group(1))
    
    # Valuation
    for p, k in [(r'P/E[^\d]*(\d+(?:\.\d+)?)', 'P/E'), (r'RoE[^\d]*(\d+(?:\.\d+)?)', 'RoE')]:
        m = re.search(p, text, re.I)
        if m: report.valuation_metrics[k] = extract_number(m.group(1))
    
    # Highlights
    report.key_highlights = [re.sub(r'\s+', ' ', m).strip() for m in re.findall(r'We\s+(?:expect|believe)[^.]{20,100}\.', text, re.I)][:3]
    
    # Risks
    m = re.search(r'Key\s*risks?[:\s]*(.*?)(?:\.|Valuation)', text, re.I)
    if m:
        report.risks = [re.sub(r'\s+', ' ', i).strip() for i in re.split(r'\d\)', m.group(1)) if len(i.strip()) > 8][:4]
    
    return report


def main():
    st.set_page_config(page_title="Stock Research Analyzer", page_icon="📊", layout="wide")
    st.title("📊 Equity Research PDF Analyzer")
    
    if PDF_LIBRARY:
        st.caption(f"✅ Using: {PDF_LIBRARY}")
    else:
        st.error("❌ Install PDF library: pip install pdfplumber")
        st.stop()
    
    uploaded = st.file_uploader("Upload Research PDF", type=['pdf'])
    
    if uploaded:
        with st.spinner("Analyzing..."):
            try:
                text = extract_text_from_pdf(uploaded)
                r = parse_report(text)
                
                st.header(f"📈 {r.company_name or 'Analysis'}")
                
                # Metrics
                c1, c2, c3, c4 = st.columns(4)
                icon = {'BUY': '🟢', 'ADD': '🟢', 'HOLD': '🟡', 'SELL': '🔴'}.get(r.rating, '⚪')
                c1.metric("Rating", f"{icon} {r.rating or 'N/A'}")
                c2.metric("CMP", f"₹{r.current_price:,.0f}" if r.current_price else "N/A")
                c3.metric("Target", f"₹{r.target_price:,.0f}" if r.target_price else "N/A", f"{r.upside_potential:+.1f}%" if r.upside_potential else None)
                c4.metric("Prev", f"₹{r.previous_target:,.0f}" if r.previous_target else "N/A")
                
                st.divider()
                left, right = st.columns([3, 2])
                
                with left:
                    if r.current_price and r.target_price:
                        st.subheader("📊 Price")
                        low = r.week_52_low or r.current_price * 0.7
                        high = max(r.week_52_high or r.current_price * 1.3, r.target_price)
                        prog = (r.current_price - low) / (high - low) if high > low else 0.5
                        st.progress(min(max(prog, 0), 1))
                        cols = st.columns(3)
                        cols[0].caption(f"52W Low: ₹{low:,.0f}")
                        cols[1].caption(f"CMP: ₹{r.current_price:,.0f}")
                        cols[2].caption(f"Target: ₹{r.target_price:,.0f}")
                    
                    if r.valuation_metrics:
                        st.subheader("💰 Valuation")
                        st.dataframe(pd.DataFrame([r.valuation_metrics]), hide_index=True)
                    
                    st.subheader("✅ Highlights")
                    for h in r.key_highlights or ["None found"]:
                        st.markdown(f"• {h}")
                    
                    st.subheader("⚠️ Risks")
                    for x in r.risks or ["None found"]:
                        st.markdown(f"• {x}")
                
                with right:
                    st.subheader("ℹ️ Info")
                    st.markdown(f"**Ticker:** {r.ticker or 'N/A'}")
                    st.markdown(f"**Date:** {r.report_date or 'N/A'}")
                    st.markdown(f"**Firm:** {r.analyst_firm or 'N/A'}")
                    st.markdown(f"**Mkt Cap:** {r.market_cap or 'N/A'}")
                    
                    if r.shareholding:
                        st.divider()
                        st.subheader("🥧 Shareholding")
                        st.bar_chart(pd.DataFrame({'%': r.shareholding}))
                    
                    if r.esg_score:
                        st.divider()
                        st.subheader("🌱 ESG")
                        st.bar_chart(pd.DataFrame({'Score': r.esg_score}))
                
                st.divider()
                c1, c2 = st.columns(2)
                c1.download_button("📄 JSON", json.dumps({'company': r.company_name, 'rating': r.rating, 'cmp': r.current_price, 'target': r.target_price}, indent=2), "data.json")
                c2.download_button("📝 Text", text, "raw.txt")
                
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.info("👆 Upload PDF to start")


if __name__ == "__main__":
    main()
