from data_fetcher import get_stock_sector
import streamlit as st
import pandas as pd
from datetime import datetime

def render(coiled_data, extract_clean_recommendation, render_unified_strategy_table, IST_TIMEZONE):
    st.markdown("### 🌀 Volatility Contraction Pattern (VCP) Squeeze")
    st.markdown("<p style='font-size:0.9rem; color:#94a3b8;'>Scan for coiled springs in final contraction (VCP) setups—price compressing tightly with drying volume *before* breakout.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    # 1. Metrics row
    c_m1, c_m2, c_m3 = st.columns(3)
    
    if coiled_data:
        coiled_count = len(coiled_data)
        min_range = min(r['range_5d'] for r in coiled_data)
        avg_squeeze = sum(r['squeeze_score'] for r in coiled_data) / coiled_count
    else:
        coiled_count = 0
        min_range = 0.0
        avg_squeeze = 0.0
        
    c_m1.markdown(f'<div class="glass-card metric-glow-blue"><p style="font-size:0.85rem; color:#94a3b8; margin:0;">Coiled Setups Found</p><h3 style="font-size:1.8rem; margin:5px 0 0 0; color:#29b6f6;">{coiled_count}</h3></div>', unsafe_allow_html=True)
    c_m2.markdown(f'<div class="glass-card metric-glow-green"><p style="font-size:0.85rem; color:#94a3b8; margin:0;">Tightest 5d Price Range</p><h3 style="font-size:1.8rem; margin:5px 0 0 0; color:#00e676;">{min_range:.2f}%</h3></div>', unsafe_allow_html=True)
    c_m3.markdown(f'<div class="glass-card metric-glow-amber"><p style="font-size:0.85rem; color:#94a3b8; margin:0;">Avg Squeeze Rating</p><h3 style="font-size:1.8rem; margin:5px 0 0 0; color:#ffa000;">{avg_squeeze:.1f} <span style="font-size: 1.1rem; color: #94a3b8;">pts</span></h3></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 2. Results table
    if coiled_data is None:
        st.info("ℹ️ Run the scanner from the sidebar to identify pre-breakout coiled spring setups.")
    elif len(coiled_data) == 0:
        st.info("ℹ️ No coiled spring (VCP) setups found today matching these filters. Price ranges might not be tight enough yet (must be <= 7.0% over the last 5 days with dried volume).")
    else:
        # Sort results descending by score
        sorted_coiled = sorted(coiled_data, key=lambda x: x['squeeze_score'], reverse=True)
        
        # Download Coiled Results Option
        export_coiled = []
        for r in sorted_coiled:
            export_coiled.append({
                "Symbol": r['symbol'],
                "Sector": get_stock_sector(r['symbol']),
                                "CMP (₹)": r['cmp'],
                "5-Day Range %": r['range_5d'],
                "Previous Range %": r['range_prev'],
                "Volume Ratio": r['vol_ratio'],
                "Squeeze Score": r['squeeze_score'],
                "Above 20 EMA": r.get('above_20ema', True),
                "Buy Range (₹)": r.get('buy_price', r.get('cmp', 0)),
                "Stop Loss (₹)": r.get('exit_price', 0),
                "Target (₹)": r.get('target_price', 0),
                "Confidence": r.get('confidence', ''),
                "Recommendation": extract_clean_recommendation(r.get('recommendation', ''))
            })
        export_c_df = pd.DataFrame(export_coiled)
        csv_c_data = export_c_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Download Coiled Squeezes (CSV)",
            data=csv_c_data,
            file_name=f"coiled_squeezes_{datetime.now(IST_TIMEZONE).strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="dl_coiled_top_btn"
        )
        
        st.markdown("---")
        # Render the unified Trade Execution Matrix
        st.markdown("### 🎯 Active Final Contraction Squeezes Trade Execution Sheet")
        render_unified_strategy_table(sorted_coiled, "coiled_spring", "coiled_tab")
