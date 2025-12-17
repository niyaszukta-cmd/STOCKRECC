import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from bs4 import BeautifulSoup
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
import json

# Page Configuration
st.set_page_config(
    page_title="Motilal Oswal Stock Recommendations",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .buy-card {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 1rem;
        border-radius: 8px;
        color: white;
        margin: 0.5rem 0;
    }
    .sell-card {
        background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        padding: 1rem;
        border-radius: 8px;
        color: white;
        margin: 0.5rem 0;
    }
    .hold-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1rem;
        border-radius: 8px;
        color: white;
        margin: 0.5rem 0;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: bold;
        border: none;
        padding: 0.75rem;
        border-radius: 8px;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    div[data-testid="stDataFrame"] {
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        overflow: hidden;
    }
    </style>
""", unsafe_allow_html=True)

# Function to fetch data from Trendlyne (Alternative source)
@st.cache_data(ttl=3600)
def fetch_trendlyne_data():
    """Fetch Motilal Oswal recommendations from Trendlyne"""
    try:
        url = "https://trendlyne.com/research-reports/broker/Motilal%20Oswal/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the table containing recommendations
        table = soup.find('table')
        
        if table:
            rows = table.find_all('tr')
            data = []
            
            for row in rows[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 6:
                    stock_name = cols[1].text.strip()
                    date = cols[0].text.strip()
                    cmp = cols[2].text.strip()
                    target = cols[3].text.strip()
                    upside = cols[4].text.strip()
                    recommendation = cols[5].text.strip()
                    
                    data.append({
                        'Date': date,
                        'Stock': stock_name,
                        'CMP': cmp,
                        'Target': target,
                        'Upside': upside,
                        'Recommendation': recommendation
                    })
            
            if data:
                return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error fetching from Trendlyne: {str(e)}")
    
    return None

# Function to create sample data (fallback)
def create_sample_data():
    """Create sample data for demonstration"""
    data = {
        'Date': ['17-Dec-24', '16-Dec-24', '15-Dec-24', '14-Dec-24', '13-Dec-24',
                 '12-Dec-24', '11-Dec-24', '10-Dec-24', '09-Dec-24', '08-Dec-24',
                 '07-Dec-24', '06-Dec-24', '05-Dec-24', '04-Dec-24', '03-Dec-24'],
        'Stock': ['Reliance Industries', 'TCS', 'HDFC Bank', 'Infosys', 'ICICI Bank',
                  'Bharti Airtel', 'ITC', 'Kotak Mahindra Bank', 'HUL', 'Axis Bank',
                  'Maruti Suzuki', 'Asian Paints', 'Bajaj Finance', 'Wipro', 'SBI'],
        'Sector': ['Oil & Gas', 'IT', 'Banking', 'IT', 'Banking',
                   'Telecom', 'FMCG', 'Banking', 'FMCG', 'Banking',
                   'Auto', 'Paints', 'NBFC', 'IT', 'Banking'],
        'CMP': [1245.50, 3890.75, 1650.20, 1520.80, 1125.40,
                1285.60, 445.30, 1790.50, 2345.80, 1095.70,
                12450.30, 2890.50, 7250.80, 445.20, 625.40],
        'Target': [1550, 4200, 1850, 1750, 1300,
                   1450, 520, 2000, 2650, 1250,
                   14000, 3200, 8500, 520, 750],
        'Upside': [24.46, 7.95, 12.11, 15.07, 15.52,
                   12.79, 16.78, 11.70, 12.97, 14.08,
                   12.45, 10.71, 17.24, 16.82, 19.94],
        'Recommendation': ['Buy', 'Buy', 'Buy', 'Buy', 'Buy',
                          'Buy', 'Buy', 'Buy', 'Hold', 'Buy',
                          'Strong Buy', 'Buy', 'Buy', 'Hold', 'Buy']
    }
    return pd.DataFrame(data)

# Function to generate PDF report
def generate_pdf_report(df, filters):
    """Generate professional PDF report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    
    # Title
    title = Paragraph("Motilal Oswal Stock Recommendations", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2*inch))
    
    # Report Info
    report_date = datetime.now().strftime("%d %B %Y, %I:%M %p")
    info_text = f"<b>Report Generated:</b> {report_date}<br/>"
    info_text += f"<b>Total Recommendations:</b> {len(df)}<br/>"
    
    if filters['recommendation'] != 'All':
        info_text += f"<b>Filtered By:</b> {filters['recommendation']} recommendations<br/>"
    if filters['sector'] != 'All':
        info_text += f"<b>Sector:</b> {filters['sector']}<br/>"
    if filters['min_upside'] > 0:
        info_text += f"<b>Minimum Upside:</b> {filters['min_upside']}%<br/>"
    
    info_para = Paragraph(info_text, normal_style)
    elements.append(info_para)
    elements.append(Spacer(1, 0.3*inch))
    
    # Summary Statistics
    summary_heading = Paragraph("Summary Statistics", heading_style)
    elements.append(summary_heading)
    
    reco_counts = df['Recommendation'].value_counts()
    summary_data = [['Recommendation', 'Count', 'Percentage']]
    for reco, count in reco_counts.items():
        pct = (count / len(df)) * 100
        summary_data.append([reco, str(count), f"{pct:.1f}%"])
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 1*inch, 1.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Stock Recommendations Table
    reco_heading = Paragraph("Stock Recommendations", heading_style)
    elements.append(reco_heading)
    
    # Prepare table data
    table_data = [['Date', 'Stock', 'Sector', 'CMP', 'Target', 'Upside%', 'Reco']]
    
    for _, row in df.iterrows():
        table_data.append([
            row['Date'],
            row['Stock'][:25],  # Truncate long names
            row['Sector'],
            f"₹{row['CMP']:.2f}" if isinstance(row['CMP'], (int, float)) else str(row['CMP']),
            f"₹{row['Target']:.2f}" if isinstance(row['Target'], (int, float)) else str(row['Target']),
            f"{row['Upside']:.1f}%" if isinstance(row['Upside'], (int, float)) else str(row['Upside']),
            row['Recommendation']
        ])
    
    # Create table with appropriate column widths
    col_widths = [0.8*inch, 1.5*inch, 0.9*inch, 0.8*inch, 0.8*inch, 0.7*inch, 1*inch]
    recommendations_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    # Table styling
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    
    # Color code recommendations
    for i, row in enumerate(table_data[1:], start=1):
        if 'Buy' in row[-1]:
            table_style.add('TEXTCOLOR', (6, i), (6, i), colors.green)
            table_style.add('FONTNAME', (6, i), (6, i), 'Helvetica-Bold')
        elif 'Sell' in row[-1]:
            table_style.add('TEXTCOLOR', (6, i), (6, i), colors.red)
            table_style.add('FONTNAME', (6, i), (6, i), 'Helvetica-Bold')
        elif 'Hold' in row[-1]:
            table_style.add('TEXTCOLOR', (6, i), (6, i), colors.orange)
            table_style.add('FONTNAME', (6, i), (6, i), 'Helvetica-Bold')
    
    recommendations_table.setStyle(table_style)
    elements.append(recommendations_table)
    
    # Footer
    elements.append(Spacer(1, 0.3*inch))
    footer_text = """
    <b>Disclaimer:</b> This report is for informational purposes only. The recommendations are based on 
    Motilal Oswal research reports and should not be considered as investment advice. Please consult 
    with your financial advisor before making any investment decisions. Past performance is not 
    indicative of future results. Investments in securities are subject to market risks.
    """
    footer_para = Paragraph(footer_text, ParagraphStyle('Footer', parent=normal_style, fontSize=8))
    elements.append(footer_para)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Main App
def main():
    # Header
    st.markdown('<h1 class="main-header">📊 Motilal Oswal Stock Recommendations</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Live Stock Analysis & Recommendations Dashboard</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://via.placeholder.com/250x80/667eea/ffffff?text=Motilal+Oswal", use_container_width=True)
        st.markdown("---")
        
        st.subheader("⚙️ Filter Options")
        
        # Data Source Selection
        data_source = st.radio(
            "Data Source",
            ["Live Data (Trendlyne)", "Sample Data (Demo)"],
            help="Choose between live data or sample demonstration data"
        )
        
        # Fetch or create data
        if data_source == "Live Data (Trendlyne)":
            with st.spinner("Fetching live data..."):
                df = fetch_trendlyne_data()
                if df is None:
                    st.warning("⚠️ Could not fetch live data. Using sample data instead.")
                    df = create_sample_data()
                else:
                    st.success("✅ Live data loaded successfully!")
        else:
            df = create_sample_data()
        
        # Ensure numeric columns
        if 'CMP' in df.columns:
            df['CMP'] = pd.to_numeric(df['CMP'].astype(str).str.replace('₹', '').str.replace(',', ''), errors='coerce')
        if 'Target' in df.columns:
            df['Target'] = pd.to_numeric(df['Target'].astype(str).str.replace('₹', '').str.replace(',', ''), errors='coerce')
        if 'Upside' in df.columns:
            df['Upside'] = pd.to_numeric(df['Upside'].astype(str).str.replace('%', '').str.replace(',', ''), errors='coerce')
        
        st.markdown("---")
        
        # Filters
        recommendation_filter = st.selectbox(
            "Recommendation Type",
            ["All"] + sorted(df['Recommendation'].unique().tolist())
        )
        
        sector_filter = st.selectbox(
            "Sector",
            ["All"] + sorted(df['Sector'].unique().tolist()) if 'Sector' in df.columns else ["All"]
        )
        
        min_upside = st.slider(
            "Minimum Upside %",
            min_value=0,
            max_value=50,
            value=0,
            step=5
        )
        
        st.markdown("---")
        
        # Auto Refresh
        auto_refresh = st.checkbox("Auto Refresh (5 min)", value=False)
        if auto_refresh:
            st.info("🔄 Dashboard will refresh every 5 minutes")
        
        refresh_button = st.button("🔄 Refresh Now", use_container_width=True)
        
        if refresh_button:
            st.cache_data.clear()
            st.rerun()
    
    # Apply filters
    filtered_df = df.copy()
    
    filters = {
        'recommendation': recommendation_filter,
        'sector': sector_filter,
        'min_upside': min_upside
    }
    
    if recommendation_filter != "All":
        filtered_df = filtered_df[filtered_df['Recommendation'] == recommendation_filter]
    
    if sector_filter != "All" and 'Sector' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Sector'] == sector_filter]
    
    if min_upside > 0:
        filtered_df = filtered_df[filtered_df['Upside'] >= min_upside]
    
    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📋 Total Recommendations",
            value=len(filtered_df),
            delta=f"{len(filtered_df) - len(df) if recommendation_filter != 'All' else 0}"
        )
    
    with col2:
        buy_count = len(filtered_df[filtered_df['Recommendation'].str.contains('Buy', case=False, na=False)])
        st.metric(
            label="✅ Buy Signals",
            value=buy_count,
            delta=f"{(buy_count/len(filtered_df)*100):.1f}%" if len(filtered_df) > 0 else "0%"
        )
    
    with col3:
        avg_upside = filtered_df['Upside'].mean() if len(filtered_df) > 0 else 0
        st.metric(
            label="📈 Avg Upside",
            value=f"{avg_upside:.2f}%",
            delta=f"Max: {filtered_df['Upside'].max():.1f}%" if len(filtered_df) > 0 else "0%"
        )
    
    with col4:
        max_upside_stock = filtered_df.loc[filtered_df['Upside'].idxmax(), 'Stock'] if len(filtered_df) > 0 else "N/A"
        st.metric(
            label="🏆 Top Pick",
            value=max_upside_stock[:15] + "..." if len(max_upside_stock) > 15 else max_upside_stock,
            delta=f"{filtered_df['Upside'].max():.1f}%" if len(filtered_df) > 0 else "0%"
        )
    
    st.markdown("---")
    
    # Charts Section
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Recommendation Distribution")
        if len(filtered_df) > 0:
            reco_counts = filtered_df['Recommendation'].value_counts()
            fig = px.pie(
                values=reco_counts.values,
                names=reco_counts.index,
                color_discrete_sequence=['#11998e', '#eb3349', '#f093fb', '#667eea'],
                hole=0.4
            )
            fig.update_layout(
                showlegend=True,
                height=350,
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for selected filters")
    
    with col2:
        st.subheader("📈 Upside Potential by Stock")
        if len(filtered_df) > 0:
            top_10 = filtered_df.nlargest(10, 'Upside')
            fig = px.bar(
                top_10,
                x='Upside',
                y='Stock',
                orientation='h',
                color='Recommendation',
                color_discrete_map={
                    'Buy': '#11998e',
                    'Strong Buy': '#06d6a0',
                    'Sell': '#eb3349',
                    'Hold': '#f093fb'
                }
            )
            fig.update_layout(
                showlegend=True,
                height=350,
                margin=dict(t=20, b=20, l=20, r=20),
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for selected filters")
    
    st.markdown("---")
    
    # Sector Analysis
    if 'Sector' in filtered_df.columns:
        st.subheader("🏢 Sector-wise Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            sector_counts = filtered_df['Sector'].value_counts().head(10)
            fig = px.bar(
                x=sector_counts.values,
                y=sector_counts.index,
                orientation='h',
                labels={'x': 'Count', 'y': 'Sector'},
                color=sector_counts.values,
                color_continuous_scale='Viridis'
            )
            fig.update_layout(
                title="Top 10 Sectors by Recommendation Count",
                height=400,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            sector_upside = filtered_df.groupby('Sector')['Upside'].mean().sort_values(ascending=False).head(10)
            fig = px.bar(
                x=sector_upside.values,
                y=sector_upside.index,
                orientation='h',
                labels={'x': 'Average Upside %', 'y': 'Sector'},
                color=sector_upside.values,
                color_continuous_scale='RdYlGn'
            )
            fig.update_layout(
                title="Top 10 Sectors by Average Upside",
                height=400,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Detailed Recommendations Table
    st.subheader("📋 Detailed Stock Recommendations")
    
    # Action buttons
    col1, col2, col3 = st.columns([2, 1, 1])
    with col2:
        export_csv = st.button("📥 Download CSV", use_container_width=True)
    with col3:
        export_pdf = st.button("📄 Download PDF", use_container_width=True)
    
    # Display table with formatting
    if len(filtered_df) > 0:
        display_df = filtered_df.copy()
        
        # Format numeric columns
        if 'CMP' in display_df.columns:
            display_df['CMP'] = display_df['CMP'].apply(lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "N/A")
        if 'Target' in display_df.columns:
            display_df['Target'] = display_df['Target'].apply(lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "N/A")
        if 'Upside' in display_df.columns:
            display_df['Upside'] = display_df['Upside'].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A")
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=500,
            hide_index=True
        )
    else:
        st.warning("⚠️ No recommendations match your filter criteria")
    
    # Export handlers
    if export_csv and len(filtered_df) > 0:
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="⬇️ Click to Download CSV",
            data=csv,
            file_name=f"motilal_oswal_recommendations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        st.success("✅ CSV file ready for download!")
    
    if export_pdf and len(filtered_df) > 0:
        with st.spinner("Generating PDF report..."):
            pdf_buffer = generate_pdf_report(filtered_df, filters)
            st.download_button(
                label="⬇️ Click to Download PDF",
                data=pdf_buffer,
                file_name=f"motilal_oswal_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            st.success("✅ PDF report generated successfully!")
    
    # Footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #666; padding: 20px;'>
            <p><b>📊 Motilal Oswal Stock Recommendations Dashboard</b></p>
            <p style='font-size: 0.9rem;'>
                Last Updated: {} | Data Source: {}
            </p>
            <p style='font-size: 0.8rem; margin-top: 10px;'>
                <b>Disclaimer:</b> This dashboard is for informational purposes only. 
                Please consult with a financial advisor before making investment decisions.
            </p>
        </div>
    """.format(
        datetime.now().strftime("%d %B %Y, %I:%M %p"),
        "Trendlyne (Live)" if data_source == "Live Data (Trendlyne)" else "Sample Data"
    ), unsafe_allow_html=True)
    
    # Auto-refresh logic
    if auto_refresh:
        import time
        time.sleep(300)  # 5 minutes
        st.rerun()

if __name__ == "__main__":
    main()
