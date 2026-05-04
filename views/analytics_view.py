import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from utils import format_currency

def render_analytics(current_event):
    """Render the Analytics & Export page."""
    st.title("📊 Analytics & Export")
    
    # Data Prep
    df = pd.DataFrame(current_event['expenses'])
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    
    tab_analytics, tab_export = st.tabs(["📈 Interactive Charts", "📥 Export Data"])
    
    with tab_analytics:
        if df.empty:
            st.info("No expenses to analyze yet.")
        else:
            # Filter Controls
            st.markdown("### 🔍 Filters")
            with st.expander("Filter Options", expanded=False):
                filter_col1, filter_col2, filter_col3 = st.columns(3)
                
                with filter_col1:
                    # Date Range Filter
                    df['date_dt'] = pd.to_datetime(df['date'])
                    min_date = df['date_dt'].min().date()
                    max_date = df['date_dt'].max().date()
                    
                    date_range = st.date_input(
                        "Date Range",
                        value=(min_date, max_date),
                        min_value=min_date,
                        max_value=max_date,
                        help="Select start and end dates"
                    )
                
                with filter_col2:
                    # Payer Filter
                    all_payers = df['payer'].unique().tolist()
                    selected_payers = st.multiselect(
                        "Payers",
                        options=all_payers,
                        default=all_payers,
                        help="Select members to include"
                    )
                
                with filter_col3:
                    # Category Filter
                    all_categories = df['category'].unique().tolist()
                    selected_categories = st.multiselect(
                        "Categories",
                        options=all_categories,
                        default=all_categories,
                        help="Select categories to include"
                    )
            
            # Apply Filters
            df_filtered = df.copy()
            
            # Date filter
            if len(date_range) == 2:
                start_date, end_date = date_range
                df_filtered = df_filtered[
                    (df_filtered['date_dt'].dt.date >= start_date) & 
                    (df_filtered['date_dt'].dt.date <= end_date)
                ]
            
            # Payer filter
            if selected_payers:
                df_filtered = df_filtered[df_filtered['payer'].isin(selected_payers)]
            
            # Category filter
            if selected_categories:
                df_filtered = df_filtered[df_filtered['category'].isin(selected_categories)]
            
            # Show filtered results count
            st.caption(f"Showing {len(df_filtered)} of {len(df)} expenses")
            st.divider()
            
            if df_filtered.empty:
                st.warning("No expenses match the selected filters.")
            else:
                col1, col2 = st.columns(2)
                
                with col1:
                    # 1. Spending by Category
                    st.subheader("Spending by Category")
                    fig_cat = px.pie(df_filtered, values='amount', names='category', 
                                    title='Total Spending by Category', hole=0.4)
                    st.plotly_chart(fig_cat, use_container_width=True)
                
                with col2:
                    # 3. Spending by Member
                    st.subheader("Spending by Member")
                    payer_stats = df_filtered.groupby('payer')['amount'].sum().reset_index()
                    fig_payer = px.bar(payer_stats, x='payer', y='amount', color='payer', 
                                      title='Total Spent by Member')
                    st.plotly_chart(fig_payer, use_container_width=True)

                # 2. Spending Over Time
                st.subheader("Spending Over Time")
                df_daily = df_filtered.groupby('date_dt')['amount'].sum().reset_index()
                fig_time = px.line(df_daily, x='date_dt', y='amount', 
                                   title='Daily Total Spending',
                                   markers=True)
                fig_time.update_traces(line_color='#1f77b4', line_width=3)
                st.plotly_chart(fig_time, use_container_width=True)
            
    with tab_export:
        st.subheader("📥 Export Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### CSV Exports")
            
            # Export Expenses
            if not df.empty:
                csv_expenses = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Download Expenses (CSV)",
                    data=csv_expenses,
                    file_name=f"expenses_{current_event['name']}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime='text/csv',
                )
            else:
                st.button("📄 Download Expenses (CSV)", disabled=True)
            
            # Export Settlements
            settlements = current_event.get('settlements', [])
            if settlements:
                df_settlements = pd.DataFrame(settlements)
                csv_settlements = df_settlements.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="🤝 Download Settlements (CSV)",
                    data=csv_settlements,
                    file_name=f"settlements_{current_event['name']}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime='text/csv',
                )
            else:
                st.button("🤝 Download Settlements (CSV)", disabled=True)
        
        with col2:
            st.markdown("### PDF Reports")
            
            def create_pdf_report():
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
                elements = []
                styles = getSampleStyleSheet()
                
                # Title
                elements.append(Paragraph(f"Event Report: {current_event['name']}", styles['Title']))
                elements.append(Spacer(1, 12))
                
                # Summary Stats
                total_spent = df['amount'].sum() if not df.empty else 0
                elements.append(Paragraph(f"Total Expenses: {format_currency(total_spent, current_event.get('currency', 'USD'))}", styles['Normal']))
                elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
                elements.append(Spacer(1, 12))
                
                # Expenses Table
                if not df.empty:
                    elements.append(Paragraph("Expenses Summary", styles['Heading2']))
                    data = [['Date', 'Title', 'Payer', 'Amount', 'Split Among']]
                    for _, row in df.iterrows():
                        date_str = str(row['date'])
                        if isinstance(row['date'], (datetime, pd.Timestamp)):
                            date_str = row['date'].strftime('%Y-%m-%d')
                        
                        # Build the split-among string
                        involved = row.get('involved', [])
                        if isinstance(involved, list):
                            split_among = ', '.join(involved)
                        else:
                            split_among = str(involved)
                            
                        data.append([
                            date_str,
                            row['title'][:30],  # Truncate long titles
                            row['payer'],
                            f"{row['amount']:.2f}",
                            split_among
                        ])
                    
                    t = Table(data, repeatRows=1)
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('ALIGN', (4, 1), (4, -1), 'LEFT'),  # Left-align Split Among column
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.beige, colors.white]),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    elements.append(t)
                
                doc.build(elements)
                return buffer.getvalue()

            # Generate PDF button
            # We generate it on click to avoid overhead
            if not df.empty:
                pdf_data = create_pdf_report()
                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=pdf_data,
                    file_name=f"report_{current_event['name']}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime='application/pdf'
                )
            else:
                st.button("⬇️ Download PDF Report", disabled=True)
