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
            df_ind['data_ref'] = pd.to_datetime(df_ind['data_referencia'])
            
            if 'tipo_indicador' in df_ind.columns:
                # Agrupa por data e semana_ref para preservar o nome da semana
                cols_index = ['data_ref']
                if 'semana_ref' in df_ind.columns:
                    cols_index.append('semana_ref')
                
                df_pivot = df_ind.pivot_table(
                    index=cols_index, 
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
        df_irr['data'] = pd.to_datetime(df_irr['data_referencia'])
        if obra_id is None:
            # Se for todas as obras, recalcula a media ponderada
            df_irr = df_irr.groupby('data').agg({
                'restricoes_totais': 'sum',
                'restricoes_removidas': 'sum'
            }).reset_index()
            df_irr['irr_percentual'] = (df_irr['restricoes_removidas'] / df_irr['restricoes_totais'] * 100).fillna(0)

    resp_prob = apply_query("pcp_historico_problemas", "data_referencia")
    df_prob = pd.DataFrame(resp_prob.data) if resp_prob.data else pd.DataFrame()

    return df_ind, df_irr, df_prob

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

    c_filtros = st.container()
    col_f1, col_f2 = c_filtros.columns([3, 1])
    
    with col_f1:
        d_end = datetime.now()
        d_start = d_end - timedelta(days=90)
        dates = st.date_input("Periodo", [d_start, d_end])
        
        if len(dates) == 2:
            s_date, e_date = dates
        else:
            s_date, e_date = d_start, d_end
            
    with col_f2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Atualizar", use_container_width=True):
            st.rerun()

    df_ind, df_irr, df_prob = load_data(supabase, obra_id, s_date.strftime('%Y-%m-%d'), e_date.strftime('%Y-%m-%d'))

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    
    avg_ppc = df_ind['ppc'].mean() if not df_ind.empty and 'ppc' in df_ind.columns else 0
    avg_pap = df_ind['pap'].mean() if not df_ind.empty and 'pap' in df_ind.columns else 0
    
    if not df_irr.empty:
        total_rem = df_irr['restricoes_removidas'].sum()
        total_tot = df_irr['restricoes_totais'].mean() 
        avg_irr = (total_rem / total_tot * 100) if total_tot > 0 else 0
    else:
        avg_irr = 0
        total_rem = 0

    with col1: card_metrica("PPC Medio", f"{avg_ppc:.0f}", "%")
    with col2: card_metrica("PAP Medio", f"{avg_pap:.0f}", "%")
    with col3: card_metrica("IRR Geral", f"{avg_irr:.0f}", "%")
    with col4: card_metrica("Removidas Total", f"{total_rem:.0f}")

    st.markdown("<br>", unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["Producao", "Restricoes", "Problemas"])

    with t1:
        if not df_ind.empty:
            df_ind = df_ind.sort_values('data')
            
            # Define eixo X: usa semana_ref se existir, senao data
            eixo_x = 'semana_ref' if 'semana_ref' in df_ind.columns else 'data'
            
            st.markdown("##### Desempenho Semanal")
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df_ind[eixo_x], y=df_ind['ppc'],
                mode='lines+markers+text', name='PPC',
                text=df_ind['ppc'].apply(lambda x: f"{x:.0f}%"), textposition='top center',
                line=dict(color='#3B82F6', width=3)
            ))
            
            fig.add_trace(go.Scatter(
                x=df_ind[eixo_x], y=df_ind['pap'],
                mode='lines+markers+text', name='PAP',
                text=df_ind['pap'].apply(lambda x: f"{x:.0f}%"), textposition='bottom center',
                line=dict(color='#4ADE80', width=3, dash='dot')
            ))
            
            fig.add_hline(y=80, line_dash="dash", line_color="white", annotation_text="Meta 80%")
            
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color="white", xaxis_title="Semana", yaxis_title="%",
                legend=dict(orientation="h", y=1.1, x=0), height=400,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown("##### Desempenho Mensal (Consolidado)")
            
            df_ind_m = df_ind.set_index('data').resample('ME').mean().reset_index()
            df_ind_m['mes_ano'] = df_ind_m['data'].dt.strftime('%m/%Y')
            
            fig_m = go.Figure()
            fig_m.add_trace(go.Bar(
                x=df_ind_m['mes_ano'], y=df_ind_m['ppc'],
                name='PPC Mensal', marker_color='#1E3A8A',
                text=df_ind_m['ppc'].apply(lambda x: f"{x:.0f}%"), textposition='auto'
            ))
            fig_m.add_trace(go.Bar(
                x=df_ind_m['mes_ano'], y=df_ind_m['pap'],
                name='PAP Mensal', marker_color='#166534',
                text=df_ind_m['pap'].apply(lambda x: f"{x:.0f}%"), textposition='auto'
            ))
            
            fig_m.update_layout(
                barmode='group',
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color="white", xaxis_title="Mes", yaxis_title="Media %",
                legend=dict(orientation="h", y=1.1, x=0), height=400
            )
            st.plotly_chart(fig_m, use_container_width=True)

        else:
            st.info("Sem dados de producao.")

    with t2:
        if not df_irr.empty:
            df_irr = df_irr.sort_values('data')
            
            st.markdown("##### Fluxo Semanal")
            c_res1, c_res2 = st.columns([2, 1])
            
            with c_res1:
                fig_bal = go.Figure()
                fig_bal.add_trace(go.Bar(
                    x=df_irr['data'], y=df_irr['restricoes_totais'],
                    name='Estoque', marker_color='#EF4444',
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
                    font_color="white", xaxis_title="Semana", yaxis_title="Qtd",
                    legend=dict(orientation="h", y=1.1, x=0), height=350
                )
                st.plotly_chart(fig_bal, use_container_width=True)

            with c_res2:
                fig_irr_line = go.Figure()
                fig_irr_line.add_trace(go.Scatter(
                    x=df_irr['data'], y=df_irr['irr_percentual'],
                    mode='lines+markers+text', name='IRR %',
                    text=df_irr['irr_percentual'].apply(lambda x: f"{x:.0f}%"), textposition='top center',
                    line=dict(color='#E37026', width=3)
                ))
                fig_irr_line.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white", xaxis_title="Semana", yaxis_title="IRR %",
                    showlegend=False, height=350
                )
                st.plotly_chart(fig_irr_line, use_container_width=True)

            st.markdown("---")
            st.markdown("##### Visao Mensal (Acumulado)")
            
            df_irr_m = df_irr.set_index('data').resample('ME').agg({
                'restricoes_totais': 'mean', 
                'restricoes_removidas': 'sum'
            }).reset_index()
            df_irr_m['mes_ano'] = df_irr_m['data'].dt.strftime('%m/%Y')
            
            fig_bal_m = go.Figure()
            fig_bal_m.add_trace(go.Bar(
                x=df_irr_m['mes_ano'], y=df_irr_m['restricoes_totais'],
                name='Media Estoque', marker_color='#991B1B',
                text=df_irr_m['restricoes_totais'].apply(lambda x: f"{x:.0f}"), textposition='auto'
            ))
            fig_bal_m.add_trace(go.Bar(
                x=df_irr_m['mes_ano'], y=df_irr_m['restricoes_removidas'],
                name='Total Removidas', marker_color='#065F46',
                text=df_irr_m['restricoes_removidas'], textposition='auto'
            ))
            fig_bal_m.update_layout(
                barmode='group',
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color="white", xaxis_title="Mes", yaxis_title="Qtd",
                legend=dict(orientation="h", y=1.1, x=0), height=400
            )
            st.plotly_chart(fig_bal_m, use_container_width=True)

        else:
            st.info("Sem dados historicos de restricoes.")

    with t3:
        st.markdown("##### Principais Ofensores (Pareto)")
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
                    xaxis_title="Causa", yaxis_title="Qtd",
                    yaxis2=dict(title="Acumulado (%)", overlaying='y', side='right', range=[0, 110], showgrid=False),
                    height=500,
                    legend=dict(orientation="h", y=1.1, x=0)
                )
                st.plotly_chart(fig_par, use_container_width=True)
            else:
                st.error("Erro na coluna de dados.")
        else:
            st.info("Nenhum problema registrado.")
