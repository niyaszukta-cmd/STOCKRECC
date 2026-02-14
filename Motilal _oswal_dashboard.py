"""
Equity Research PDF Analyzer Dashboard
Extracts key data, charts, prices, targets, and financials from research reports
"""

import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json

# Try pdfplumber first, fallback to pypdf
try:
    import pdfplumber
    PDF_LIBRARY = "pdfplumber"
except ImportError:
    try:
        from pypdf import PdfReader
        PDF_LIBRARY = "pypdf"
    except ImportError:
        import PyPDF2
        PDF_LIBRARY = "PyPDF2"


@dataclass
class ResearchReport:
    """Data class to hold extracted research report information"""
    company_name: str = ""
    ticker: str = ""
    exchange: str = ""
    report_date: str = ""
    analyst_firm: str = ""
    analysts: List[str] = None
    
    # Ratings & Targets
    rating: str = ""
    previous_rating: str = ""
    current_price: float = 0.0
    target_price: float = 0.0
    previous_target: float = 0.0
    upside_potential: float = 0.0
    
    # Market Data
    market_cap: str = ""
    market_cap_usd: str = ""
    free_float: float = 0.0
    adtv: str = ""
    week_52_high: float = 0.0
    week_52_low: float = 0.0
    
    # Sector Info
    sector: str = ""
    industry: str = ""
    
    # Key Highlights
    key_highlights: List[str] = None
    risks: List[str] = None
    
    # Financial Tables
    financial_summary: pd.DataFrame = None
    quarterly_data: pd.DataFrame = None
    valuation_metrics: Dict[str, Any] = None
    
    # ESG Scores
    esg_score: Dict[str, Any] = None
    
    # Shareholding
    shareholding: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.analysts is None:
            self.analysts = []
        if self.key_highlights is None:
            self.key_highlights = []
        if self.risks is None:
            self.risks = []
        if self.valuation_metrics is None:
            self.valuation_metrics = {}
        if self.esg_score is None:
            self.esg_score = {}
        if self.shareholding is None:
            self.shareholding = {}


def extract_number(text: str) -> Optional[float]:
    """Extract numeric value from text"""
    if not text:
        return None
    text = str(text).replace(',', '').replace('INR', '').replace('$', '').strip()
    if text.startswith('(') and text.endswith(')'):
        text = '-' + text[1:-1]
    match = re.search(r'-?\d+\.?\d*', text)
    if match:
        try:
            return float(match.group())
        except:
            return None
    return None


def parse_financial_table(table: List[List[str]], table_type: str = "auto") -> pd.DataFrame:
    """Parse extracted table into a clean DataFrame"""
    if not table or len(table) < 2:
        return pd.DataFrame()
    
    cleaned_table = []
    for row in table:
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append("")
            else:
                cleaned_row.append(str(cell).strip())
        cleaned_table.append(cleaned_row)
    
    try:
        df = pd.DataFrame(cleaned_table[1:], columns=cleaned_table[0])
        df.columns = [str(col).strip() for col in df.columns]
        return df
    except Exception:
        return pd.DataFrame(cleaned_table)


def extract_text_from_pdf(pdf_file) -> tuple:
    """Extract text from PDF using available library"""
    all_text = ""
    all_tables = []
    
    if PDF_LIBRARY == "pdfplumber":
        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                all_text += f"\n--- Page {page_num + 1} ---\n{text}"
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        all_tables.append({'page': page_num + 1, 'data': table})
    elif PDF_LIBRARY == "pypdf":
        from pypdf import PdfReader
        reader = PdfReader(pdf_file)
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            all_text += f"\n--- Page {page_num + 1} ---\n{text}"
    else:
        import PyPDF2
        reader = PyPDF2.PdfReader(pdf_file)
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            all_text += f"\n--- Page {page_num + 1} ---\n{text}"
    
    return all_text, all_tables


def extract_report_data(pdf_file) -> tuple:
    """Main function to extract all relevant data from equity research PDF"""
    report = ResearchReport()
    all_text, all_tables = extract_text_from_pdf(pdf_file)
    
    report = parse_header_info(all_text, report)
    report = parse_ratings_targets(all_text, report)
    report = parse_market_data(all_text, report)
    report = parse_key_points(all_text, report)
    report = parse_financial_tables(all_tables, report)
    report = parse_financial_data_from_text(all_text, report)
    report = parse_esg_data(all_text, report)
    report = parse_shareholding(all_text, all_tables, report)
    
    return report, all_text, all_tables


def parse_header_info(text: str, report: ResearchReport) -> ResearchReport:
    """Extract header information"""
    lines = text.split('\n')
    for line in lines[:30]:
        if 'Consumer' in line or 'Ltd' in line or 'Limited' in line or 'Industries' in line:
            potential_name = re.sub(r'[|].*', '', line).strip()
            if len(potential_name) > 3 and len(potential_name) < 50:
                potential_name = re.sub(r'\s+', ' ', potential_name)
                if not any(x in potential_name.lower() for x in ['page', 'report', 'research']):
                    report.company_name = potential_name
                    break
    
    ticker_match = re.search(r'Bloomberg\s*Code\s*[:\s]*([A-Z]+\s+IN)', text)
    if ticker_match:
        report.ticker = ticker_match.group(1)
    else:
        ticker_match = re.search(r'([A-Z]{3,10})\s+IN\b', text)
        if ticker_match:
            report.ticker = ticker_match.group(1) + " IN"
    
    date_patterns = [
        r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
        r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
    ]
    for pattern in date_patterns:
        date_match = re.search(pattern, text, re.IGNORECASE)
        if date_match:
            report.report_date = date_match.group(1)
            break
    
    firm_patterns = [r'(ICICI Securities|Motilal Oswal|HDFC Securities|Kotak Securities|JM Financial|Axis Securities|Edelweiss|Nuvama)']
    for pattern in firm_patterns:
        firm_match = re.search(pattern, text, re.IGNORECASE)
        if firm_match:
            report.analyst_firm = firm_match.group(0)
            break
    
    if 'Consumer' in text[:500]:
        report.sector = "Consumer Staples & Discretionary"
    
    return report


def parse_ratings_targets(text: str, report: ResearchReport) -> ResearchReport:
    """Extract ratings and price targets"""
    rating_match = re.search(r'\b(BUY|SELL|HOLD|ADD|REDUCE|ACCUMULATE|NEUTRAL)\b', text[:1000], re.IGNORECASE)
    if rating_match:
        report.rating = rating_match.group(1).upper()
    
    cmp_patterns = [
        r'CMP[:\s]*(?:INR\s*)?[₹]?(\d+(?:,\d{3})*(?:\.\d+)?)',
        r'Current\s*(?:Market\s*)?Price[:\s]*(?:INR\s*)?[₹]?(\d+(?:,\d{3})*(?:\.\d+)?)',
    ]
    for pattern in cmp_patterns:
        cmp_match = re.search(pattern, text, re.IGNORECASE)
        if cmp_match:
            report.current_price = extract_number(cmp_match.group(1)) or 0.0
            break
    
    target_patterns = [
        r'Target\s*Price[:\s]*(?:INR\s*)?[₹]?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:\((?:INR\s*)?[₹]?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:earlier)?\))?',
        r'TP[:\s]*(?:INR\s*)?[₹]?(\d+(?:,\d{3})*(?:\.\d+)?)',
    ]
    for pattern in target_patterns:
        target_match = re.search(pattern, text, re.IGNORECASE)
        if target_match:
            report.target_price = extract_number(target_match.group(1)) or 0.0
            if target_match.lastindex and target_match.lastindex >= 2 and target_match.group(2):
                report.previous_target = extract_number(target_match.group(2)) or 0.0
            break
    
    if report.current_price and report.target_price:
        report.upside_potential = ((report.target_price - report.current_price) / report.current_price) * 100
    
    return report


def parse_market_data(text: str, report: ResearchReport) -> ResearchReport:
    """Extract market data"""
    mcap_match = re.search(r'Market\s*Cap[^\d]*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(bn|mn|cr)?', text, re.IGNORECASE)
    if mcap_match:
        value = extract_number(mcap_match.group(1))
        unit = mcap_match.group(2) if mcap_match.lastindex >= 2 else ''
        report.market_cap = f"INR {value}{unit}" if unit else f"INR {value}"
    
    range_match = re.search(r'52-week\s*Range[^\d]*(\d+(?:,\d{3})*(?:\.\d+)?)\s*/\s*(\d+(?:,\d{3})*(?:\.\d+)?)', text, re.IGNORECASE)
    if range_match:
        report.week_52_high = extract_number(range_match.group(1)) or 0.0
        report.week_52_low = extract_number(range_match.group(2)) or 0.0
    
    float_match = re.search(r'Free\s*Float[^\d]*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if float_match:
        report.free_float = extract_number(float_match.group(1)) or 0.0
    
    return report


def parse_key_points(text: str, report: ResearchReport) -> ResearchReport:
    """Extract key highlights and risks"""
    highlights = []
    risks = []
    
    thesis_patterns = [
        r'We\s+(?:expect|believe|maintain)[^.]{20,150}\.',
        r'(?:growth|margin|revenue)[^.]*(?:driven by|led by|supported by)[^.]{10,100}\.',
    ]
    
    for pattern in thesis_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches[:2]:
            clean_match = re.sub(r'\s+', ' ', match).strip()
            if len(clean_match) > 30 and clean_match not in highlights:
                if not re.search(r'\d+\.\d+\s+\d+\.\d+', clean_match):
                    highlights.append(clean_match)
    
    growth_text = re.search(r'(?:led by|driven by|expect)[:\s]*(.*?)(?:BUY|Maintain|risks)', text, re.IGNORECASE | re.DOTALL)
    if growth_text:
        numbered_points = re.findall(r'\d\)\s*([A-Za-z][^;,\d]{10,80})', growth_text.group(1))
        for point in numbered_points[:4]:
            clean_point = re.sub(r'\s+', ' ', point).strip()
            if clean_point not in highlights and not re.search(r'\d+\.\d+', clean_point):
                highlights.append(clean_point)
    
    risk_match = re.search(r'Key\s*risks?[:\s]*\d?\)?\s*([^.]+(?:\.\s*)?(?:\d\)[^.]+(?:\.\s*)?)*)', text, re.IGNORECASE)
    if risk_match:
        risk_text = risk_match.group(1)
        risk_items = re.split(r',?\s*\d\)\s*', risk_text)
        for item in risk_items:
            item = item.strip().rstrip('.')
            item = re.sub(r'\s+', ' ', item)
            if len(item) > 10 and len(item) < 100 and item not in risks:
                if not re.search(r'\d+\.\d+\s+\d+', item):
                    risks.append(item)
    
    report.key_highlights = highlights[:5]
    report.risks = risks[:5]
    return report


def parse_financial_tables(tables: List[Dict], report: ResearchReport) -> ResearchReport:
    """Parse financial tables"""
    for table_info in tables:
        table = table_info['data']
        if not table or len(table) < 2:
            continue
        
        first_row = [str(cell).strip() if cell else '' for cell in table[0]]
        non_empty = sum(1 for cell in first_row if cell)
        if non_empty < 2:
            continue
        
        df = parse_financial_table(table)
        if df.empty or len(df) < 2:
            continue
        
        all_text = ' '.join(str(cell).lower() for row in table for cell in row if cell)
        
        if (('net revenue' in all_text or 'net sales' in all_text) and 
            ('ebitda' in all_text or 'pat' in all_text or 'net profit' in all_text)):
            if any('fy' in str(col).lower() for col in df.columns):
                report.financial_summary = df
                continue
        
        if ('q3fy' in all_text or 'q2fy' in all_text or 'qoq' in all_text):
            if any('yoy' in str(col).lower() or 'qoq' in str(col).lower() for col in df.columns):
                report.quarterly_data = df
    
    return report


def parse_financial_data_from_text(text: str, report: ResearchReport) -> ResearchReport:
    """Extract financial metrics from text"""
    pe_match = re.search(r'P/E\s*(?:\(x\))?\s*[:\s]*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if pe_match:
        report.valuation_metrics['P/E'] = extract_number(pe_match.group(1))
    
    ev_match = re.search(r'EV\s*/\s*EBITDA\s*(?:\(x\))?\s*[:\s]*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if ev_match:
        report.valuation_metrics['EV/EBITDA'] = extract_number(ev_match.group(1))
    
    roe_match = re.search(r'RoE\s*(?:\(%\))?\s*[:\s]*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if roe_match:
        report.valuation_metrics['RoE'] = extract_number(roe_match.group(1))
    
    roce_match = re.search(r'RoCE\s*(?:\(%\))?\s*[:\s]*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if roce_match:
        report.valuation_metrics['RoCE'] = extract_number(roce_match.group(1))
    
    return report


def parse_esg_data(text: str, report: ResearchReport) -> ResearchReport:
    """Extract ESG scores"""
    esg_section = re.search(r'ESG\s*Score[\s\S]{0,600}', text, re.IGNORECASE)
    if esg_section:
        section_text = esg_section.group(0)
        
        esg_total_match = re.search(r'ESG\s*score[^\d]*(?:\d{4}[^\d]*)?(?:NA[^\d]*)?(\d{2}\.\d)', section_text, re.IGNORECASE)
        if esg_total_match:
            val = extract_number(esg_total_match.group(1))
            if val and 0 < val <= 100:
                report.esg_score['total'] = val
        
        env_match = re.search(r'Environment[^\d]*(?:NA[^\d]*)?(\d{2}\.\d)', section_text, re.IGNORECASE)
        if env_match:
            val = extract_number(env_match.group(1))
            if val and 0 < val <= 100:
                report.esg_score['environment'] = val
        
        social_match = re.search(r'Social[^\d]*(?:NA[^\d]*)?(\d{2}\.\d)', section_text, re.IGNORECASE)
        if social_match:
            val = extract_number(social_match.group(1))
            if val and 0 < val <= 100:
                report.esg_score['social'] = val
        
        gov_match = re.search(r'Governance[^\d]*(?:NA[^\d]*)?(\d{2}\.\d)', section_text, re.IGNORECASE)
        if gov_match:
            val = extract_number(gov_match.group(1))
            if val and 0 < val <= 100:
                report.esg_score['governance'] = val
    
    return report


def parse_shareholding(text: str, tables: List[Dict], report: ResearchReport) -> ResearchReport:
    """Extract shareholding pattern"""
    shareholding = {}
    patterns = [
        (r'Promoters?\s*[:\s]*(\d+(?:\.\d+)?)\s*%?', 'Promoters'),
        (r'Institutional\s*investors?\s*[:\s]*(\d+(?:\.\d+)?)\s*%?', 'Institutional'),
        (r'FIIs?\s*[:\s]*(\d+(?:\.\d+)?)\s*%?', 'FIIs'),
        (r'Public\s*[:\s]*(\d+(?:\.\d+)?)\s*%?', 'Public'),
    ]
    
    for pattern, key in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            shareholding[key] = extract_number(match.group(1))
    
    report.shareholding = shareholding
    return report


def create_price_target_gauge(current_price: float, target_price: float, low_52: float, high_52: float):
    """Create gauge chart"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=current_price,
        delta={'reference': target_price, 'relative': True, 'valueformat': '.1%'},
        title={'text': "Current Price vs Target"},
        gauge={
            'axis': {'range': [low_52 * 0.9, max(high_52, target_price) * 1.1]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [low_52 * 0.9, current_price], 'color': "lightgray"},
                {'range': [current_price, target_price], 'color': "lightgreen"},
            ],
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': target_price}
        }
    ))
    fig.update_layout(height=300)
    return fig


def create_shareholding_pie(shareholding: Dict):
    """Create pie chart"""
    if not shareholding:
        return None
    fig = go.Figure(data=[go.Pie(
        labels=list(shareholding.keys()),
        values=list(shareholding.values()),
        hole=0.4,
        marker_colors=px.colors.qualitative.Set3
    )])
    fig.update_layout(title="Shareholding Pattern", height=350)
    return fig


def create_esg_radar(esg_scores: Dict):
    """Create radar chart"""
    if not esg_scores or len(esg_scores) < 3:
        return None
    categories = ['Environment', 'Social', 'Governance']
    values = [esg_scores.get('environment', 0), esg_scores.get('social', 0), esg_scores.get('governance', 0)]
    fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', marker_color='#2ecc71'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), title="ESG Scores", height=350)
    return fig


def main():
    st.set_page_config(page_title="Equity Research PDF Analyzer", page_icon="📊", layout="wide")
    
    st.title("📊 Equity Research PDF Analyzer")
    st.markdown("Extract key data, targets, financials, and charts from research reports")
    st.caption(f"PDF Library: {PDF_LIBRARY}")
    
    uploaded_file = st.file_uploader("Upload Equity Research PDF", type=['pdf'])
    
    if uploaded_file is not None:
        with st.spinner("Analyzing PDF..."):
            try:
                report, raw_text, tables = extract_report_data(uploaded_file)
                
                st.header(f"📈 {report.company_name or 'Research Report Analysis'}")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    rating_color = {'BUY': '🟢', 'ADD': '🟢', 'HOLD': '🟡', 'NEUTRAL': '🟡', 'SELL': '🔴', 'REDUCE': '🔴'}.get(report.rating, '⚪')
                    st.metric("Rating", f"{rating_color} {report.rating or 'N/A'}")
                with col2:
                    st.metric("Current Price", f"₹{report.current_price:,.2f}" if report.current_price else "N/A")
                with col3:
                    st.metric("Target Price", f"₹{report.target_price:,.2f}" if report.target_price else "N/A", f"{report.upside_potential:.1f}%" if report.upside_potential else None)
                with col4:
                    st.metric("Previous Target", f"₹{report.previous_target:,.2f}" if report.previous_target else "N/A")
                
                st.divider()
                left_col, right_col = st.columns([2, 1])
                
                with left_col:
                    if report.current_price and report.target_price:
                        st.subheader("📊 Price Target Analysis")
                        gauge_fig = create_price_target_gauge(report.current_price, report.target_price, report.week_52_low or report.current_price * 0.7, report.week_52_high or report.current_price * 1.3)
                        st.plotly_chart(gauge_fig, use_container_width=True)
                    
                    if report.financial_summary is not None and not report.financial_summary.empty:
                        st.subheader("📋 Financial Summary")
                        st.dataframe(report.financial_summary, use_container_width=True, hide_index=True)
                    
                    if report.valuation_metrics:
                        st.subheader("💰 Valuation Metrics")
                        st.dataframe(pd.DataFrame([report.valuation_metrics]), use_container_width=True, hide_index=True)
                
                with right_col:
                    st.subheader("ℹ️ Company Info")
                    st.markdown(f"**Ticker:** {report.ticker or 'N/A'}")
                    st.markdown(f"**Sector:** {report.sector or 'N/A'}")
                    st.markdown(f"**Report Date:** {report.report_date or 'N/A'}")
                    st.markdown(f"**Analyst Firm:** {report.analyst_firm or 'N/A'}")
                    
                    st.divider()
                    st.subheader("📊 Market Data")
                    st.markdown(f"**Market Cap:** {report.market_cap or 'N/A'}")
                    st.markdown(f"**52W High:** ₹{report.week_52_high:,.2f}" if report.week_52_high else "**52W High:** N/A")
                    st.markdown(f"**52W Low:** ₹{report.week_52_low:,.2f}" if report.week_52_low else "**52W Low:** N/A")
                    st.markdown(f"**Free Float:** {report.free_float}%" if report.free_float else "**Free Float:** N/A")
                    
                    if report.shareholding:
                        st.divider()
                        st.subheader("🥧 Shareholding")
                        pie_fig = create_shareholding_pie(report.shareholding)
                        if pie_fig:
                            st.plotly_chart(pie_fig, use_container_width=True)
                    
                    if report.esg_score:
                        st.divider()
                        st.subheader("🌱 ESG Scores")
                        esg_fig = create_esg_radar(report.esg_score)
                        if esg_fig:
                            st.plotly_chart(esg_fig, use_container_width=True)
                
                st.divider()
                highlight_col, risk_col = st.columns(2)
                with highlight_col:
                    st.subheader("✅ Key Highlights")
                    if report.key_highlights:
                        for h in report.key_highlights:
                            st.markdown(f"• {h}")
                    else:
                        st.info("No highlights extracted")
                
                with risk_col:
                    st.subheader("⚠️ Key Risks")
                    if report.risks:
                        for r in report.risks:
                            st.markdown(f"• {r}")
                    else:
                        st.info("No risks extracted")
                
                st.divider()
                with st.expander("🔍 View Raw Data"):
                    tab1, tab2 = st.tabs(["Raw Text", "JSON"])
                    with tab1:
                        st.text_area("Extracted Text", raw_text, height=400)
                    with tab2:
                        report_dict = {
                            'company_name': report.company_name, 'ticker': report.ticker, 'report_date': report.report_date,
                            'rating': report.rating, 'current_price': report.current_price, 'target_price': report.target_price,
                            'upside_potential': round(report.upside_potential, 2) if report.upside_potential else None,
                            'market_cap': report.market_cap, 'esg_score': report.esg_score, 'shareholding': report.shareholding,
                        }
                        st.json(report_dict)
                
                st.divider()
                st.subheader("📥 Export")
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button("📄 Download JSON", json.dumps(report_dict, indent=2), f"{report.company_name or 'report'}.json", "application/json")
                with col2:
                    st.download_button("📝 Download Text", raw_text, f"{report.company_name or 'report'}.txt", "text/plain")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.exception(e)
    else:
        st.info("👆 Upload an equity research PDF to get started")
        st.markdown("""
        ### Features
        - 🎯 **Ratings & Targets**: Buy/Sell recommendations, price targets
        - 📊 **Market Data**: Market cap, 52-week range, free float
        - 💰 **Valuation**: P/E, EV/EBITDA, RoE, RoCE
        - 🥧 **Shareholding Pattern**: Promoter, FII, DII holdings
        - 🌱 **ESG Scores**: Environmental, Social, Governance
        - ⚠️ **Key Risks & Highlights**
        """)


if __name__ == "__main__":
    main()
