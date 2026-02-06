import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules import database
from modules import ui
import time

def get_mondays(start_date, num_weeks=12):
    """Gera lista de segundas-feiras"""
    current = start_date - timedelta(days=start_date.weekday())
    weeks = []
    for _ in range(num_weeks):
        weeks.append(current)
        current += timedelta(weeks=1)
    return weeks

def format_week_label(dt):
    end = dt + timedelta(days=4)
    return f"{dt.day:02d} a {end.day:02d}/{end.month:02d}"

def safe_date(val):
    if val is None: return None
    try:
        return pd.to_datetime(val).to_pydatetime().replace(tzinfo=None)
    except: return None

def render_pull_board(df):
    df['semana_ref'] = df['semana_ref'].apply(safe_date)
    df = df.dropna(subset=['semana_ref'])
    
    hoje = datetime.now()
    start_view = (hoje - timedelta(weeks=4)) - timedelta(days=hoje.weekday())
    end_view = start_view + timedelta(weeks=16)
    
    weeks_list = []
    curr = start_view
    while curr <= end_view:
        weeks_list.append(curr)
        curr += timedelta(weeks=1)
        
    locais_ordem = df[['local_nome', 'local_ordem']].drop_duplicates().sort_values('local_ordem')
    
    if locais_ordem.empty:
        st.info("Nenhum dado lançado no Pull Planning.")
        return

    st.markdown("""
    <style>
        .pull-board-container {
            display: flex;
            flex-direction: column;
            background-color: #121212;
            border: 1px solid #333;
            border-radius: 8px;
            overflow-x: auto;
            margin-bottom: 20px;
        }
        
        /* HEADER (LINHA SUPERIOR) */
        .board-header-row {
            display: flex;
            background-color: #1e1e1e;
            border-bottom: 2px solid #444;
            position: sticky;
            top: 0;
            z-index: 50;
            min-width: max-content;
        }
        .header-cell-local {
            position: sticky;
            left: 0;
            z-index: 60;
            background-color: #1e1e1e;
            color: #aaa;
            font-weight: bold;
            border-right: 2px solid #444;
            min-width: 180px;
            max-width: 180px;
            padding: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 2px 0 5px rgba(0,0,0,0.5);
        }
        .header-cell-week {
            min-width: 150px;
            max-width: 150px;
            padding: 10px;
            text-align: center;
            border-right: 1px solid #333;
            color: #ddd;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .week-current {
            background-color: rgba(227, 112, 38, 0.15);
            color: #E37026;
            border-bottom: 3px solid #E37026;
        }

        /* DATA ROW (LINHAS DE DADOS) */
        .board-data-row {
            display: flex;
            border-bottom: 1px solid #2a2a2a;
            min-width: max-content;
            min-height: 80px;
        }
        .row-header-local {
            position: sticky;
            left: 0;
            z-index: 40;
            background-color: #161616;
            color: #eee;
            font-size: 0.85rem;
            font-weight: 600;
            border-right: 2px solid #444;
            min-width: 180px;
            max-width: 180px;
            padding: 10px;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            text-align: right;
            box-shadow: 2px 0 5px rgba(0,0,0,0.5);
        }
        .row-cell-week {
            min-width: 150px;
            max-width: 150px;
            padding: 5px;
            border-right: 1px solid #2a2a2a;
            background-color: #121212;
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .row-cell-week:hover {
            background-color: #181818;
        }

        /* CARDS */
        .pp-card {
            background-color: #262626;
            border-radius: 4px;
            border-left: 4px solid #555;
            padding: 6px;
            font-size: 0.7rem;
            color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.4);
            transition: transform 0.1s;
        }
        .pp-card:hover {
            transform: translateY(-2px);
            filter: brightness(1.2);
            z-index: 10;
        }
    </style>
    """, unsafe_allow_html=True)

    html = []
    html.append('<div class="pull-board-container">')

    html.append('<div class="board-header-row">')
    html.append('<div class="header-cell-local">PAVIMENTO</div>')
    
    hoje_date = datetime.now().date()
    
    for wk in weeks_list:
        label = format_week_label(wk)
        wk_end = wk + timedelta(days=6)
        
        extra_class = "week-current" if wk.date() <= hoje_date <= wk_end.date() else ""
        
        html.append(f'<div class="header-cell-week {extra_class}">{label}</div>')
    html.append('</div>') 

    for _, lrow in locais_ordem.iterrows():
        loc_nome = lrow['local_nome']
        
        html.append('<div class="board-data-row">')
        html.append(f'<div class="row-header-local">{loc_nome}</div>')
        
        atvs_loc = df[df['local_nome'] == loc_nome]
        
        for wk in weeks_list:
            html.append('<div class="row-cell-week">')
            
            atvs_cell = atvs_loc[atvs_loc['semana_ref'].dt.date == wk.date()]
            
            for _, row in atvs_cell.iterrows():
                stt = row.get('status', 'Planejado')
                color = "#3B82F6" 
                if stt == 'Liberado': color = "#10B981"
                elif stt == 'Bloqueado': color = "#EF4444"
                elif stt == 'Em Analise': color = "#F59E0B"
                
                resp = row.get('responsavel', '') or ''
                
                html.append(f"""
                <div class="pp-card" style="border-left-color: {color};" title="{row['atividade']}">
                    <div style="font-weight:bold; margin-bottom:2px;">{row['atividade']}</div>
                    <div style="color:#aaa; font-size:0.6rem;">{resp}</div>
                </div>
                """)
                
            html.append('</div>') 
        html.append('</div>') 

    html.append('</div>') 
    st.markdown("".join(html), unsafe_allow_html=True)


def render_management(supabase, obra_id):
    st.markdown("##### Gerenciar Pull Planning")
    
    c1, c2 = st.columns(2)
    
    locais_disp = []
    try:
        r = supabase.table("pcp_locais").select("nome").eq("obra_id", obra_id).order("ordem").execute()
        locais_disp = [l['nome'] for l in r.data]
    except: pass
    
    filtro_local = c1.multiselect("Filtrar Local", locais_disp)
    
    query = supabase.table("pcp_pull_planning").select("*, pcp_locais(nome, ordem)").eq("obra_id", obra_id)
    
    response = query.execute()
    if not response.data:
        st.info("Nenhuma atividade encontrada.")
        return

    df = pd.DataFrame(response.data)
    df['local_nome'] = df['pcp_locais'].apply(lambda x: x['nome'] if x else "N/A")
    df['local_ordem'] = df['pcp_locais'].apply(lambda x: x['ordem'] if x else 0)
    df['semana_ref'] = df['semana_ref'].apply(safe_date)
    
    if filtro_local:
        df = df[df['local_nome'].isin(filtro_local)]
        
    df = df.sort_values(['semana_ref', 'local_ordem'])
    
    mondays = get_mondays(datetime.now() - timedelta(weeks=4), num_weeks=20)
    mondays_labels = {m.date(): format_week_label(m) for m in mondays}
    
    for i, row in df.iterrows():
        semana_label = format_week_label(row['semana_ref']) if row['semana_ref'] else "Sem Data"
        
        with st.expander(f"{semana_label} | {row['local_nome']} - {row['atividade']}"):
            c_ed = st.container()
            c_a, c_b = c_ed.columns(2)
            
            curr_date = row['semana_ref'].date() if row['semana_ref'] else mondays[0].date()
            try:
                idx_sem = list(mondays_labels.keys()).index(curr_date)
            except: 
                idx_sem = 0
                
            new_week_date = c_a.selectbox("Semana", list(mondays_labels.keys()), format_func=lambda x: mondays_labels[x], index=idx_sem, key=f"ed_wk_{row['id']}")
            
            curr_st = row.get('status', 'Planejado')
            opts = ["Planejado", "Em Analise", "Liberado", "Bloqueado"]
            try: st_ix = opts.index(curr_st)
            except: st_ix = 0
            new_status = c_b.selectbox("Status", opts, index=st_ix, key=f"ed_st_{row['id']}")
            
            new_resp = c_ed.text_input("Responsavel", value=row.get('responsavel', ''), key=f"ed_rp_{row['id']}")
            
            c_btn1, c_btn2 = c_ed.columns([1,1])
            if c_btn1.button("Salvar", key=f"sv_{row['id']}", type="primary", use_container_width=True):
                supabase.table("pcp_pull_planning").update({
                    "semana_ref": str(new_week_date),
                    "status": new_status,
                    "responsavel": new_resp
                }).eq("id", row['id']).execute()
                st.toast("Salvo!")
                time.sleep(0.5)
                st.rerun()
                
            if c_btn2.button("Excluir", key=f"dl_{row['id']}", use_container_width=True):
                supabase.table("pcp_pull_planning").delete().eq("id", row['id']).execute()
                st.rerun()

def app(obra_id):
    st.header("Pull Planning", divider="orange")
    
    supabase = database.get_db_client()
    user = st.session_state.get('user', {})
    is_admin = user.get('role') == 'admin'
    
    tabs_list = ["Mural Visual"]
    if is_admin:
        tabs_list.append("Gerenciar Atividades")
        
    tabs = st.tabs(tabs_list)
    
    with tabs[0]:
        if is_admin:
            with st.expander("Nova Atividade", expanded=False):
                c_form = st.container()
                
                usar_texto = c_form.toggle("Digitar nova atividade?", key="new_pp_tgg")
                
                atividades_padrao = []
                try:
                    r = supabase.table("pcp_atividades_padrao").select("atividade").execute()
                    atividades_padrao = [a['atividade'] for a in r.data]
                except: pass
                
                if usar_texto:
                    atv_input = c_form.text_input("Nome da Atividade")
                else:
                    atv_input = c_form.selectbox("Selecionar Atividade", [a.upper() for a in atividades_padrao]) if atividades_padrao else c_form.text_input("Atividade")
                
                locais = []
                try:
                    r = supabase.table("pcp_locais").select("id, nome").eq("obra_id", obra_id).order("ordem").execute()
                    locais = r.data
                except: pass
                
                c_1, c_2 = c_form.columns(2)
                loc_sel = c_1.selectbox("Local", [l['nome'] for l in locais])
                
                mondays = get_mondays(datetime.now(), num_weeks=12)
                week_opts = {m.date(): format_week_label(m) for m in mondays}
                sem_sel = c_2.selectbox("Semana", list(week_opts.keys()), format_func=lambda x: week_opts[x])
                
                resp_input = c_form.text_input("Responsavel (Opcional)")
                
                if c_form.button("Nova Atividade", type="primary"):
                    if not atv_input: 
                        st.warning("Preencha a atividade")
                    elif not loc_sel:
                        st.warning("Sem locais cadastrados")
                    else:
                        map_ids = {l['nome']: l['id'] for l in locais}
                        
                        payload = {
                            "obra_id": obra_id,
                            "local_id": map_ids.get(loc_sel),
                            "atividade": atv_input.upper(),
                            "semana_ref": str(sem_sel),
                            "responsavel": resp_input,
                            "status": "Planejado"
                        }
                        supabase.table("pcp_pull_planning").insert(payload).execute()
                        st.success("Post-it adicionado!")
                        time.sleep(0.5)
                        st.rerun()

        try:
            response = supabase.table("pcp_pull_planning").select("*, pcp_locais(nome, ordem)").eq("obra_id", obra_id).execute()
            
            if not response.data:
                st.info("Mural vazio. Adicione post-its.")
            else:
                df = pd.DataFrame(response.data)
                df['local_nome'] = df['pcp_locais'].apply(lambda x: x['nome'] if x else "N/A")
                df['local_ordem'] = df['pcp_locais'].apply(lambda x: x['ordem'] if x else 0)
                
                render_pull_board(df)
                
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")

    if is_admin and len(tabs) > 1:
        with tabs[1]:
            render_management(supabase, obra_id)
