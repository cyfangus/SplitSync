    elif menu == "Analytics & Export":
        st.title("📊 Analytics & Export")
        
        tab_analytics, tab_export = st.tabs(["📈 Interactive Charts", "📥 Export Data"])
        
        with tab_analytics:
            if df.empty:
                st.info("No expenses to analyze yet.")
            else:
                col1, col2 = st.columns(2)
                
                with col1:
                    # 1. Spending by Category
                    st.subheader("Spending by Category")
                    fig_cat = px.pie(df, values='amount', names='category', title='Total Spending by Category', hole=0.4)
                    st.plotly_chart(fig_cat, use_container_width=True)
                
                with col2:
                    # 3. Spending by Member
                    st.subheader("Spending by Member")
                    # Need to calculate total spent by each payer
                    payer_stats = df.groupby('payer')['amount'].sum().reset_index()
                    fig_payer = px.bar(payer_stats, x='payer', y='amount', color='payer', title='Total Spent by Member')
                    st.plotly_chart(fig_payer, use_container_width=True)

                # 2. Spending Over Time
                st.subheader("Spending Over Time")
                # Group by date and category
                # Ensure date is datetime
                df['date_dt'] = pd.to_datetime(df['date'])
                df_daily = df.groupby(['date_dt', 'category'])['amount'].sum().reset_index()
                fig_time = px.bar(df_daily, x='date_dt', y='amount', color='category', title='Daily Spending by Category')
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
                    doc = SimpleDocTemplate(buffer, pagesize=letter)
                    elements = []
                    styles = getSampleStyleSheet()
                    
                    # Title
                    elements.append(Paragraph(f"Event Report: {current_event['name']}", styles['Title']))
                    elements.append(Spacer(1, 12))
                    
                    # Summary Stats
                    total_spent = df['amount'].sum() if not df.empty else 0
                    elements.append(Paragraph(f"Total Expenses: {format_currency(total_spent)}", styles['Normal']))
                    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
                    elements.append(Spacer(1, 12))
                    
                    # Expenses Table
                    if not df.empty:
                        elements.append(Paragraph("Expenses Summary", styles['Heading2']))
                        data = [['Date', 'Title', 'Payer', 'Amount']]
                        for _, row in df.iterrows():
                            date_str = str(row['date'])
                            if isinstance(row['date'], (datetime, pd.Timestamp)):
                                date_str = row['date'].strftime('%Y-%m-%d')
                                
                            data.append([
                                date_str,
                                row['title'][:30], # Truncate title
                                row['payer'],
                                f"{row['amount']:.2f}"
                            ])
                        
                        t = Table(data)
                        t.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
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
