import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from modules import database
from modules import ui

def load_data(supabase, obra_id, start_date, end_date):
    resp_ind = supabase.table("pcp_historico_indicadores").select("*").eq("obra_id", obra_id).gte("data_inicio_semana", start_date).lte("data_inicio_semana", end_date).order("data_inicio_semana").execute()
    df_ind = pd.DataFrame(resp_ind.data) if resp_ind.data else pd.DataFrame()

    resp_irr = supabase.table("pcp_historico_irr").select("*").eq("obra_id", obra_id).gte("data_referencia", start_date).lte("data_referencia", end_date).order("data_referencia").execute()
    df_irr = pd.DataFrame(resp_irr.data) if resp_irr.data else pd.DataFrame()

    resp_prob = supabase.table("pcp_historico_problemas").select("*").eq("obra_id", obra_id).gte("data_inicio_semana", start_date).lte("data_inicio_semana", end_date).execute()
    df_prob = pd.DataFrame(resp_prob.data) if resp_prob.data else pd.DataFrame()

    resp_rest = supabase.table("pcp_restricoes").select("*").eq("obra_id", obra_id).eq("status", "Pendente").execute()
    df_rest_atuais = pd.DataFrame(resp_rest.data) if resp_rest.data else pd.DataFrame()

    return df_ind, df_irr, df_prob, df_rest_atuais

def card_metrica(label, value, suffix="", color="#1E1E1E"):
    st.markdown(f"""
    <div style="background-color: {color}; padding: 20px; border-radius: 8px; border: 1px solid #333; text-align: center; height: 100%;">
        <div style="font-size: 0.85rem; color: #aaa; text-transform: uppercase; margin-bottom: 5px;">{label}</div>
        <div style="font-size: 2rem; font-weight: bold; color: white;">{value}<span style="font-size: 1rem; color: #888;">{suffix}</span></div>
    </div>
    """, unsafe_allow_html=True)

def app(obra_id):
    st.markdown("### Dashboard Geral")
    
    supabase = database.get_db_client()

    c_filtros = st.container()
    col_f1, col_f2 = c_filtros.columns([3, 1])
    
    with col_f1:
        d_end = datetime.now()
        d_start = d_end - timedelta(days=90)
        dates = st.date_input("Periodo de Analise", [d_start, d_end])
        
        if len(dates) == 2:
            s_date, e_date = dates
        else:
            s_date, e_date = d_start, d_end
            
    with col_f2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Atualizar Dados", use_container_width=True):
            st.rerun()

    df_ind, df_irr, df_prob, df_rest_atuais = load_data(supabase, obra_id, s_date.strftime('%Y-%m-%d'), e_date.strftime('%Y-%m-%d'))

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    
    avg_ppc = df_ind['ppc'].mean() if not df_ind.empty and 'ppc' in df_ind.columns else 0
    avg_pap = df_ind['pap'].mean() if not df_ind.empty and 'pap' in df_ind.columns else 0
    avg_irr = df_irr['irr_percentual'].mean() if not df_irr.empty and 'irr_percentual' in df_irr.columns else 0
    total_rest_pendentes = len(df_rest_atuais)

    with col1: card_metrica("Media PPC", f"{avg_ppc:.1f}", "%")
    with col2: card_metrica("Media PAP", f"{avg_pap:.1f}", "%")
    with col3: card_metrica("Media IRR", f"{avg_irr:.1f}", "%")
    with col4: card_metrica("Restricoes Ativas", total_rest_pendentes)

    st.markdown("<br>", unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["Producao", "Restricoes", "Qualidade & Causas"])

    with t1:
        g1, g2 = st.columns([2, 1])
        
        with g1:
            st.markdown("##### Evolucao PPC e PAP")
            if not df_ind.empty:
                df_ind = df_ind.sort_values('data_inicio_semana')
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_ind['data_inicio_semana'], y=df_ind['ppc'],
                    mode='lines+markers', name='PPC (Semanal)',
                    line=dict(color='#3B82F6', width=3)
                ))
                fig.add_trace(go.Scatter(
                    x=df_ind['data_inicio_semana'], y=df_ind['pap'],
                    mode='lines+markers', name='PAP (Diario)',
                    line=dict
