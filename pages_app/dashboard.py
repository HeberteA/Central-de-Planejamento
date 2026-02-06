import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from modules import database
from modules import ui

LAVIE_PALETTE = [
    "#E37026", 
    "#CA6422",
    "#B1581E",
    "#984B19",
    "#803F15",
    "#673311",
    "#4E260D",
    "#351A09"
]

BG_COLOR = 'rgba(0,0,0,0)'
TEXT_COLOR = 'white'

def load_data(supabase, obra_id, start_date, end_date):
    obras_map = {}
    try:
        resp_obras = supabase.table("pcp_obras").select("id, nome").execute()
        if resp_obras.data:
            obras_map = {o['id']: o['nome'] for o in resp_obras.data}
    except Exception as e:
        print(f"Erro obras: {e}")

    def apply_query(table, date_col):
        try:
            q = supabase.table(table).select("*")
            if obra_id: q = q.eq("obra_id", obra_id)
            if date_col:
                q = q.gte(date_col, start_date).lte(date_col, end_date)
                q = q.order(date_col)
            return q.execute()
        except: return None

    resp_ind = apply_query("pcp_historico_indicadores", "data_referencia")
    df_ind = pd.DataFrame(resp_ind.data) if resp_ind and resp_ind.data else pd.DataFrame()
    if not df_ind.empty:
        df_ind['obra_nome'] = df_ind['obra_id'].map(obras_map).fillna("Desconhecida")
        df_ind['data_ref'] = pd.to_datetime(df_ind['data_referencia'])
        df_ind['sort_date'] = df_ind['data_ref']
        df_ind['mes_ano_label'] = df_ind['data_ref'].dt.strftime('%m/%Y')
        if 'semana_ref' not in df_ind.columns:
            df_ind['semana_ref'] = df_ind['data_ref'].apply(lambda d: f"Semana {d.isocalendar()[1]}")

        if 'tipo_indicador' in df_ind.columns:
            df_pivot = df_ind.pivot_table(
                index=['data_ref', 'sort_date', 'mes_ano_label', 'semana_ref', 'obra_nome', 'obra_id'], 
                columns='tipo_indicador', values='valor_percentual', aggfunc='mean'
            ).reset_index()
            df_pivot.columns = [str(c).lower() for c in df_pivot.columns]
            if 'ppc' not in df_pivot.columns: df_pivot['ppc'] = 0
            if 'pap' not in df_pivot.columns: df_pivot['pap'] = 0
            df_ind = df_pivot
            df_ind.rename(columns={'data_ref': 'data'}, inplace=True)
        else:
            df_ind['data'] = df_ind['data_ref']
    else:
        df_ind = pd.DataFrame(columns=['data', 'ppc', 'pap', 'obra_nome', 'semana_ref', 'mes_ano_label', 'sort_date'])

    resp_irr = apply_query("pcp_historico_irr", "data_referencia")
    df_irr = pd.DataFrame(resp_irr.data) if resp_irr and resp_irr.data else pd.DataFrame()
    if not df_irr.empty:
        df_irr['data'] = pd.to_datetime(df_irr['data_referencia'])
        df_irr['sort_date'] = df_irr['data']
        df_irr['mes_ano_label'] = df_irr['data'].dt.strftime('%m/%Y')
        df_irr['obra_nome'] = df_irr['obra_id'].map(obras_map).fillna("Desconhecida")
        if 'semana_ref' not in df_irr.columns:
            df_irr['semana_ref'] = df_irr['data'].apply(lambda d: f"Semana {d.isocalendar()[1]}")
        if 'irr_percentual' not in df_irr.columns: df_irr['irr_percentual'] = 0

    resp_prob = apply_query("pcp_historico_problemas", "data_referencia")
    df_prob = pd.DataFrame(resp_prob.data) if resp_prob and resp_prob.data else pd.DataFrame()
    if not df_prob.empty:
        df_prob['data'] = pd.to_datetime(df_prob['data_referencia'])
        df_prob['obra_nome'] = df_prob['obra_id'].map(obras_map).fillna("Desconhecida")

    return df_ind, df_irr, df_prob

def card_kpi(label, value, suffix="", border_color="#E37026"):
    st.markdown(f"""
    <div style="
        background: linear-gradient(145deg, #1e1e1e, #252525);
        padding: 15px; 
        border-radius: 10px; 
        border: 1px solid #333; 
        border-bottom: 4px solid {border_color};
        text-align: center; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        height: 100%;
        min-height: 110px;
        display: flex; flex-direction: column; justify-content: center;
    ">
        <div style="font-size: 0.75rem; color: #aaa; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;">{label}</div>
        <div style="font-size: 1.6rem; font-weight: 700; color: white;">
            {value}<span style="font-size: 0.9rem; color: {border_color}; margin-left: 2px;">{suffix}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def plot_bar_week_grouped(df, x_col, y_col, color_col, title, color_seq, y_title="%"):
    fig = px.bar(
        df, x=x_col, y=y_col, 
        color=color_col, barmode="group",
        text_auto='.0f', color_discrete_sequence=color_seq
    )
    max_val = df[y_col].max() if not df.empty else 100
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#CCC")),
        paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR,
        font_color=TEXT_COLOR, xaxis_title="", yaxis_title=y_title,
        yaxis_range=[0, max_val * 1.2],
        legend=dict(orientation="h", y=-0.2),
        margin=dict(t=40, b=20), height=350,
        hovermode="x unified"
    )
    fig.update_traces(textposition='outside', cliponaxis=False)
    return fig

def app(obra_id_param):
    st.markdown("### Dashboard de Planejamento")
    
    supabase = database.get_db_client()
    user = st.session_state.get('user', {})
    is_admin = user.get('role') == 'admin'

    obra_id = obra_id_param
    
    if is_admin:
        c_filter, c_date = st.columns([1, 1])
        with c_filter:
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
                    
                    selected_nome = st.selectbox("Obra:", list(opcoes.keys()), index=idx_selecionado)
                    obra_id = opcoes[selected_nome]
            except: pass
    else:
        c_date = st.container()

    d_end = datetime.now()
    d_start = d_end - timedelta(days=180)
    with c_date:
        dates = st.date_input("Periodo:", [d_start, d_end])
        s_date, e_date = (dates[0], dates[1]) if len(dates) == 2 else (d_start, d_end)
            
    df_ind, df_irr, df_prob = load_data(supabase, obra_id, s_date.strftime('%Y-%m-%d'), e_date.strftime('%Y-%m-%d'))

    st.markdown("---")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    
    avg_ppc = df_ind['ppc'].mean() if not df_ind.empty else 0
    avg_pap = df_ind['pap'].mean() if not df_ind.empty else 0
    
    tot_restricoes = 0
    tot_removidas = 0
    saldo_aberto = 0
    
    if not df_irr.empty:
        df_latest = df_irr.drop_duplicates(['obra_id', 'semana_ref', 'mes_ano_label'])
        tot_restricoes = df_latest['restricoes_totais'].sum()
        tot_removidas = df_latest['restricoes_removidas'].sum()
        saldo_aberto = tot_restricoes - tot_removidas
        if saldo_aberto < 0: saldo_aberto = 0
    
    maior_ofensor = "-"
    count_ofensor = 0
    if not df_prob.empty:
        col_prob = 'problema_descricao' if 'problema_descricao' in df_prob.columns else 'problema'
        if col_prob in df_prob.columns:
            top = df_prob.groupby(col_prob)['quantidade'].sum().sort_values(ascending=False).head(1)
            if not top.empty:
                count_ofensor = top.values[0]
                maior_ofensor = top.index[0]
                if len(maior_ofensor) > 12: maior_ofensor = maior_ofensor[:10] + "..."

    with k1: card_kpi("PPC Medio", f"{avg_ppc:.0f}", "%", "#3B82F6")
    with k2: card_kpi("PAP Medio", f"{avg_pap:.0f}", "%", "#10B981")
    with k3: card_kpi("Restricoes Totais", f"{tot_restricoes}", "", "#EF4444")
    with k4: card_kpi("Total Removidas", f"{tot_removidas}", "", "#10B981")
    with k5: card_kpi("Saldo Restricoes", f"{saldo_aberto}", "", "#E37026")
    with k6: card_kpi("Maior Ofensor", f"{count_ofensor}", f"\n{maior_ofensor}", "#E37026")

    st.markdown("<br>", unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["Producao (PPC/PAP)", "Restricoes (Quantitativo)", "Problemas"])

    with t1:
        st.markdown("##### Tendencia Mensal")
        if not df_ind.empty:
            df_ind_m = df_ind.groupby('mes_ano_label').agg({'ppc': 'mean', 'pap': 'mean', 'sort_date': 'min'}).reset_index().sort_values('sort_date')
            
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=df_ind_m['mes_ano_label'], y=df_ind_m['ppc'],
                mode='lines+markers+text', name='PPC Mensal',
                text=df_ind_m['ppc'].apply(lambda x: f"{x:.0f}%"), textposition='top center',
                line=dict(color=LAVIE_PALETTE[0], width=3)
            ))
            fig_trend.add_trace(go.Scatter(
                x=df_ind_m['mes_ano_label'], y=df_ind_m['pap'],
                mode='lines+markers', name='PAP Mensal',
                line=dict(color='#A0A0A0', width=3, dash='dot')
            ))
            fig_trend.update_layout(
                paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                yaxis_title="Media %", margin=dict(t=20, b=20), height=300,
                legend=dict(orientation="h", y=1.1), hovermode="x unified"
            )
            st.plotly_chart(fig_trend, use_container_width=True)
            
            st.markdown("---")
            st.markdown("##### Detalhamento Semanal")
            
            meses_unicos = df_ind[['mes_ano_label', 'sort_date']].drop_duplicates().sort_values('sort_date')
            lista_meses = meses_unicos['mes_ano_label'].unique().tolist()
            
            c_sel, _ = st.columns([1, 3])
            if lista_meses:
                mes_sel = c_sel.selectbox("Mes:", lista_meses, index=len(lista_meses)-1, key="sel_mes_prod")
                df_mes = df_ind[df_ind['mes_ano_label'] == mes_sel].copy()
                try:
                    df_mes['sem_num'] = df_mes['semana_ref'].str.extract(r'(\d+)').astype(float)
                    df_mes = df_mes.sort_values(['obra_nome', 'sem_num'])
                except:
                    df_mes = df_mes.sort_values('semana_ref')
                
                col_ppc, col_pap = st.columns(2)
                with col_ppc:
                    st.plotly_chart(plot_bar_week_grouped(df_mes, "semana_ref", "ppc", "obra_nome", "PPC Semanal", LAVIE_PALETTE), use_container_width=True)
                with col_pap:
                    st.plotly_chart(plot_bar_week_grouped(df_mes, "semana_ref", "pap", "obra_nome", "PAP Semanal", LAVIE_PALETTE), use_container_width=True)
            
            st.markdown("---")
            st.markdown("##### Analise Comparativa")
            g_new1, g_new2 = st.columns(2)
            
            with g_new1:
                st.markdown("**Mapa de Calor: Desempenho por Obra**")
                df_heat = df_ind.groupby(['obra_nome', 'mes_ano_label'])['ppc'].mean().reset_index()
                fig_heat = px.density_heatmap(
                    df_heat, x="mes_ano_label", y="obra_nome", z="ppc", 
                    text_auto='.0f', color_continuous_scale=LAVIE_PALETTE
                )
                fig_heat.update_layout(paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR, height=350)
                st.plotly_chart(fig_heat, use_container_width=True)
                
            with g_new2:
                st.markdown("**Ranking de Obras (PPC Medio)**")
                df_rank = df_ind.groupby('obra_nome')['ppc'].mean().reset_index().sort_values('ppc', ascending=True)
                fig_rank = px.bar(
                    df_rank, x='ppc', y='obra_nome', orientation='h', text_auto='.1f',
                    color='ppc', color_continuous_scale=[LAVIE_PALETTE[-1], LAVIE_PALETTE[0]]
                )
                fig_rank.update_layout(
                    paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                    height=350, xaxis_title="PPC Medio", yaxis_title=""
                )
                st.plotly_chart(fig_rank, use_container_width=True)
        else:
            st.info("Sem dados de producao.")

    with t2:
        if not df_irr.empty:
            st.markdown("##### Evolucao Mensal (Restricoes vs Removidas)")
            
            df_irr_m = df_irr.groupby('mes_ano_label').agg({'restricoes_totais': 'max', 'restricoes_removidas': 'sum', 'sort_date': 'min'}).reset_index().sort_values('sort_date')
            
            fig_trend_irr = go.Figure()
            fig_trend_irr.add_trace(go.Scatter(
                x=df_irr_m['mes_ano_label'], y=df_irr_m['restricoes_totais'],
                mode='lines+markers+text', name='Restricoes Totais',
                text=df_irr_m['restricoes_totais'], textposition='top center',
                line=dict(color='#777', width=3)
            ))
            fig_trend_irr.add_trace(go.Scatter(
                x=df_irr_m['mes_ano_label'], y=df_irr_m['restricoes_removidas'],
                mode='lines+markers+text', name='Removidas',
                text=df_irr_m['restricoes_removidas'], textposition='bottom center',
                line=dict(color=LAVIE_PALETTE[0], width=3)
            ))
            fig_trend_irr.update_layout(
                paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                xaxis_title="", yaxis_title="Qtd", margin=dict(t=20, b=20), height=320,
                legend=dict(orientation="h", y=1.1), hovermode="x unified"
            )
            st.plotly_chart(fig_trend_irr, use_container_width=True)
            
            st.markdown("---")
            st.markdown("##### Detalhamento Semanal")
            
            meses_irr = df_irr[['mes_ano_label', 'sort_date']].drop_duplicates().sort_values('sort_date')
            lista_meses_irr = meses_irr['mes_ano_label'].unique().tolist()
            
            c_sel_i, _ = st.columns([1, 3])
            if lista_meses_irr:
                mes_sel_irr = c_sel_i.selectbox("Mes:", lista_meses_irr, index=len(lista_meses_irr)-1, key="sel_mes_irr")
                df_irr_sem = df_irr[df_irr['mes_ano_label'] == mes_sel_irr].copy()
                try:
                    df_irr_sem['sem_num'] = df_irr_sem['semana_ref'].str.extract(r'(\d+)').astype(float)
                    df_irr_sem = df_irr_sem.sort_values('sem_num')
                except:
                    df_irr_sem = df_irr_sem.sort_values('semana_ref')
                
                col_rest, col_rem = st.columns(2)
                with col_rest:
                    st.plotly_chart(plot_bar_week_grouped(df_irr_sem, "semana_ref", "restricoes_totais", "obra_nome", "Restricoes Totais", LAVIE_PALETTE, "Qtd"), use_container_width=True)
                with col_rem:
                    st.plotly_chart(plot_bar_week_grouped(df_irr_sem, "semana_ref", "restricoes_removidas", "obra_nome", "Removidas", LAVIE_PALETTE, "Qtd"), use_container_width=True)

            st.markdown("---")
            st.markdown("##### Analise de Eficiencia")
            
            e1, e2 = st.columns(2)
            with e1:
                st.markdown("**Resolutividade por Obra**")
                df_eff = df_irr.groupby('obra_nome').agg({'restricoes_totais': 'max', 'restricoes_removidas': 'sum'}).reset_index()
                df_eff['eficiencia'] = (df_eff['restricoes_removidas'] / df_eff['restricoes_totais'] * 100).fillna(0)
                
                fig_scat = px.scatter(
                    df_eff, x='restricoes_totais', y='restricoes_removidas', 
                    size='restricoes_totais', color='obra_nome',
                    hover_name='obra_nome', text='eficiencia',
                    color_discrete_sequence=LAVIE_PALETTE
                )
                fig_scat.update_traces(texttemplate='%{text:.0f}%', textposition='top center')
                fig_scat.update_layout(
                    paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                    height=350, xaxis_title="Total Identificadas", yaxis_title="Total Removidas"
                )
                st.plotly_chart(fig_scat, use_container_width=True)
                
            with e2:
                st.markdown("**Evolucao de Saldo Acumulado**")
                df_acum = df_irr.groupby('sort_date').agg({'restricoes_totais': 'max', 'restricoes_removidas': 'sum'}).reset_index()
                df_acum['saldo'] = df_acum['restricoes_totais'] - df_acum['restricoes_removidas']
                df_acum['saldo'] = df_acum['saldo'].apply(lambda x: max(0, x))
                
                fig_area = px.area(df_acum, x='sort_date', y='saldo')
                fig_area.update_traces(line_color=LAVIE_PALETTE[0], fillcolor='rgba(227, 112, 38, 0.2)')
                fig_area.update_layout(
                    paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                    height=350, title="Backlog (Saldo)", xaxis_title="", yaxis_title="Saldo"
                )
                st.plotly_chart(fig_area, use_container_width=True)
        else:
            st.info("Sem dados historicos.")

    with t3:
        if not df_prob.empty:
            col_prob = 'problema_descricao' if 'problema_descricao' in df_prob.columns else 'problema'
            if col_prob in df_prob.columns:
                df_group = df_prob.groupby(col_prob)['quantidade'].sum().reset_index().sort_values('quantidade', ascending=True)
                
                c_p1, c_p2 = st.columns([2, 1])
                with c_p1:
                    st.markdown("##### Causas (Quantitativo)")
                    fig_bar_p = px.bar(
                        df_group, x='quantidade', y=col_prob, orientation='h',
                        text_auto=True, color_discrete_sequence=[LAVIE_PALETTE[0]]
                    )
                    max_x = df_group['quantidade'].max()
                    fig_bar_p.update_layout(
                        paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                        xaxis_title="Ocorrencias", yaxis_title="",
                        xaxis_range=[0, max_x * 1.2], height=500
                    )
                    fig_bar_p.update_traces(textposition='outside', cliponaxis=False)
                    st.plotly_chart(fig_bar_p, use_container_width=True)
                    
                with c_p2:
                    st.markdown("##### Distribuicao")
                    fig_pie = px.pie(
                        df_group, values='quantidade', names=col_prob, hole=0.5,
                        color_discrete_sequence=LAVIE_PALETTE
                    )
                    fig_pie.update_layout(
                        paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                        showlegend=False, height=400, margin=dict(t=0, b=0, l=0, r=0)
                    )
                    fig_pie.update_traces(textposition='inside', textinfo='value+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                st.markdown("---")
                st.markdown("##### Analise Detalhada")
                
                n_p1, n_p2 = st.columns(2)
                with n_p1:
                    st.markdown("**Top 5 Problemas no Tempo**")
                    top_5_probs = df_group.sort_values('quantidade', ascending=False).head(5)[col_prob].tolist()
                    df_time_prob = df_prob[df_prob[col_prob].isin(top_5_probs)].groupby(['data', col_prob])['quantidade'].sum().reset_index()
                    
                    fig_line_prob = px.line(df_time_prob, x='data', y='quantidade', color=col_prob, color_discrete_sequence=LAVIE_PALETTE)
                    fig_line_prob.update_layout(
                        paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                        height=350, showlegend=True, legend=dict(orientation="h", y=-0.2)
                    )
                    st.plotly_chart(fig_line_prob, use_container_width=True)
                    
                with n_p2:
                    st.markdown("**Mapa de Calor: Problema x Obra**")
                    df_heat_prob = df_prob.groupby(['obra_nome', col_prob])['quantidade'].sum().reset_index()
                    fig_heat_prob = px.density_heatmap(
                        df_heat_prob, x='obra_nome', y=col_prob, z='quantidade',
                        text_auto=True, color_continuous_scale=LAVIE_PALETTE
                    )
                    fig_heat_prob.update_layout(
                        paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR, height=350
                    )
                    st.plotly_chart(fig_heat_prob, use_container_width=True)

            else:
                st.error("Erro na coluna de dados.")
        else:
            st.info("Nenhum problema registrado.")
