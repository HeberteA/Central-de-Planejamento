import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from modules import database
from modules import ui

def load_data(supabase, obra_id, start_date, end_date):
    def apply_query(table, date_col):
        q = supabase.table(table).select("*")
        if obra_id: 
            q = q.eq("obra_id", obra_id)
        
        if date_col:
            q = q.gte(date_col, start_date).lte(date_col, end_date)
        
        if date_col:
            q = q.order(date_col)
            
        return q.execute()

    resp_ind = apply_query("pcp_historico_indicadores", "data_referencia")
    df_ind = pd.DataFrame(resp_ind.data) if resp_ind.data else pd.DataFrame()

    if not df_ind.empty:
        if 'data_referencia' in df_ind.columns:
            df_ind['data_ref'] = pd.to_datetime(df_ind['data_referencia']).dt.date
            
            if 'tipo_indicador' in df_ind.columns:
                df_pivot = df_ind.pivot_table(
                    index='data_ref', 
                    columns='tipo_indicador', 
                    values='valor_percentual', 
                    aggfunc='mean' 
                ).reset_index()
                
                df_pivot.columns = [str(c).lower() for c in df_pivot.columns]
                
                if 'ppc' not in df_pivot.columns: df_pivot['ppc'] = 0
                if 'pap' not in df_pivot.columns: df_pivot['pap'] = 0
                
                df_ind = df_pivot
                df_ind.rename(columns={'data_ref': 'data'}, inplace=True)
            else:
                df_ind['data'] = df_ind['data_ref']
    else:
        df_ind = pd.DataFrame(columns=['data', 'ppc', 'pap'])

    resp_irr = apply_query("pcp_historico_irr", "data_referencia")
    df_irr = pd.DataFrame(resp_irr.data) if resp_irr.data else pd.DataFrame()
    
    if not df_irr.empty:
        df_irr['data'] = pd.to_datetime(df_irr['data_referencia']).dt.date
        if obra_id is None:
            df_irr = df_irr.groupby('data').agg({
                'restricoes_totais': 'sum',
                'restricoes_removidas': 'sum'
            }).reset_index()
            df_irr['irr_percentual'] = (df_irr['restricoes_removidas'] / df_irr['restricoes_totais'] * 100).fillna(0)

    resp_prob = apply_query("pcp_historico_problemas", "data_referencia")
    df_prob = pd.DataFrame(resp_prob.data) if resp_prob.data else pd.DataFrame()

    q_rest = supabase.table("pcp_restricoes").select("*").eq("status", "Pendente")
    if obra_id:
        q_rest = q_rest.eq("obra_id", obra_id)
    resp_rest = q_rest.execute()
    df_rest_atuais = pd.DataFrame(resp_rest.data) if resp_rest.data else pd.DataFrame()

    return df_ind, df_irr, df_prob, df_rest_atuais

def card_metrica(label, value, suffix="", color="#1E1E1E"):
    st.markdown(f"""
    <div style="background-color: {color}; padding: 20px; border-radius: 8px; border: 1px solid #333; text-align: center; height: 100%;">
        <div style="font-size: 0.85rem; color: #aaa; text-transform: uppercase; margin-bottom: 5px;">{label}</div>
        <div style="font-size: 2rem; font-weight: bold; color: white;">{value}<span style="font-size: 1rem; color: #888;">{suffix}</span></div>
    </div>
    """, unsafe_allow_html=True)

def app(obra_id_param):
    st.markdown("### Dashboard Geral")
    
    supabase = database.get_db_client()
    user = st.session_state.get('user', {})
    is_admin = user.get('role') == 'admin'
    
    c_filtros = st.container()
    col_f1, col_f2 = c_filtros.columns([1, 1])
    
    with col_f1:
        obra_id = obra_id_param
        if is_admin:
            try:
                obras_resp = supabase.table("pcp_obras").select("id, nome").order("nome").execute()
                if obras_resp.data:
                    opcoes = {"TODAS AS OBRAS": None}
                    for o in obras_resp.data:
                        opcoes[o['nome']] = o['id']
                
                    idx_selecionado = 0
                    if obra_id_param in opcoes.values():
                        nome_atual = [k for k, v in opcoes.items() if v == obra_id_param][0]
                        idx_selecionado = list(opcoes.keys()).index(nome_atual)
                
                    selected_nome = st.selectbox("Visualizar:", list(opcoes.keys()), index=idx_selecionado)
                    obra_id = opcoes[selected_nome] 
            except: pass

    with col_f2:
        d_end = datetime.now()
        d_start = d_end - timedelta(days=90)
        dates = st.date_input("Periodo", [d_start, d_end])
        
        if len(dates) == 2:
            s_date, e_date = dates
        else:
            s_date, e_date = d_start, d_end

    df_ind, df_irr, df_prob, df_rest_atuais = load_data(supabase, obra_id, s_date.strftime('%Y-%m-%d'), e_date.strftime('%Y-%m-%d'))

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    
    avg_ppc = df_ind['ppc'].mean() if not df_ind.empty and 'ppc' in df_ind.columns else 0
    avg_pap = df_ind['pap'].mean() if not df_ind.empty and 'pap' in df_ind.columns else 0
    avg_irr = df_irr['irr_percentual'].mean() if not df_irr.empty and 'irr_percentual' in df_irr.columns else 0
    total_rest_pendentes = len(df_rest_atuais)

    with col1: card_metrica("Media PPC", f"{avg_ppc:.0f}", "%")
    with col2: card_metrica("Media PAP", f"{avg_pap:.0f}", "%")
    with col3: card_metrica("IRR (Medio)", f"{avg_irr:.0f}", "%")
    with col4: card_metrica("Restricoes Ativas", total_rest_pendentes)

    st.markdown("<br>", unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["Producao (PPC/PAP)", "Restricoes", "Causas & Problemas"])

    with t1:
        if not df_ind.empty:
            df_ind = df_ind.sort_values('data')
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df_ind['data'], y=df_ind['ppc'],
                mode='lines+markers+text', name='PPC (Semanal)',
                text=df_ind['ppc'].apply(lambda x: f"{x:.0f}%"), textposition='top center',
                line=dict(color='#3B82F6', width=3)
            ))
            
            fig.add_trace(go.Scatter(
                x=df_ind['data'], y=df_ind['pap'],
                mode='lines+markers+text', name='PAP (Diario)',
                text=df_ind['pap'].apply(lambda x: f"{x:.0f}%"), textposition='bottom center',
                line=dict(color='#4ADE80', width=3, dash='dot')
            ))
            
            fig.add_hline(y=80, line_dash="dash", line_color="white", annotation_text="Meta 80%")
            
            fig.update_layout(
                title="Evolucao Semanal",
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color="white", xaxis_title="Semana", yaxis_title="Percentual",
                legend=dict(orientation="h", y=1.1, x=1.1), height=450,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de producao no periodo.")

    with t2:
        c_res1, c_res2 = st.columns(2)
        
        with c_res1:
            st.markdown("##### Restrições vs Removidas")
            if not df_irr.empty:
                df_irr = df_irr.sort_values('data')
                
                fig_bal = go.Figure()
                
                fig_bal.add_trace(go.Bar(
                    x=df_irr['data'], y=df_irr['restricoes_totais'],
                    name='Restrições', marker_color='#EF4444',
                    text=df_irr['restricoes_totais'], textposition='auto'
                ))
                fig_bal.add_trace(go.Bar(
                    x=df_irr['data'], y=df_irr['restricoes_removidas'],
                    name='Removidas', marker_color='#10B981',
                    text=df_irr['restricoes_removidas'], textposition='auto'
                ))
                
                fig_bal.update_layout(
                    barmode='group',
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white", xaxis_title="Semana", yaxis_title="Quantidade",
                    legend=dict(orientation="h", y=1.1, x=0), height=400
                )
                st.plotly_chart(fig_bal, use_container_width=True)
            else:
                st.info("Sem dados de restricoes historicas.")

        with c_res2:
            st.markdown("##### Status Atual")
            if not df_rest_atuais.empty:
                df_rest_atuais['area'] = df_rest_atuais['area'].fillna('GERAL')
                df_pizza = df_rest_atuais['area'].value_counts().reset_index()
                df_pizza.columns = ['area', 'count']
                
                fig_pie = px.pie(df_pizza, values='count', names='area', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_traces(textinfo='value+label')
                fig_pie.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white", height=400, showlegend=False
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Nenhuma restricao pendente.")

    with t3:
        st.markdown("##### Analise de Causas Raiz")
        if not df_prob.empty:
            col_prob = 'problema_descricao' if 'problema_descricao' in df_prob.columns else 'problema'
            
            if col_prob in df_prob.columns:
                df_pareto = df_prob.groupby(col_prob)['quantidade'].sum().reset_index()
                df_pareto = df_pareto.sort_values('quantidade', ascending=False)
                
                df_pareto['acumulado'] = df_pareto['quantidade'].cumsum()
                df_pareto['perc_acumulado'] = (df_pareto['acumulado'] / df_pareto['quantidade'].sum()) * 100
                
                fig_par = go.Figure()
                
                fig_par.add_trace(go.Bar(
                    x=df_pareto[col_prob], y=df_pareto['quantidade'],
                    name='Ocorrencias', marker_color='#EF4444',
                    text=df_pareto['quantidade'], textposition='auto'
                ))
                fig_par.add_trace(go.Scatter(
                    x=df_pareto[col_prob], y=df_pareto['perc_acumulado'],
                    name='% Acumulado', yaxis='y2',
                    mode='lines+markers', line=dict(color='white', width=2)
                ))
                
                fig_par.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white",
                    xaxis_title="Causa Raiz", yaxis_title="Frequencia",
                    yaxis2=dict(title="Acumulado (%)", overlaying='y', side='right', range=[0, 110], showgrid=False),
                    height=500,
                    legend=dict(orientation="h", y=1.1, x=0)
                )
                st.plotly_chart(fig_par, use_container_width=True)
            else:
                st.error("Coluna de dados nao encontrada.")
        else:
            st.info("Nenhum problema registrado no periodo.")
