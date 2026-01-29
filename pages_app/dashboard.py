import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from modules import database
from modules import ui
from datetime import datetime, timedelta

def app(obra_id):
    ui.header("Dashboard")

    with st.expander("Filtros"):
        f1, f2, f3 = st.columns(3)
        with f1:
            periodo = st.date_input("Período", [datetime.now() - timedelta(days=90), datetime.now()])
        with f2:
            filtro_local = st.text_input("Local")
        with f3:
            filtro_ind = st.multiselect("Indicadores", ["PPC", "PAP"], default=["PPC", "PAP"])

    df_ind = database.fetch_indicadores_historicos(obra_id)

    if df_ind.empty:
        st.info("Sem dados.")
        return

    if 'data_referencia' in df_ind.columns:
        df_ind['data_referencia'] = pd.to_datetime(df_ind['data_referencia'])
        if len(periodo) == 2:
            mask = (df_ind['data_referencia'].dt.date >= periodo[0]) & (df_ind['data_referencia'].dt.date <= periodo[1])
            df_ind = df_ind.loc[mask]
        df_ind = df_ind.sort_values(by='data_referencia')

    df_ppc = df_ind[df_ind['tipo_indicador'] == 'PPC'].copy()
    df_pap = df_ind[df_ind['tipo_indicador'] == 'PAP'].copy()
    
    ppc_medio = df_ppc['valor_percentual'].mean() if not df_ppc.empty else 0
    pap_medio = df_pap['valor_percentual'].mean() if not df_pap.empty else 0
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: ui.metric_card("PPC Médio", f"{ppc_medio:.1f}%", color="#E37026")
    with c2: ui.metric_card("PAP Médio", f"{pap_medio:.1f}%", color="#3B82F6")
    with c3: ui.metric_card("Desvio Prazo", "0 Dias", color="#888")
    with c4: ui.metric_card("Registros", str(len(df_ind)), color="#888")

    st.markdown("---")

    g1, g2 = st.columns([2, 1])

    with g1:
        st.subheader("Evolução PPC e PAP")
        if not df_ppc.empty:
            fig = go.Figure()
            if "PPC" in filtro_ind:
                fig.add_trace(go.Scatter(
                    x=df_ppc['data_referencia'], y=df_ppc['valor_percentual'],
                    mode='lines+markers+text', name='PPC',
                    line=dict(color='#E37026', width=3),
                    text=df_ppc['valor_percentual'], textposition='top center', texttemplate='%{text:.0f}%'
                ))
            if "PAP" in filtro_ind and not df_pap.empty:
                fig.add_trace(go.Scatter(
                    x=df_pap['data_referencia'], y=df_pap['valor_percentual'],
                    mode='lines', name='PAP',
                    line=dict(color='#3B82F6', width=2, dash='dot')
                ))
            
            fig.add_hline(y=80, line_dash="dash", line_color="#4ADE80", annotation_text="Meta 80%")
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_color="white", xaxis_title="Data", yaxis_title="Percentual",
                legend=dict(orientation="h", y=1.1)
            )
            st.plotly_chart(fig, use_container_width=True)

    with g2:
        st.subheader("Ofensores")
        dados_pareto = pd.DataFrame({
            'Causa': ['Material', 'Mão de Obra', 'Chuva', 'Projeto'],
            'Qtd': [15, 12, 5, 2]
        })
        fig_p = px.bar(dados_pareto, x='Qtd', y='Causa', orientation='h', text='Qtd')
        fig_p.update_traces(marker_color='#EF4444', textposition='outside')
        fig_p.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color="white",
            yaxis={'categoryorder':'total ascending'}
        )
        st.plotly_chart(fig_p, use_container_width=True)