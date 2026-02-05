import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from modules import database
from modules import ui

def load_data(supabase, obra_id, start_date, end_date):
    obras_map = {}
    try:
        resp_obras = supabase.table("pcp_obras").select("id, nome").execute()
        if resp_obras.data:
            obras_map = {o['id']: o['nome'] for o in resp_obras.data}
    except: pass

    def apply_query(table, date_col):
        q = supabase.table(table).select("*")
        if obra_id: 
            q = q.eq("obra_id", obra_id)
        
        if date_col:
            q = q.gte(date_col, start_date).lte(date_col, end_date)
        
        if date_col:
            q = q.order(date_col)
            
        return q.execute()

    # 1. INDICADORES (PPC/PAP)
    resp_ind = apply_query("pcp_historico_indicadores", "data_referencia")
    df_ind = pd.DataFrame(resp_ind.data) if resp_ind.data else pd.DataFrame()

    if not df_ind.empty:
        df_ind['obra_nome'] = df_ind['obra_id'].map(obras_map).fillna("Desconhecida")
        if 'data_referencia' in df_ind.columns:
            df_ind['data_ref'] = pd.to_datetime(df_ind['data_referencia'])
            # Cria coluna de ordenacao por Mes/Ano para o grafico de tendencia
            df_ind['mes_ano_label'] = df_ind['data_ref'].dt.strftime('%m/%Y')
            
            # Garante coluna semana_ref
            if 'semana_ref' not in df_ind.columns:
                df_ind['semana_ref'] = df_ind['data_ref'].apply(lambda d: f"Semana {d.isocalendar()[1]}")

            if 'tipo_indicador' in df_ind.columns:
                df_pivot = df_ind.pivot_table(
                    index=['data_ref', 'mes_ano_label', 'semana_ref', 'obra_nome', 'obra_id'], 
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
        df_ind = pd.DataFrame(columns=['data', 'ppc', 'pap', 'obra_nome', 'semana_ref', 'mes_ano_label'])

    # 2. IRR (RESTRICOES)
    resp_irr = apply_query("pcp_historico_irr", "data_referencia")
    df_irr = pd.DataFrame(resp_irr.data) if resp_irr.data else pd.DataFrame()
    
    if not df_irr.empty:
        df_irr['data'] = pd.to_datetime(df_irr['data_referencia'])
        df_irr['mes_ano_label'] = df_irr['data'].dt.strftime('%m/%Y')
        df_irr['obra_nome'] = df_irr['obra_id'].map(obras_map).fillna("Desconhecida")
        
        if 'semana_ref' not in df_irr.columns:
            df_irr['semana_ref'] = df_irr['data'].apply(lambda d: f"Semana {d.isocalendar()[1]}")

        # Se for visao global (Todas as Obras), agrupa para nao duplicar linhas no grafico de tendencia
        if obra_id is None:
            # Agrupamento diario para tendencia
            df_irr_agg = df_irr.groupby(['data', 'mes_ano_label', 'semana_ref']).agg({
                'restricoes_totais': 'sum',
                'restricoes_removidas': 'sum'
            }).reset_index()
            df_irr_agg['irr_percentual'] = (df_irr_agg['restricoes_removidas'] / df_irr_agg['restricoes_totais'] * 100).fillna(0)
            df_irr_agg['obra_nome'] = 'Geral'
            # Mantem o df detalhado para o grafico de barras (por obra) se necessario, ou usa o agg
            # Para simplificar a visao global, usaremos o agg como base principal, mas o df_irr original tem o detalhe por obra
    
    # 3. PROBLEMAS
    resp_prob = apply_query("pcp_historico_problemas", "data_referencia")
    df_prob = pd.DataFrame(resp_prob.data) if resp_prob.data else pd.DataFrame()

    return df_ind, df_irr, df_prob

def card_metrica(label, value, suffix="", color="#1E1E1E"):
    st.markdown(f"""
    <div style="background-color: {color}; padding: 15px; border-radius: 8px; border: 1px solid #333; text-align: center; height: 100%; min-height: 110px; display: flex; flex-direction: column; justify-content: center;">
        <div style="font-size: 0.75rem; color: #aaa; text-transform: uppercase; margin-bottom: 5px; font-weight: 600;">{label}</div>
        <div style="font-size: 1.6rem; font-weight: 800; color: white;">{value}<span style="font-size: 0.9rem; color: #E37026; margin-left: 2px;">{suffix}</span></div>
    </div>
    """, unsafe_allow_html=True)

def app(obra_id_param):
    st.markdown("### Dashboard de Planejamento")
    
    supabase = database.get_db_client()
    user = st.session_state.get('user', {})
    is_admin = user.get('role') == 'admin'

    lavie_orange = '#E37026'
    
    # --- SELECAO DE OBRA ---
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

    # --- FILTROS DE DATA ---
    c_filtros = st.container()
    col_f1, col_f2 = c_filtros.columns([3, 1])
    
    with col_f1:
        d_end = datetime.now()
        d_start = d_end - timedelta(days=120) # 4 meses padrao
        dates = st.date_input("Periodo de Analise", [d_start, d_end])
        s_date, e_date = (dates[0], dates[1]) if len(dates) == 2 else (d_start, d_end)
            
    with col_f2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Atualizar", use_container_width=True):
            st.rerun()

    df_ind, df_irr, df_prob = load_data(supabase, obra_id, s_date.strftime('%Y-%m-%d'), e_date.strftime('%Y-%m-%d'))

    st.markdown("---")

    # --- KPI CARDS (LINHA SUPERIOR) ---
    k1, k2, k3, k4, k5 = st.columns(5)
    
    avg_ppc = df_ind['ppc'].mean() if not df_ind.empty else 0
    avg_pap = df_ind['pap'].mean() if not df_ind.empty else 0
    
    # Calculos IRR
    if not df_irr.empty:
        tot_estoque = df_irr['restricoes_totais'].sum()
        tot_removidas = df_irr['restricoes_removidas'].sum()
        # Media do IRR percentual (semana a semana)
        avg_irr = df_irr['irr_percentual'].mean() if 'irr_percentual' in df_irr.columns else 0
    else:
        tot_estoque = 0
        tot_removidas = 0
        avg_irr = 0
        
    # Maior Ofensor
    maior_ofensor = "-"
    if not df_prob.empty:
        col_prob = 'problema_descricao' if 'problema_descricao' in df_prob.columns else 'problema'
        if col_prob in df_prob.columns:
            top = df_prob.groupby(col_prob)['quantidade'].sum().sort_values(ascending=False).head(1)
            if not top.empty:
                maior_ofensor = f"{top.index[0]} ({top.values[0]})"
                if len(maior_ofensor) > 25: maior_ofensor = top.index[0][:22] + "..."

    with k1: card_metrica("PPC Medio", f"{avg_ppc:.0f}", "%")
    with k2: card_metrica("PAP Medio", f"{avg_pap:.0f}", "%")
    with k3: card_metrica("IRR Medio", f"{avg_irr:.0f}", "%")
    with k4: card_metrica("Restricoes Resolvidas", f"{tot_removidas}")
    with k5: card_metrica("Principal Ofensor", "", f"{maior_ofensor}")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- ABAS ---
    t1, t2, t3 = st.tabs(["Producao (PPC/PAP)", "Restricoes (IRR)", "Problemas"])

    # ========================== ABA PRODUCAO ==========================
    with t1:
        if not df_ind.empty:
            # 1. Grafico de Tendencia Mensal (Macro)
            st.markdown("##### Evolucao Mensal (Tendencia)")
            
            # Agrupa por mes para a linha de tendencia
            df_ind_m = df_ind.groupby('mes_ano_label')[['ppc', 'pap']].mean().reset_index()
            # Ordenacao cronologica
            df_order = df_ind[['mes_ano_label', 'data']].sort_values('data').drop_duplicates('mes_ano_label')
            df_ind_m = df_ind_m.merge(df_order[['mes_ano_label']], on='mes_ano_label')
            
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=df_ind_m['mes_ano_label'], y=df_ind_m['ppc'],
                mode='lines+markers+text', name='PPC Mensal',
                text=df_ind_m['ppc'].apply(lambda x: f"{x:.0f}%"), textposition='top center',
                line=dict(color=lavie_orange, width=3)
            ))
            fig_trend.add_trace(go.Scatter(
                x=df_ind_m['mes_ano_label'], y=df_ind_m['pap'],
                mode='lines+markers', name='PAP Mensal',
                line=dict(color='#888', width=3, dash='dot')
            ))
            fig_trend.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color="white", xaxis_title="Mes", yaxis_title="Media %",
                margin=dict(t=20, b=20), height=300,
                legend=dict(orientation="h", y=1.1)
            )
            # Cliponaxis False para nao cortar labels
            fig_trend.update_traces(cliponaxis=False)
            st.plotly_chart(fig_trend, use_container_width=True)
            
            st.markdown("---")
            
            # 2. Detalhamento Semanal com Filtro de Mes
            st.markdown("##### Detalhamento Semanal")
            
            meses_disp = df_ind['mes_ano_label'].unique().tolist()
            # Ordena meses
            meses_sorted = sorted(meses_disp, key=lambda x: datetime.strptime(x, "%m/%Y"))
            
            c_sel, _ = st.columns([1, 3])
            mes_sel = c_sel.selectbox("Selecione o Mes:", meses_sorted, index=len(meses_sorted)-1, key="sel_mes_prod")
            
            df_mes = df_ind[df_ind['mes_ano_label'] == mes_sel].copy()
            # Ordena por semana_ref
            df_mes = df_mes.sort_values('semana_ref')
            
            col_ppc, col_pap = st.columns(2)
            
            # Funcao para gerar grafico de barra padrao
            def plot_bar_week(df, y_col, title, color_seq):
                fig = px.bar(
                    df, x="semana_ref", y=y_col, 
                    color="obra_nome", barmode="group",
                    text_auto='.0f', color_discrete_sequence=color_seq
                )
                # Aumenta range Y para caber o label (max value * 1.15)
                max_val = df[y_col].max() if not df.empty else 100
                fig.update_layout(
                    title=title,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color="white", xaxis_title="", yaxis_title="%",
                    yaxis_range=[0, max_val * 1.2],
                    legend=dict(orientation="h", y=-0.15),
                    margin=dict(t=40, b=20), height=380,
                    uniformtext_minsize=8, uniformtext_mode='hide'
                )
                fig.update_traces(textposition='outside', cliponaxis=False)
                return fig

            with col_ppc:
                # Cores Lavie para Obras (Laranja, Cinza Escuro, Cinza Claro...)
                paleta_obras = [lavie_orange, '#444444', '#777777', '#AAAAAA']
                st.plotly_chart(plot_bar_week(df_mes, "ppc", "PPC Semanal", paleta_obras), use_container_width=True)
                
            with col_pap:
                st.plotly_chart(plot_bar_week(df_mes, "pap", "PAP Semanal", paleta_obras), use_container_width=True)

        else:
            st.info("Sem dados de producao para o periodo.")

    # ========================== ABA RESTRICOES ==========================
    with t2:
        if not df_irr.empty:
            # 1. Grafico de Tendencia Mensal (Macro) - Linha IRR
            st.markdown("##### Evolucao Mensal (Tendencia)")
            
            # Se for Geral, precisa recalcular media ponderada por mes
            if obra_id is None:
                df_irr_m = df_irr.groupby('mes_ano_label').agg({
                    'restricoes_totais': 'sum', 'restricoes_removidas': 'sum', 'data': 'min'
                }).reset_index()
                df_irr_m['irr_percentual'] = (df_irr_m['restricoes_removidas'] / df_irr_m['restricoes_totais'] * 100).fillna(0)
            else:
                df_irr_m = df_irr.groupby('mes_ano_label')[['irr_percentual', 'data']].mean().reset_index()

            df_irr_m = df_irr_m.sort_values('data')
            
            fig_irr_trend = go.Figure()
            fig_irr_trend.add_trace(go.Scatter(
                x=df_irr_m['mes_ano_label'], y=df_irr_m['irr_percentual'],
                mode='lines+markers+text', name='IRR %',
                text=df_irr_m['irr_percentual'].apply(lambda x: f"{x:.0f}%"), textposition='top center',
                line=dict(color=lavie_orange, width=3)
            ))
            fig_irr_trend.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color="white", xaxis_title="Mes", yaxis_title="IRR %",
                margin=dict(t=20, b=20), height=300
            )
            fig_irr_trend.update_traces(cliponaxis=False)
            st.plotly_chart(fig_irr_trend, use_container_width=True)
            
            st.markdown("---")
            
            # 2. Detalhamento Semanal (Estoque vs Removidas) - COM FILTRO DE MES
            st.markdown("##### Detalhamento Semanal")
            
            meses_disp_irr = df_irr['mes_ano_label'].unique().tolist()
            meses_sorted_irr = sorted(meses_disp_irr, key=lambda x: datetime.strptime(x, "%m/%Y"))
            
            c_sel_irr, _ = st.columns([1, 3])
            mes_sel_irr = c_sel_irr.selectbox("Selecione o Mes:", meses_sorted_irr, index=len(meses_sorted_irr)-1, key="sel_mes_irr")
            
            df_irr_sem = df_irr[df_irr['mes_ano_label'] == mes_sel_irr].copy()
            df_irr_sem = df_irr_sem.sort_values('semana_ref')
            
            # Se for visao Geral, agrupa as obras por semana para mostrar o total da semana
            if obra_id is None:
                df_irr_sem = df_irr_sem.groupby('semana_ref').agg({
                    'restricoes_totais': 'sum',
                    'restricoes_removidas': 'sum'
                }).reset_index()

            fig_bar_irr = go.Figure()
            
            # Barras Lado a Lado
            fig_bar_irr.add_trace(go.Bar(
                x=df_irr_sem['semana_ref'], y=df_irr_sem['restricoes_totais'],
                name='Estoque Total', marker_color='#333333',
                text=df_irr_sem['restricoes_totais'], textposition='outside'
            ))
            fig_bar_irr.add_trace(go.Bar(
                x=df_irr_sem['semana_ref'], y=df_irr_sem['restricoes_removidas'],
                name='Removidas', marker_color=lavie_orange,
                text=df_irr_sem['restricoes_removidas'], textposition='outside'
            ))
            
            max_y = max(df_irr_sem['restricoes_totais'].max(), df_irr_sem['restricoes_removidas'].max())
            
            fig_bar_irr.update_layout(
                title=f"Fluxo de Restricoes - {mes_sel_irr}",
                barmode='group',
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color="white", xaxis_title="", yaxis_title="Qtd",
                yaxis_range=[0, max_y * 1.2],
                legend=dict(orientation="h", y=-0.15),
                margin=dict(t=40, b=20), height=400
            )
            fig_bar_irr.update_traces(cliponaxis=False)
            st.plotly_chart(fig_bar_irr, use_container_width=True)

        else:
            st.info("Sem dados historicos de restricoes.")

    # ========================== ABA PROBLEMAS ==========================
    with t3:
        if not df_prob.empty:
            col_prob = 'problema_descricao' if 'problema_descricao' in df_prob.columns else 'problema'
            
            if col_prob in df_prob.columns:
                # Agrupamento Total
                df_group = df_prob.groupby(col_prob)['quantidade'].sum().reset_index()
                df_group = df_group.sort_values('quantidade', ascending=True) # Ascendente para barra horizontal ficar certa
                
                c_p1, c_p2 = st.columns([2, 1])
                
                with c_p1:
                    st.markdown("##### Causas (Barras)")
                    fig_bar_p = px.bar(
                        df_group, x='quantidade', y=col_prob, orientation='h',
                        text_auto=True, color_discrete_sequence=[lavie_orange]
                    )
                    # Ajuste do eixo X para dar espaco ao label
                    max_x = df_group['quantidade'].max()
                    fig_bar_p.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        font_color="white", xaxis_title="Qtd", yaxis_title="",
                        xaxis_range=[0, max_x * 1.15],
                        height=500, margin=dict(l=0)
                    )
                    fig_bar_p.update_traces(textposition='outside', cliponaxis=False)
                    st.plotly_chart(fig_bar_p, use_container_width=True)
                    
                with c_p2:
                    st.markdown("##### Distribuicao (Rosca)")
                    fig_pie = px.pie(
                        df_group, values='quantidade', names=col_prob, hole=0.5,
                        color_discrete_sequence=px.colors.sequential.Oranges_r
                    )
                    fig_pie.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        font_color="white", showlegend=False,
                        height=400, margin=dict(t=0, b=0, l=0, r=0)
                    )
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.error("Erro na coluna de dados.")
        else:
            st.info("Nenhum problema registrado.")
