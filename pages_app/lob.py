import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules import database
from modules import ui
import time

def safe_date(val):
    if val is None: return None
    try:
        return pd.to_datetime(val).to_pydatetime().replace(tzinfo=None)
    except: return None

def render_custom_lob(df):
    if df.empty:
        st.info("Sem dados para exibir.")
        return

    df['dt_ini'] = df['data_inicio'].apply(safe_date)
    df['dt_fim'] = df['data_fim'].apply(safe_date)
    df = df.dropna(subset=['dt_ini', 'dt_fim'])

    if df.empty:
        st.warning("Datas invalidas.")
        return

    min_date = df['dt_ini'].min() - timedelta(days=2)
    max_date = df['dt_fim'].max() + timedelta(days=5)
    total_days = (max_date - min_date).days
    if total_days < 1: total_days = 1

    pavimentos_ordem = df[['pavimento', 'ordem_pav']].drop_duplicates().sort_values('ordem_pav', ascending=False)
    
    colors = [
        "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", 
        "#EC4899", "#6366F1", "#14B8A6", "#F97316"
    ]
    atv_unique = df['atividade_nome'].unique()
    map_colors = {atv: colors[i % len(colors)] for i, atv in enumerate(atv_unique)}

    st.markdown("""
    <style>
        .gantt-scroll {
            overflow-x: auto;
            border: 1px solid #333;
            border-radius: 8px;
            background: #1e1e1e;
            margin-bottom: 20px;
        }
        
        .gantt-header {
            display: flex;
            height: 40px;
            background: #262626;
            border-bottom: 1px solid #444;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header-spacer {
            min-width: 180px;
            position: sticky;
            left: 0;
            background: #262626;
            z-index: 101;
            border-right: 1px solid #444;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: #aaa;
            font-size: 0.8rem;
        }
        .header-timeline {
            flex-grow: 1;
            position: relative;
            min-width: 800px;
        }
        .month-marker {
            position: absolute;
            top: 10px;
            font-size: 0.75rem;
            color: #888;
            border-left: 1px solid #444;
            padding-left: 5px;
            height: 30px;
        }

        .gantt-row {
            display: flex;
            border-bottom: 1px solid #2a2a2a;
            position: relative;
            background: #1a1a1a;
            transition: background 0.2s;
        }
        .gantt-row:hover { background: #222; }

        .row-label {
            min-width: 180px;
            max-width: 180px;
            position: sticky;
            left: 0;
            background: #1a1a1a;
            z-index: 50;
            border-right: 1px solid #333;
            padding: 10px;
            font-size: 0.85rem;
            color: #ddd;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            text-align: right;
            box-shadow: 2px 0 5px rgba(0,0,0,0.2);
        }

        .row-track {
            flex-grow: 1;
            position: relative;
            min-width: 800px;
        }

        .grid-guide {
            position: absolute;
            top: 0; bottom: 0;
            border-left: 1px dashed rgba(255,255,255,0.05);
            pointer-events: none;
        }

        .gantt-bar {
            position: absolute;
            height: 24px;
            border-radius: 4px;
            color: white;
            font-size: 0.7rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            padding: 0 8px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            cursor: pointer;
            border: 1px solid rgba(255,255,255,0.15);
            transition: transform 0.1s;
        }
        .gantt-bar:hover {
            z-index: 999;
            transform: scale(1.02);
            filter: brightness(1.1);
            box-shadow: 0 5px 15px rgba(0,0,0,0.5);
        }

        .today-line {
            position: absolute;
            top: 0; bottom: 0;
            width: 2px;
            background: #E37026;
            z-index: 40;
            pointer-events: none;
        }
    </style>
    """, unsafe_allow_html=True)

    html_out = '<div class="gantt-scroll">'
    
    html_out += '<div class="gantt-header">'
    html_out += '<div class="header-spacer">PAVIMENTO</div>'
    html_out += '<div class="header-timeline">'
    
    curr = min_date.replace(day=1)
    while curr <= max_date:
        offset = (curr - min_date).days
        left_pct = (offset / total_days) * 100
        if 0 <= left_pct <= 100:
            label = curr.strftime('%b/%y').upper()
            html_out += f'<div class="month-marker" style="left: {left_pct}%;">{label}</div>'
        
        if curr.month == 12: curr = curr.replace(year=curr.year+1, month=1)
        else: curr = curr.replace(month=curr.month+1)
        
    hoje = datetime.now()
    if min_date <= hoje <= max_date:
        hoje_pos = ((hoje - min_date).days / total_days) * 100
        html_out += f'<div class="today-line" style="left: {hoje_pos}%;"></div>'

    html_out += '</div></div>'

    for _, pav_row in pavimentos_ordem.iterrows():
        pav_nome = pav_row['pavimento']
        atvs = df[df['pavimento'] == pav_nome].sort_values('dt_ini')
        
        lanes = [] 
        
        bars_html = ""
        for _, row in atvs.iterrows():
            lane_idx = -1
            for i, end_date in enumerate(lanes):
                if row['dt_ini'] >= end_date:
                    lane_idx = i
                    lanes[i] = row['dt_fim']
                    break
            
            if lane_idx == -1:
                lanes.append(row['dt_fim'])
                lane_idx = len(lanes) - 1
            
            start_pct = ((row['dt_ini'] - min_date).days / total_days) * 100
            dur_days = (row['dt_fim'] - row['dt_ini']).days
            width_pct = (max(1, dur_days) / total_days) * 100
            
            top_px = 10 + (lane_idx * 30)
            color = map_colors.get(row['atividade_nome'], "#666")
            
            tooltip_txt = f"{row['atividade_nome']} &#10;Inicio: {row['dt_ini'].strftime('%d/%m')} &#10;Fim: {row['dt_fim'].strftime('%d/%m')}"
            
            bars_html += f'<div class="gantt-bar" title="{tooltip_txt}" style="left: {start_pct}%; width: {width_pct}%; top: {top_px}px; background-color: {color};">{row["atividade_nome"]}</div>'
        
        row_height = max(50, (len(lanes) * 30) + 20)
        
        html_out += f'<div class="gantt-row" style="height: {row_height}px;">'
        html_out += f'<div class="row-label">{pav_nome}</div>'
        html_out += '<div class="row-track">'
        
        curr_g = min_date.replace(day=1)
        while curr_g <= max_date:
            offset = (curr_g - min_date).days
            left_pct = (offset / total_days) * 100
            if 0 <= left_pct <= 100:
                html_out += f'<div class="grid-guide" style="left: {left_pct}%;"></div>'
            if curr_g.month == 12: curr_g = curr_g.replace(year=curr_g.year+1, month=1)
            else: curr_g = curr_g.replace(month=curr_g.month+1)
            
        html_out += bars_html
        html_out += '</div></div>'

    html_out += '</div>'
    st.markdown(html_out, unsafe_allow_html=True)
    
    st.markdown("**Legenda de Atividades:**")
    cols = st.columns(6)
    for i, (atv, clr) in enumerate(map_colors.items()):
        with cols[i % 6]:
            st.markdown(f"<div style='display:flex;align-items:center;gap:5px'><div style='width:12px;height:12px;background:{clr};border-radius:2px'></div><span>{atv}</span></div>", unsafe_allow_html=True)

def render_management_tab(supabase, obra_id):
    st.markdown("""
    <style>
        .manage-card {
            background-color: #262626;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            position: relative;
            border-left: 5px solid #E37026;
            transition: all 0.3s;
        }
        .manage-card:hover {
            border-color: #555;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .mc-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }
        .mc-title { font-size: 1rem; font-weight: bold; color: white; margin: 0; }
        .mc-sub { font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }
        .mc-id { font-size: 0.7rem; color: #555; font-family: monospace; }
        div[data-testid="stDateInput"] label { font-size: 0.75rem; color: #888; }
        div[data-testid="stDateInput"] { margin-bottom: 0px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("##### Filtros de Busca")
    c1, c2 = st.columns(2)
    
    locais_disponiveis = []
    atividades_disponiveis = []
    try:
        r_loc = supabase.table("pcp_locais").select("nome").eq("obra_id", obra_id).order("ordem").execute()
        locais_disponiveis = [l['nome'] for l in r_loc.data]
        
        r_atv = supabase.table("pcp_lob_atividades").select("atividade_nome").eq("obra_id", obra_id).execute()
        atividades_disponiveis = sorted(list(set([a['atividade_nome'] for a in r_atv.data])))
    except: pass

    filtro_pav = c1.multiselect("Filtrar por Pavimento", locais_disponiveis)
    filtro_atv = c2.multiselect("Filtrar por Atividade", atividades_disponiveis)
    
    st.markdown("---")

    query = supabase.table("pcp_lob_atividades").select("*, pcp_locais(nome, ordem)").eq("obra_id", obra_id)
    
    response = query.execute()
    if not response.data:
        st.info("Nenhuma atividade encontrada.")
        return

    df = pd.DataFrame(response.data)
    df['pavimento'] = df['pcp_locais'].apply(lambda x: x['nome'] if x else "N/A")
    df['ordem_pav'] = df['pcp_locais'].apply(lambda x: x['ordem'] if x else 0)
    df['atividade_nome'] = df['atividade_nome'].fillna("Sem Nome")
    df['dt_ini'] = df['data_inicio'].apply(safe_date)
    df['dt_fim'] = df['data_fim'].apply(safe_date)
    
    if filtro_pav:
        df = df[df['pavimento'].isin(filtro_pav)]
    if filtro_atv:
        df = df[df['atividade_nome'].isin(filtro_atv)]
    
    df = df.sort_values(by=['ordem_pav', 'dt_ini'], ascending=[True, True])

    if df.empty:
        st.warning("Nenhum resultado para os filtros selecionados.")
        return

    st.markdown(f"**Encontrados: {len(df)} atividades**")

    items_per_page = 20
    if 'manage_page' not in st.session_state: st.session_state.manage_page = 0
    
    total_pages = max(1, len(df) // items_per_page + 1)
    
    start_idx = st.session_state.manage_page * items_per_page
    end_idx = start_idx + items_per_page
    df_page = df.iloc[start_idx:end_idx]

    for i, row in df_page.iterrows():
        st.markdown(f"""
        <div class="manage-card">
            <div class="mc-header">
                <div>
                    <div class="mc-title">{row['atividade_nome']}</div>
                    <div class="mc-sub">{row['pavimento']}</div>
                </div>
                <div class="mc-id">ID: {row['id']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        c_in1, c_in2, c_btn1, c_btn2 = st.columns([1.5, 1.5, 0.8, 0.8])
        
        with c_in1:
            new_ini = st.date_input("Inicio", value=row['dt_ini'], key=f"ini_{row['id']}", label_visibility="collapsed")
        with c_in2:
            new_fim = st.date_input("Fim", value=row['dt_fim'], key=f"fim_{row['id']}", label_visibility="collapsed")
            
        with c_btn1:
            if st.button("Salvar", key=f"save_{row['id']}", use_container_width=True):
                if new_fim < new_ini:
                    st.error("Data final menor que inicial!")
                else:
                    supabase.table("pcp_lob_atividades").update({
                        "data_inicio": new_ini.strftime("%Y-%m-%d"),
                        "data_fim": new_fim.strftime("%Y-%m-%d")
                    }).eq("id", row['id']).execute()
                    st.toast("Salvo com sucesso!")
                    time.sleep(0.5)
                    st.rerun()
                    
        with c_btn2:
            if st.button("Excluir", key=f"del_{row['id']}", type="primary", use_container_width=True):
                supabase.table("pcp_lob_atividades").delete().eq("id", row['id']).execute()
                st.toast("Atividade excluida!")
                time.sleep(0.5)
                st.rerun()
                
        st.markdown("<div style='margin-bottom:15px'></div>", unsafe_allow_html=True)

    c_p1, c_p2, c_p3 = st.columns([1, 5, 1])
    if c_p1.button("Anterior", disabled=(st.session_state.manage_page == 0), use_container_width=True):
        st.session_state.manage_page -= 1
        st.rerun()
    
    c_p2.markdown(f"<div style='text-align:center; padding-top:10px'>Pagina {st.session_state.manage_page + 1} de {total_pages}</div>", unsafe_allow_html=True)
    
    if c_p3.button("Proxima", disabled=(end_idx >= len(df)), use_container_width=True):
        st.session_state.manage_page += 1
        st.rerun()

def app(obra_id):
    supabase = database.get_db_client()
    user = st.session_state.get('user', {})
    is_admin = user.get('role') == 'admin'
    
    st.header("# Longo Prazo(LOB)", divider="orange")
    
    tabs_list = ["Visualização LOB"]
    if is_admin:
        tabs_list.extend(["Gerenciar Atividades", "Config. Pavimentos"])
        
    tabs = st.tabs(tabs_list)
    
    with tabs[0]:
        if is_admin:
            with st.expander("Nova Atividade", expanded=False):
                locais = []
                try:
                    r_loc = supabase.table("pcp_locais").select("id, nome").eq("obra_id", obra_id).order("ordem").execute()
                    locais = r_loc.data
                except: pass
                
                atividades_padrao = []
                try:
                    r_atv = supabase.table("pcp_atividades_padrao").select("atividade").execute()
                    atividades_padrao = [a['atividade'] for a in r_atv.data]
                except: pass

                with st.form("form_lob_quick"):
                    c_form = st.container()
                    usar_texto = c_form.toggle("Digitar nova atividade?", key="new_pp_tgg")

                    atividades_padrao = []
                    try:
                        r = supabase.table("pcp_atividades_padrao").select("atividade").execute()
                        atividades_padrao = [a['atividade'] for a in r.data]
                    except: pass

                    if usar_texto:
                        atv = c_form.text_input("Nome da Atividade")
                    else:
                        atv = c_form.selectbox("Selecionar Atividade", [a.upper() for a in atividades_padrao]) if atividades_padrao else c_form.text_input("Atividade")
                    locs_sel = st.multiselect("Pavimentos", [l['nome'] for l in locais])
                    c1, c2 = st.columns(2)
                    d_ini = c1.date_input("Data Inicio")
                    d_fim = c2.date_input("Data Fim")
                    
                    if st.form_submit_button("Adicionar Atividade", use_container_width=True):
                        if not locs_sel: st.warning("Selecione pavimentos.")
                        elif d_fim < d_ini: st.error("Data invalida.")
                        else:
                            inserts = []
                            map_ids = {l['nome']: l['id'] for l in locais}
                            str_ini = d_ini.strftime("%Y-%m-%d")
                            str_fim = d_fim.strftime("%Y-%m-%d")
                            for nome_loc in locs_sel:
                                inserts.append({
                                    "obra_id": obra_id, "local_id": map_ids[nome_loc], "atividade_nome": atv,
                                    "data_inicio": str_ini, "data_fim": str_fim, "status": "Planejado"
                                })
                            supabase.table("pcp_lob_atividades").insert(inserts).execute()
                            st.success("Salvo!")
                            time.sleep(1)
                            st.rerun()

        try:
            response = supabase.table("pcp_lob_atividades").select("*, pcp_locais(nome, ordem)").eq("obra_id", obra_id).execute()
            if not response.data:
                st.info("Cronograma vazio.")
            else:
                df = pd.DataFrame(response.data)
                df['pavimento'] = df['pcp_locais'].apply(lambda x: x['nome'] if x else "N/A")
                df['ordem_pav'] = df['pcp_locais'].apply(lambda x: x['ordem'] if x else 0)
                df['atividade_nome'] = df['atividade_nome'].fillna("Sem Nome")
                render_custom_lob(df)
        except Exception as e:
            st.error(f"Erro: {e}")

    if is_admin:
        with tabs[1]:
            render_management_tab(supabase, obra_id)

        with tabs[2]:
            with st.form("add_pav"):
                c1, c2 = st.columns([3, 1])
                nome = c1.text_input("Nome Pavimento")
                ordem = c2.number_input("Ordem", value=0)
                if st.form_submit_button("Salvar Pavimento"):
                    supabase.table("pcp_locais").insert({"obra_id": obra_id, "nome": nome, "ordem": ordem, "tipo": "Pavimento"}).execute()
                    st.rerun()
            
            res = supabase.table("pcp_locais").select("*").eq("obra_id", obra_id).order("ordem").execute()
            if res.data:
                st.markdown("---")
                for l in res.data:
                    c1, c2 = st.columns([4,1])
                    c1.text(f"{l['ordem']} - {l['nome']}")
                    if c2.button("Excluir", key=f"del_lob_{l['id']}"):
                        supabase.table("pcp_locais").delete().eq("id", l['id']).execute()
                        st.rerun()
