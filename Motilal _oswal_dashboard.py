"""
Equity Research PDF Analyzer Dashboard
Extracts key data, charts, prices, targets, and financials from research reports
"""

import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json


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
    # Remove common formatting
    text = str(text).replace(',', '').replace('INR', '').replace('$', '').strip()
    # Handle parentheses for negative numbers
    if text.startswith('(') and text.endswith(')'):
        text = '-' + text[1:-1]
    # Find number pattern
    match = re.search(r'-?\d+\.?\d*', text)
    if match:
        try:
            return float(match.group())
        except:
            return None
    return None


def extract_percentage(text: str) -> Optional[float]:
    """Extract percentage value from text"""
    if not text:
        return None
    text = str(text).replace('%', '').strip()
    return extract_number(text)


def parse_financial_table(table: List[List[str]], table_type: str = "auto") -> pd.DataFrame:
    """Parse extracted table into a clean DataFrame"""
    if not table or len(table) < 2:
        return pd.DataFrame()
    
    # Clean the table
    cleaned_table = []
    for row in table:
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append("")
            else:
                cleaned_row.append(str(cell).strip())
        cleaned_table.append(cleaned_row)
    
    # Try to identify header row
    try:
        df = pd.DataFrame(cleaned_table[1:], columns=cleaned_table[0])
        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]
        return df
    except Exception as e:
        return pd.DataFrame(cleaned_table)


def extract_report_data(pdf_file) -> ResearchReport:
    """Main function to extract all relevant data from equity research PDF"""
    report = ResearchReport()
    all_text = ""
    all_tables = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Extract text
            text = page.extract_text() or ""
            all_text += f"\n--- Page {page_num + 1} ---\n{text}"
            
            # Extract tables
            tables = page.extract_tables()
            for table in tables:
                if table:
                    all_tables.append({
                        'page': page_num + 1,
                        'data': table
                    })
    
    # Parse the extracted content
    report = parse_header_info(all_text, report)
    report = parse_ratings_targets(all_text, report)
    report = parse_market_data(all_text, report)
    report = parse_key_points(all_text, report)
    report = parse_financial_tables(all_tables, report)
    report = parse_esg_data(all_text, report)
    report = parse_shareholding(all_text, all_tables, report)
    
    return report, all_text, all_tables


def parse_header_info(text: str, report: ResearchReport) -> ResearchReport:
    """Extract header information like company name, date, analysts"""
    
    # Company name patterns
    company_patterns = [
        r'(?:Company|Stock):\s*([A-Za-z\s]+)',
        r'^([A-Z][A-Za-z\s]+(?:Ltd|Limited|Inc|Corp|Consumer|Industries|Pharma))',
    ]
    
    # Try to find company name
    lines = text.split('\n')
    for line in lines[:30]:
        if 'Consumer' in line or 'Ltd' in line or 'Limited' in line:
            # Clean and extract
            potential_name = re.sub(r'[|].*', '', line).strip()
            if len(potential_name) > 3 and len(potential_name) < 50:
                report.company_name = potential_name
                break
    
    # Extract ticker/Bloomberg code
    ticker_match = re.search(r'Bloomberg Code\s*[:\s]*([A-Z]+\s+IN)', text)
    if ticker_match:
        report.ticker = ticker_match.group(1)
    else:
        ticker_match = re.search(r'([A-Z]{3,10})\s+IN\b', text)
        if ticker_match:
            report.ticker = ticker_match.group(1) + " IN"
    
    # Extract date
    date_patterns = [
        r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
        r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
        r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
    ]
    for pattern in date_patterns:
        date_match = re.search(pattern, text, re.IGNORECASE)
        if date_match:
            report.report_date = date_match.group(1)
            break
    
    # Extract analyst firm
    firm_patterns = [
        r'(ICICI Securities|Motilal Oswal|HDFC Securities|Kotak Securities|JM Financial|Axis Securities)',
        r'ICICI Securities Limited',
    ]
    for pattern in firm_patterns:
        firm_match = re.search(pattern, text, re.IGNORECASE)
        if firm_match:
            report.analyst_firm = firm_match.group(0)
            break
    
    # Extract analysts
    analyst_section = re.search(r'(Manoj Menon|Dhiraj Mistry|Ashutosh|Akshay)[\s\S]*?@', text)
    if analyst_section:
        analysts = re.findall(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', analyst_section.group(0))
        report.analysts = analysts[:4]
    
    # Sector
    sector_match = re.search(r'(?:Sector|Industry):\s*([A-Za-z\s&]+)', text)
    if sector_match:
        report.sector = sector_match.group(1).strip()
    else:
        if 'Consumer' in text[:500]:
            report.sector = "Consumer Staples & Discretionary"
    
    return report


def parse_ratings_targets(text: str, report: ResearchReport) -> ResearchReport:
    """Extract ratings and price targets"""
    
    # Rating extraction
    rating_patterns = [
        r'\b(BUY|SELL|HOLD|ADD|REDUCE|ACCUMULATE|NEUTRAL)\s*(?:\(Maintain\)|\(Upgrade\)|\(Downgrade\))?',
    ]
    for pattern in rating_patterns:
        rating_match = re.search(pattern, text, re.IGNORECASE)
        if rating_match:
            report.rating = rating_match.group(1).upper()
            break
    
    # Current price (CMP)
    cmp_patterns = [
        r'CMP[:\s]*(?:INR\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)',
        r'Current\s*(?:Market\s*)?Price[:\s]*(?:INR\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)',
    ]
    for pattern in cmp_patterns:
        cmp_match = re.search(pattern, text, re.IGNORECASE)
        if cmp_match:
            report.current_price = extract_number(cmp_match.group(1)) or 0.0
            break
    
    # Target price
    target_patterns = [
        r'Target\s*Price[:\s]*(?:INR\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:\((?:INR\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:earlier)?\))?',
        r'TP[:\s]*(?:INR\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)',
    ]
    for pattern in target_patterns:
        target_match = re.search(pattern, text, re.IGNORECASE)
        if target_match:
            report.target_price = extract_number(target_match.group(1)) or 0.0
            if target_match.lastindex >= 2 and target_match.group(2):
                report.previous_target = extract_number(target_match.group(2)) or 0.0
            break
    
    # Upside percentage
    upside_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text[:500])
    if upside_match and report.current_price and report.target_price:
        report.upside_potential = ((report.target_price - report.current_price) / report.current_price) * 100
    
    return report


def parse_market_data(text: str, report: ResearchReport) -> ResearchReport:
    """Extract market data like market cap, 52-week range, etc."""
    
    # Market Cap
    mcap_match = re.search(r'Market\s*Cap\s*\(INR\)[:\s]*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(bn|mn|cr)?', text, re.IGNORECASE)
    if mcap_match:
        value = extract_number(mcap_match.group(1))
        unit = mcap_match.group(2) if mcap_match.lastindex >= 2 else ''
        report.market_cap = f"INR {value}{unit}"
    
    # Market Cap USD
    mcap_usd_match = re.search(r'Market\s*Cap\s*\(USD\)[:\s]*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(bn|mn)?', text, re.IGNORECASE)
    if mcap_usd_match:
        value = extract_number(mcap_usd_match.group(1))
        unit = mcap_usd_match.group(2) if mcap_usd_match.lastindex >= 2 else ''
        report.market_cap_usd = f"USD {value}{unit}"
    
    # 52-week range
    range_match = re.search(r'52-week\s*Range\s*\(INR\)[:\s]*(\d+(?:,\d{3})*(?:\.\d+)?)\s*/\s*(\d+(?:,\d{3})*(?:\.\d+)?)', text, re.IGNORECASE)
    if range_match:
        report.week_52_high = extract_number(range_match.group(1)) or 0.0
        report.week_52_low = extract_number(range_match.group(2)) or 0.0
    
    # Free Float
    float_match = re.search(r'Free\s*Float\s*\(%?\)[:\s]*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if float_match:
        report.free_float = extract_number(float_match.group(1)) or 0.0
    
    # ADTV
    adtv_match = re.search(r'ADTV[^:]*[:\s]*(?:\(USD\))?\s*(\d+(?:\.\d+)?)\s*(mn)?', text, re.IGNORECASE)
    if adtv_match:
        report.adtv = f"${adtv_match.group(1)}mn"
    
    return report


def parse_key_points(text: str, report: ResearchReport) -> ResearchReport:
    """Extract key highlights and risks"""
    
    highlights = []
    risks = []
    
    # Look for the main investment thesis
    thesis_patterns = [
        r'We\s+(?:expect|believe|maintain)[^.]{20,150}\.',
        r'(?:growth|margin|revenue)[^.]*(?:driven by|led by|supported by)[^.]{10,100}\.',
    ]
    
    for pattern in thesis_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches[:2]:
            # Clean up the match
            clean_match = re.sub(r'\s+', ' ', match).strip()
            if len(clean_match) > 30 and clean_match not in highlights:
                # Avoid table data
                if not re.search(r'\d+\.\d+\s+\d+\.\d+', clean_match):
                    highlights.append(clean_match)
    
    # Look for numbered growth drivers (like "1) Strategic investments...")
    growth_text = re.search(r'(?:led by|driven by|expect)[:\s]*(.*?)(?:BUY|Maintain|risks)', text, re.IGNORECASE | re.DOTALL)
    if growth_text:
        numbered_points = re.findall(r'\d\)\s*([A-Za-z][^;,\d]{10,80})', growth_text.group(1))
        for point in numbered_points[:4]:
            clean_point = re.sub(r'\s+', ' ', point).strip()
            if clean_point not in highlights and not re.search(r'\d+\.\d+', clean_point):
                highlights.append(clean_point)
    
    # Risks extraction - look for "Key risks:" pattern
    risk_match = re.search(r'Key\s*risks?[:\s]*\d?\)?\s*([^.]+(?:\.\s*)?(?:\d\)[^.]+(?:\.\s*)?)*)', text, re.IGNORECASE)
    if risk_match:
        risk_text = risk_match.group(1)
        # Split on numbered items or commas
        risk_items = re.split(r',?\s*\d\)\s*', risk_text)
        for item in risk_items:
            item = item.strip().rstrip('.')
            # Clean up
            item = re.sub(r'\s+', ' ', item)
            if len(item) > 10 and len(item) < 100 and item not in risks:
                # Skip if it looks like data
                if not re.search(r'\d+\.\d+\s+\d+', item):
                    risks.append(item)
    
    report.key_highlights = highlights[:5]
    report.risks = risks[:5]
    
    return report


def parse_financial_tables(tables: List[Dict], report: ResearchReport) -> ResearchReport:
    """Parse and categorize financial tables"""
    
    for table_info in tables:
        table = table_info['data']
        if not table or len(table) < 2:
            continue
        
        # Check if first row looks like a header
        first_row = [str(cell).strip() if cell else '' for cell in table[0]]
        first_row_text = ' '.join(first_row).lower()
        
        # Skip if it's mostly empty or chart data
        non_empty = sum(1 for cell in first_row if cell)
        if non_empty < 2:
            continue
        
        df = parse_financial_table(table)
        if df.empty or len(df) < 2:
            continue
        
        # Check table content for classification
        all_text = ' '.join(str(cell).lower() for row in table for cell in row if cell)
        
        # Financial Summary - look for key financial line items
        if (('net revenue' in all_text or 'net sales' in all_text) and 
            ('ebitda' in all_text or 'pat' in all_text or 'net profit' in all_text)):
            # Verify it has FY columns
            if any('fy' in str(col).lower() for col in df.columns):
                report.financial_summary = df
                continue
        
        # Quarterly Data - look for Q indicators
        if ('q3fy' in all_text or 'q2fy' in all_text or 'qoq' in all_text):
            if any('yoy' in str(col).lower() or 'qoq' in str(col).lower() for col in df.columns):
                report.quarterly_data = df
                continue
        
        # Valuation metrics extraction
        if any(x in all_text for x in ['p/e', 'ev/ebitda', 'p/bv', 'roe', 'roce']):
            for idx, row in df.iterrows():
                try:
                    metric = str(row.iloc[0]).strip()
                    if metric in ['P/E', 'P/E (x)', 'EV/EBITDA', 'EV / EBITDA', 'P/BV', 'RoE', 'RoE (%)', 'RoCE', 'RoCE (%)']:
                        values = {}
                        for col in df.columns[1:]:
                            val = extract_number(row[col])
                            if val is not None:
                                values[str(col)] = val
                        if values:
                            report.valuation_metrics[metric] = values
                except:
                    continue
    
    return report


def parse_esg_data(text: str, report: ResearchReport) -> ResearchReport:
    """Extract ESG scores"""
    
    # Look for ESG section
    esg_section = re.search(r'ESG\s*Score[\s\S]{0,600}', text, re.IGNORECASE)
    if esg_section:
        section_text = esg_section.group(0)
        
        # For total ESG score - look for pattern "ESG score ... 52.3" skipping years and NA
        # The total score usually appears as last number after "ESG score"
        esg_total_match = re.search(r'ESG\s*score[^\d]*(?:\d{4}[^\d]*)?(?:NA[^\d]*)?(\d{2}\.\d)', section_text, re.IGNORECASE)
        if esg_total_match:
            val = extract_number(esg_total_match.group(1))
            if val and 0 < val <= 100:
                report.esg_score['total'] = val
        
        # Environment score
        env_match = re.search(r'Environment[^\d]*(?:NA[^\d]*)?(\d{2}\.\d)', section_text, re.IGNORECASE)
        if env_match:
            val = extract_number(env_match.group(1))
            if val and 0 < val <= 100:
                report.esg_score['environment'] = val
        
        # Social score  
        social_match = re.search(r'Social[^\d]*(?:NA[^\d]*)?(\d{2}\.\d)', section_text, re.IGNORECASE)
        if social_match:
            val = extract_number(social_match.group(1))
            if val and 0 < val <= 100:
                report.esg_score['social'] = val
        
        # Governance score
        gov_match = re.search(r'Governance[^\d]*(?:NA[^\d]*)?(\d{2}\.\d)', section_text, re.IGNORECASE)
        if gov_match:
            val = extract_number(gov_match.group(1))
            if val and 0 < val <= 100:
                report.esg_score['governance'] = val
    
    return report


def parse_shareholding(text: str, tables: List[Dict], report: ResearchReport) -> ResearchReport:
    """Extract shareholding pattern"""
    
    shareholding = {}
    
    # From text
    patterns = [
        (r'Promoters?\s*[:\s]*(\d+(?:\.\d+)?)\s*%?', 'Promoters'),
        (r'Institutional\s*investors?\s*[:\s]*(\d+(?:\.\d+)?)\s*%?', 'Institutional'),
        (r'FIIs?\s*[:\s]*(\d+(?:\.\d+)?)\s*%?', 'FIIs'),
        (r'DIIs?\s*[:\s]*(\d+(?:\.\d+)?)\s*%?', 'DIIs'),
        (r'Public\s*[:\s]*(\d+(?:\.\d+)?)\s*%?', 'Public'),
    ]
    
    for pattern, key in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            shareholding[key] = extract_number(match.group(1))
    
    report.shareholding = shareholding
    return report


def create_price_target_gauge(current_price: float, target_price: float, low_52: float, high_52: float):
    """Create a gauge chart for price vs target"""
    
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
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': target_price
            }
        }
    ))
    
    fig.update_layout(height=300)
    return fig


def create_financial_chart(df: pd.DataFrame, metric: str):
    """Create a bar chart for financial metrics"""
    
    if df is None or df.empty:
        return None
    
    # Try to find the metric row
    for idx, row in df.iterrows():
        if metric.lower() in str(row.iloc[0]).lower():
            # Get fiscal years from columns
            years = [col for col in df.columns[1:] if 'FY' in str(col) or any(c.isdigit() for c in str(col))]
            values = [extract_number(row[col]) for col in years]
            
            if any(v is not None for v in values):
                fig = go.Figure(data=[
                    go.Bar(x=years, y=values, marker_color='#1f77b4')
                ])
                fig.update_layout(
                    title=f"{metric} Trend",
                    xaxis_title="Period",
                    yaxis_title=metric,
                    height=300
                )
                return fig
    
    return None


def create_shareholding_pie(shareholding: Dict):
    """Create pie chart for shareholding pattern"""
    
    if not shareholding:
        return None
    
    labels = list(shareholding.keys())
    values = list(shareholding.values())
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker_colors=px.colors.qualitative.Set3
    )])
    
    fig.update_layout(
        title="Shareholding Pattern",
        height=350
    )
    
    return fig


def create_esg_radar(esg_scores: Dict):
    """Create radar chart for ESG scores"""
    
    if not esg_scores or len(esg_scores) < 3:
        return None
    
    categories = ['Environment', 'Social', 'Governance']
    values = [
        esg_scores.get('environment', 0),
        esg_scores.get('social', 0),
        esg_scores.get('governance', 0)
    ]
    
    fig = go.Figure(data=go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        marker_color='#2ecc71'
    ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="ESG Scores",
        height=350
    )
    
    return fig


def main():
    st.set_page_config(
        page_title="Equity Research PDF Analyzer",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Equity Research PDF Analyzer")
    st.markdown("Extract key data, targets, financials, and charts from research reports")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Upload Equity Research PDF",
        type=['pdf'],
        help="Upload an equity research report in PDF format"
    )
    
    if uploaded_file is not None:
        with st.spinner("Analyzing PDF..."):
            try:
                report, raw_text, tables = extract_report_data(uploaded_file)
                
                # Header Section
                st.header(f"📈 {report.company_name or 'Research Report Analysis'}")
                
                # Rating Badge
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    rating_color = {
                        'BUY': '🟢', 'ADD': '🟢',
                        'HOLD': '🟡', 'NEUTRAL': '🟡',
                        'SELL': '🔴', 'REDUCE': '🔴'
                    }.get(report.rating, '⚪')
                    st.metric(
                        "Rating",
                        f"{rating_color} {report.rating or 'N/A'}"
                    )
                
                with col2:
                    st.metric(
                        "Current Price",
                        f"₹{report.current_price:,.2f}" if report.current_price else "N/A"
                    )
                
                with col3:
                    st.metric(
                        "Target Price",
                        f"₹{report.target_price:,.2f}" if report.target_price else "N/A",
                        f"{report.upside_potential:.1f}%" if report.upside_potential else None
                    )
                
                with col4:
                    st.metric(
                        "Previous Target",
                        f"₹{report.previous_target:,.2f}" if report.previous_target else "N/A"
                    )
                
                st.divider()
                
                # Two column layout
                left_col, right_col = st.columns([2, 1])
                
                with left_col:
                    # Price Target Visualization
                    if report.current_price and report.target_price:
                        st.subheader("📊 Price Target Analysis")
                        gauge_fig = create_price_target_gauge(
                            report.current_price,
                            report.target_price,
                            report.week_52_low or report.current_price * 0.7,
                            report.week_52_high or report.current_price * 1.3
                        )
                        st.plotly_chart(gauge_fig, use_container_width=True)
                    
                    # Financial Summary Table
                    if report.financial_summary is not None and not report.financial_summary.empty:
                        st.subheader("📋 Financial Summary")
                        st.dataframe(report.financial_summary, use_container_width=True, hide_index=True)
                        
                        # Financial Charts
                        st.subheader("📈 Financial Trends")
                        metric_tabs = st.tabs(["Revenue", "EBITDA", "Net Profit", "EPS"])
                        
                        for tab, metric in zip(metric_tabs, ["Net Revenue", "EBITDA", "Net Profit", "EPS"]):
                            with tab:
                                fig = create_financial_chart(report.financial_summary, metric)
                                if fig:
                                    st.plotly_chart(fig, use_container_width=True)
                                else:
                                    st.info(f"No {metric} data found")
                    
                    # Quarterly Data
                    if report.quarterly_data is not None and not report.quarterly_data.empty:
                        st.subheader("📅 Quarterly Results")
                        st.dataframe(report.quarterly_data, use_container_width=True, hide_index=True)
                
                with right_col:
                    # Company Info Card
                    st.subheader("ℹ️ Company Info")
                    info_data = {
                        "Ticker": report.ticker or "N/A",
                        "Sector": report.sector or "N/A",
                        "Report Date": report.report_date or "N/A",
                        "Analyst Firm": report.analyst_firm or "N/A",
                    }
                    for key, value in info_data.items():
                        st.markdown(f"**{key}:** {value}")
                    
                    st.divider()
                    
                    # Market Data Card
                    st.subheader("📊 Market Data")
                    market_data = {
                        "Market Cap": report.market_cap or "N/A",
                        "Market Cap (USD)": report.market_cap_usd or "N/A",
                        "52W High": f"₹{report.week_52_high:,.2f}" if report.week_52_high else "N/A",
                        "52W Low": f"₹{report.week_52_low:,.2f}" if report.week_52_low else "N/A",
                        "Free Float": f"{report.free_float}%" if report.free_float else "N/A",
                        "ADTV": report.adtv or "N/A",
                    }
                    for key, value in market_data.items():
                        st.markdown(f"**{key}:** {value}")
                    
                    st.divider()
                    
                    # Shareholding Chart
                    if report.shareholding:
                        st.subheader("🥧 Shareholding Pattern")
                        pie_fig = create_shareholding_pie(report.shareholding)
                        if pie_fig:
                            st.plotly_chart(pie_fig, use_container_width=True)
                    
                    # ESG Scores
                    if report.esg_score:
                        st.subheader("🌱 ESG Scores")
                        esg_fig = create_esg_radar(report.esg_score)
                        if esg_fig:
                            st.plotly_chart(esg_fig, use_container_width=True)
                
                # Key Highlights & Risks
                st.divider()
                highlight_col, risk_col = st.columns(2)
                
                with highlight_col:
                    st.subheader("✅ Key Highlights")
                    if report.key_highlights:
                        for highlight in report.key_highlights:
                            st.markdown(f"• {highlight}")
                    else:
                        st.info("No key highlights extracted")
                
                with risk_col:
                    st.subheader("⚠️ Key Risks")
                    if report.risks:
                        for risk in report.risks:
                            st.markdown(f"• {risk}")
                    else:
                        st.info("No risks extracted")
                
                # Valuation Metrics
                if report.valuation_metrics:
                    st.divider()
                    st.subheader("💰 Valuation Metrics")
                    valuation_df = pd.DataFrame(report.valuation_metrics).T
                    st.dataframe(valuation_df, use_container_width=True)
                
                # Raw Data Explorer
                st.divider()
                with st.expander("🔍 View Raw Extracted Data"):
                    tab1, tab2, tab3 = st.tabs(["Raw Text", "Extracted Tables", "Report JSON"])
                    
                    with tab1:
                        st.text_area("Extracted Text", raw_text, height=400)
                    
                    with tab2:
                        for i, table_info in enumerate(tables):
                            st.markdown(f"**Table {i+1} (Page {table_info['page']})**")
                            df = parse_financial_table(table_info['data'])
                            if not df.empty:
                                st.dataframe(df, use_container_width=True, hide_index=True)
                            st.divider()
                    
                    with tab3:
                        # Convert report to JSON-serializable dict
                        report_dict = {
                            'company_name': report.company_name,
                            'ticker': report.ticker,
                            'report_date': report.report_date,
                            'analyst_firm': report.analyst_firm,
                            'rating': report.rating,
                            'current_price': report.current_price,
                            'target_price': report.target_price,
                            'previous_target': report.previous_target,
                            'upside_potential': round(report.upside_potential, 2) if report.upside_potential else None,
                            'market_cap': report.market_cap,
                            'week_52_high': report.week_52_high,
                            'week_52_low': report.week_52_low,
                            'free_float': report.free_float,
                            'esg_score': report.esg_score,
                            'shareholding': report.shareholding,
                            'key_highlights': report.key_highlights,
                            'risks': report.risks,
                        }
                        st.json(report_dict)
                
                # Download Options
                st.divider()
                st.subheader("📥 Export Data")
                
                export_col1, export_col2, export_col3 = st.columns(3)
                
                with export_col1:
                    # Export as JSON
                    report_dict = {
                        'company_name': report.company_name,
                        'ticker': report.ticker,
                        'report_date': report.report_date,
                        'rating': report.rating,
                        'current_price': report.current_price,
                        'target_price': report.target_price,
                        'upside_potential': round(report.upside_potential, 2) if report.upside_potential else None,
                        'market_cap': report.market_cap,
                        'esg_score': report.esg_score,
                        'shareholding': report.shareholding,
                    }
                    json_str = json.dumps(report_dict, indent=2)
                    st.download_button(
                        label="📄 Download JSON",
                        data=json_str,
                        file_name=f"{report.company_name or 'report'}_analysis.json",
                        mime="application/json"
                    )
                
                with export_col2:
                    # Export Financial Summary as CSV
                    if report.financial_summary is not None and not report.financial_summary.empty:
                        csv_buffer = io.StringIO()
                        report.financial_summary.to_csv(csv_buffer, index=False)
                        st.download_button(
                            label="📊 Download Financials CSV",
                            data=csv_buffer.getvalue(),
                            file_name=f"{report.company_name or 'report'}_financials.csv",
                            mime="text/csv"
                        )
                
                with export_col3:
                    # Export raw text
                    st.download_button(
                        label="📝 Download Raw Text",
                        data=raw_text,
                        file_name=f"{report.company_name or 'report'}_raw.txt",
                        mime="text/plain"
                    )
                
            except Exception as e:
                st.error(f"Error processing PDF: {str(e)}")
                st.exception(e)
    
    else:
        # Landing page
        st.info("👆 Upload an equity research PDF to get started")
        
        st.markdown("""
        ### Features
        
        This dashboard extracts and visualizes:
        
        - 🎯 **Ratings & Targets**: Buy/Sell recommendations, price targets, upside potential
        - 📊 **Market Data**: Market cap, 52-week range, free float, trading volumes
        - 💰 **Financial Summary**: Revenue, EBITDA, Net Profit, EPS trends
        - 📅 **Quarterly Results**: QoQ and YoY comparisons
        - 🥧 **Shareholding Pattern**: Promoter, FII, DII holdings
        - 🌱 **ESG Scores**: Environmental, Social, and Governance ratings
        - ⚠️ **Key Risks**: Risk factors identified in the report
        - ✅ **Key Highlights**: Investment thesis and key points
        
        ### Supported Formats
        
        Works best with institutional research reports from:
        - ICICI Securities
        - Motilal Oswal
        - HDFC Securities
        - Kotak Securities
        - And other major brokerages
        """)
        
        # Sample metrics display
        st.markdown("### Sample Output Preview")
        demo_col1, demo_col2, demo_col3, demo_col4 = st.columns(4)
        with demo_col1:
            st.metric("Rating", "🟢 BUY")
        with demo_col2:
            st.metric("CMP", "₹299")
        with demo_col3:
            st.metric("Target", "₹500", "+67%")
        with demo_col4:
            st.metric("Market Cap", "₹97bn")


if __name__ == "__main__":
    main()
