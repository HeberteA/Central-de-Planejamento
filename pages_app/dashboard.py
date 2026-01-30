import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from modules import database
from modules import ui

def load_data(supabase, obra_id, start_date, end_date):
    # 1. INDICADORES (PPC/PAP)
    # O erro ocorria aqui: a coluna correta é 'data_referencia' e não 'data_inicio_semana'
    resp_ind = supabase.table("pcp_historico_indicadores")\
        .select("*")\
        .eq("obra_id", obra_id)\
        .gte("data_referencia", start_date)\
        .lte("data_referencia", end_date)\
        .order("data_referencia").execute()
    
    df_ind = pd.DataFrame(resp_ind.data) if resp_ind.data else pd.DataFrame()

    # Tratamento: Transformar de Formato Longo (Linhas) para Largo (Colunas)
    # Se a tabela tiver 'tipo_indicador', fazemos o pivot
    if not df_ind.empty and 'tipo_indicador' in df_ind.columns:
        # Converte para datetime
        df_ind['data_ref'] = pd.to_datetime(df_ind['data_referencia']).dt.date
        
        # Pivot: Transforma valores de 'PPC' e 'PAP' em colunas
        df_pivot = df_ind.pivot_table(
            index='data_ref', 
            columns='tipo_indicador', 
            values='valor_percentual', 
            aggfunc='mean' # Caso haja duplicatas, pega a media
        ).reset_index()
        
        # Renomeia colunas para facilitar (data, ppc, pap)
        df_pivot.columns = [str(c).lower() for c in df_pivot.columns]
        
        # Garante que as colunas existam mesmo que nao tenha dados
        if 'ppc' not in df_pivot.columns: df_pivot['ppc'] = 0
        if 'pap' not in df_pivot.columns: df_pivot['pap'] = 0
        
        df_ind = df_pivot
        # Renomeia para padronizar com o grafico
        df_ind.rename(columns={'data_ref': 'data'}, inplace=True)
        
    elif not df_ind.empty:
        # Fallback se a tabela ja estiver no formato largo (colunas ppc/pap existem)
        if 'data_referencia' in df_ind.columns:
            df_ind['data'] = pd.to_datetime(df_ind['data_referencia']).dt.date
    else:
        df_ind = pd.DataFrame(columns=['data', 'ppc', 'pap'])

    # 2. IRR (Restrições)
    resp_irr = supabase.table("pcp_historico_irr")\
        .select("*")\
        .eq("obra_id", obra_id)\
        .gte("data_referencia", start_date)\
        .lte("data_referencia", end_date)\
        .order("data_referencia").execute()
    df_irr = pd.DataFrame(resp_irr.data) if resp_irr.data else pd.DataFrame()
    if not df_irr.empty:
        df_irr['data'] = pd.to_datetime(df_irr['data_referencia']).dt.date

    # 3. PROBLEMAS (Causas)
    resp_prob = supabase.table("pcp_historico_problemas")\
        .select("*")\
        .eq("obra_id", obra_id)\
        .gte("data_referencia", start_date)\
        .lte("data_referencia", end_date).execute()
    df_prob = pd.DataFrame(resp_prob.data) if resp_prob.data else pd.DataFrame()

    # 4. RESTRIÇÕES ATUAIS
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

    # Carrega dados com as correções de coluna e pivot
    df_ind, df_irr, df_prob, df_rest_atuais = load_data(supabase, obra_id, s_date.strftime('%Y-%m-%d'), e_date.strftime('%Y-%m-%d'))

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    
    # Calculos seguros
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
                df_ind = df_ind.sort_values('data')
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_ind['data'], y=df_ind['ppc'],
                    mode='lines+markers', name='PPC (Semanal)',
                    line=dict(color='#3B82F6', width=3)
                ))
                fig.add_trace(go.Scatter(
                    x=df_ind['data'], y=df_ind['pap'],
                    mode='lines+markers', name='PAP (Diario)',
                    line=dict(color='#4ADE80', width=3, dash='dot')
                ))
                fig.add_hline(y=80, line_dash="dash", line_color="white", annotation_text="Meta 80%")
                
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white", xaxis_title="Semana", yaxis_title="Percentual",
                    legend=dict(orientation="h", y=1.1, x=0), height=350,
                    margin=dict(l=20, r=20, t=20, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados de producao no periodo.")

        with g2:
            st.markdown("##### Volume de Atividades")
            # Tenta estimar o total programado baseado no PPC se não tiver a coluna explicita
            if not df_ind.empty and 'ppc' in df_ind.columns:
                # Mock visual para exemplo se não tiver dados brutos de qtd
                # O ideal seria ter a coluna 'atividades_totais' no histórico, mas vamos usar o PPC
                fig_vol = go.Figure()
                
                # Exibe apenas PPC em barra se não tivermos contagem absoluta no historico
                fig_vol.add_trace(go.Bar(
                    x=df_ind['data'], y=df_ind['ppc'],
                    name='Desempenho', marker_color='#3B82F6'
                ))
                fig_vol.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white", xaxis_title="Semana", yaxis_title="%",
                    height=350
                )
                st.plotly_chart(fig_vol, use_container_width=True)
            else:
                st.info("Sem dados suficientes.")

    with t2:
        r1, r2 = st.columns(2)
        
        with r1:
            st.markdown("##### Evolucao IRR")
            if not df_irr.empty:
                df_irr = df_irr.sort_values('data')
                fig_irr = go.Figure()
                fig_irr.add_trace(go.Scatter(
                    x=df_irr['data'], y=df_irr['irr_percentual'],
                    mode='lines+markers+text', text=df_irr['irr_percentual'].apply(lambda x: f"{x:.0f}%"),
                    textposition="top center",
                    name='IRR', line=dict(color='#E37026', width=3)
                ))
                fig_irr.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white", xaxis_title="Semana", yaxis_title="IRR (%)",
                    height=350, margin=dict(l=20, r=20, t=20, b=20)
                )
                st.plotly_chart(fig_irr, use_container_width=True)
            else:
                st.info("Sem dados de IRR.")

        with r2:
            st.markdown("##### Balanco: Identificadas vs Removidas")
            if not df_irr.empty:
                fig_bal = go.Figure()
                fig_bal.add_trace(go.Bar(
                    x=df_irr['data'], y=df_irr['restricoes_totais'],
                    name='Total Estoque', marker_color='#EF4444'
                ))
                fig_bal.add_trace(go.Bar(
                    x=df_irr['data'], y=df_irr['restricoes_removidas'],
                    name='Removidas', marker_color='#10B981'
                ))
                fig_bal.update_layout(
                    barmode='group',
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white", xaxis_title="Semana", yaxis_title="Quantidade",
                    legend=dict(orientation="h", y=1.1, x=0), height=350
                )
                st.plotly_chart(fig_bal, use_container_width=True)
            else:
                st.info("Sem dados.")

        st.markdown("---")
        st.markdown("##### Restricoes Pendentes (Snapshot Atual)")
        
        rp1, rp2 = st.columns(2)
        
        with rp1:
            if not df_rest_atuais.empty:
                df_rest_atuais['area'] = df_rest_atuais['area'].fillna('GERAL')
                df_pizza = df_rest_atuais['area'].value_counts().reset_index()
                df_pizza.columns = ['area', 'count']
                
                fig_pie = px.pie(df_pizza, values='count', names='area', title='Por Area', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white", height=300
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Nenhuma pendencia.")
        
        with rp2:
            if not df_rest_atuais.empty:
                df_prio = df_rest_atuais['prioridade'].value_counts().reset_index()
                df_prio.columns = ['prioridade', 'count']
                
                fig_bar_p = px.bar(df_prio, x='prioridade', y='count', title='Por Prioridade', color='prioridade', 
                                   color_discrete_map={'Alta': '#EF4444', 'Media': '#F59E0B', 'Baixa': '#3B82F6'})
                fig_bar_p.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white", height=300
                )
                st.plotly_chart(fig_bar_p, use_container_width=True)

    with t3:
        st.markdown("##### Analise de Causas Raiz (Pareto)")
        if not df_prob.empty:
            # Tenta identificar a coluna correta de problema (problema ou problema_descricao)
            col_prob = 'problema_descricao' if 'problema_descricao' in df_prob.columns else 'problema'
            
            if col_prob in df_prob.columns:
                df_pareto = df_prob.groupby(col_prob)['quantidade'].sum().reset_index()
                df_pareto = df_pareto.sort_values('quantidade', ascending=False)
                
                df_pareto['acumulado'] = df_pareto['quantidade'].cumsum()
                df_pareto['perc_acumulado'] = (df_pareto['acumulado'] / df_pareto['quantidade'].sum()) * 100
                
                fig_par = go.Figure()
                fig_par.add_trace(go.Bar(
                    x=df_pareto[col_prob], y=df_pareto['quantidade'],
                    name='Ocorrencias', marker_color='#EF4444'
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
                    height=450,
                    legend=dict(orientation="h", y=1.1, x=0)
                )
                st.plotly_chart(fig_par, use_container_width=True)
                
                st.markdown("##### Detalhamento")
                st.dataframe(df_pareto, use_container_width=True, hide_index=True)
            else:
                st.error("Coluna de descrição do problema não encontrada.")
        else:
            st.info("Nenhum problema registrado no periodo.")
