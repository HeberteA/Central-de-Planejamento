import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules import database
from modules import ui
import time
import math

def safe_date(val):
    if val is None: return None
    try:
        return pd.to_datetime(val).to_pydatetime().replace(tzinfo=None)
    except: return None

def get_month_name(dt):
    meses = {
        1: 'JANEIRO', 2: 'FEVEREIRO', 3: 'MARÇO', 4: 'ABRIL',
        5: 'MAIO', 6: 'JUNHO', 7: 'JULHO', 8: 'AGOSTO',
        9: 'SETEMBRO', 10: 'OUTUBRO', 11: 'NOVEMBRO', 12: 'DEZEMBRO'
    }
    return f"{meses[dt.month]}"

def get_week_label(dt):
    if not dt: return ""
    week_num = math.ceil(dt.day / 7)
    return f"SEMANA {week_num}"

def render_kpi_cards(df, start_week, end_week):
    current_month = start_week.month
    current_year = start_week.year
    
    count_pendente = len(df[df['status'] == 'Pendente'])
    
    df_removidas_mes = df[
        (df['status'] == 'Removida') & 
        (df['data_resolucao'].apply(lambda x: safe_date(x).month if safe_date(x) else 0) == current_month) &
        (df['data_resolucao'].apply(lambda x: safe_date(x).year if safe_date(x) else 0) == current_year)
    ]
    count_resolvidas_mes = len(df_removidas_mes)
    
    total_mes = count_pendente + count_resolvidas_mes
    
    df_removidas_semana = df[
        (df['status'] == 'Removida') & 
        (df['data_resolucao'] >= start_week.strftime('%Y-%m-%d')) & 
        (df['data_resolucao'] <= end_week.strftime('%Y-%m-%d'))
    ]
    count_resolvidas_semana = len(df_removidas_semana)
    
    irr = (count_resolvidas_semana / total_mes * 100) if total_mes > 0 else 0

    st.markdown("""
    <style>
        .kpi-row {
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }
        .kpi-box {
            flex: 1;
            background: linear-gradient(135deg, #1e1e1e 0%, #252525 100%);
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }
        .kpi-info { display: flex; flex-direction: column; }
        .kpi-val { font-size: 1.8rem; font-weight: bold; color: white; }
        .kpi-lbl { font-size: 0.75rem; color: #aaa; text-transform: uppercase; font-weight: 600; }
        .kb-red { border-left: 4px solid #EF4444; }
        .kb-green { border-left: 4px solid #10B981; }
        .kb-blue { border-left: 4px solid #3B82F6; }
    </style>
    """, unsafe_allow_html=True)

    html = f"""
    <div class="kpi-row">
        <div class="kpi-box kb-red">
            <div class="kpi-info">
                <span class="kpi-val">{total_mes}</span>
                <span class="kpi-lbl">Total Restrições (Mês)</span>
            </div>
        </div>
        <div class="kpi-box kb-green">
            <div class="kpi-info">
                <span class="kpi-val">{count_resolvidas_semana}</span>
                <span class="kpi-lbl">Removidas na Semana</span>
            </div>
        </div>
        <div class="kpi-box kb-blue">
            <div class="kpi-info">
                <span class="kpi-val">{irr:.1f}%</span>
                <span class="kpi-lbl">IRR</span>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    return total_mes, count_resolvidas_semana, irr

def render_boards(df, supabase):
    st.markdown("""
    <style>
        .section-title {
            font-size: 1rem;
            color: #E37026;
            margin-bottom: 15px;
            border-bottom: 1px solid #444;
            padding-bottom: 5px;
            font-weight: bold;
        }
        .group-header {
            background: #2a2a2a;
            color: #ddd;
            padding: 8px 12px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 0.85rem;
            margin-top: 15px;
            margin-bottom: 10px;
            border-left: 3px solid #E37026;
            display: flex;
            justify-content: space-between;
        }
        .rest-card {
            background: #1e1e1e;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 8px;
            transition: all 0.2s;
        }
        .rest-card:hover {
            border-color: #555;
            transform: translateX(3px);
        }
        .rc-top { display: flex; justify-content: space-between; align-items: start; margin-bottom: 5px; }
        .rc-area { background: #333; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
        .rc-prio { font-size: 0.65rem; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; }
        .p-Alta { background: rgba(239, 68, 68, 0.2); color: #EF4444; }
        .p-Media { background: rgba(245, 158, 11, 0.2); color: #F59E0B; }
        .p-Baixa { background: rgba(59, 130, 246, 0.2); color: #3B82F6; }
        
        .rc-desc { color: #eee; font-size: 0.9rem; margin-bottom: 8px; line-height: 1.3; }
        .rc-bott { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #2a2a2a; padding-top: 8px; }
        .rc-resp { color: #888; font-size: 0.75rem; }
        
        .col-wrapper {
            background: #161616;
            padding: 15px;
            border-radius: 8px;
            height: 100%;
            min-height: 400px;
        }
    </style>
    """, unsafe_allow_html=True)

    col_pend, col_res = st.columns(2)

    with col_pend:
        st.markdown('<div class="section-title">RESTRIÇÕES (POR MÊS)</div>', unsafe_allow_html=True)
        
        df_pend = df[df['status'] == 'Pendente'].copy()
        if df_pend.empty:
            st.info("Nenhuma pendência ativa.")
        else:
            df_pend['mes_grupo'] = df_pend['data_identificacao'].apply(lambda x: f"{get_month_name(safe_date(x))} {safe_date(x).year}" if safe_date(x) else "S/D")
            df_pend['data_dt'] = df_pend['data_identificacao'].apply(safe_date)
            df_pend = df_pend.sort_values('data_dt')
            
            grupos = df_pend['mes_grupo'].unique()
            
            for grupo in grupos:
                items = df_pend[df_pend['mes_grupo'] == grupo]
                st.markdown(f'<div class="group-header"><span>{grupo}</span><span>{len(items)}</span></div>', unsafe_allow_html=True)
                
                for _, row in items.iterrows():
                    area_txt = row.get('area', 'GERAL') or 'GERAL'
                    prio_cls = f"p-{row.get('prioridade', 'Media')}"
                    
                    c_card = st.container()
                    c1, c2 = c_card.columns([5, 1])
                    
                    with c1:
                        st.markdown(f"""
                        <div class="rest-card">
                            <div class="rc-top">
                                <span class="rc-area">{area_txt}</span>
                                <span class="rc-prio {prio_cls}">{row.get('prioridade', 'Media')}</span>
                            </div>
                            <div class="rc-desc">{row['descricao']}</div>
                            <div class="rc-bott">
                                <span class="rc-resp">Resp: {row['responsavel']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("OK", key=f"ok_{row['id']}", help="Marcar como Resolvido"):
                            supabase.table("pcp_restricoes").update({
                                "status": "Removida",
                                "data_resolucao": datetime.now().strftime('%Y-%m-%d')
                            }).eq("id", row['id']).execute()
                            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with col_res:
        st.markdown('<div class="section-title">REMOVIDAS (POR SEMANA)</div>', unsafe_allow_html=True)
        
        df_res = df[df['status'] == 'Removida'].copy()
        if df_res.empty:
            st.info("Nenhuma restrição removida ainda.")
        else:
            df_res['sem_grupo'] = df_res['data_resolucao'].apply(lambda x: f"{get_week_label(safe_date(x))} ({safe_date(x).year})" if safe_date(x) else "S/D")
            df_res['data_res_dt'] = df_res['data_resolucao'].apply(safe_date)
            df_res = df_res.sort_values('data_res_dt', ascending=False)
            
            grupos = df_res['sem_grupo'].unique()
            
            for grupo in grupos:
                items = df_res[df_res['sem_grupo'] == grupo]
                st.markdown(f'<div class="group-header" style="border-color: #10B981;"><span>{grupo}</span><span>{len(items)}</span></div>', unsafe_allow_html=True)
                
                for _, row in items.iterrows():
                    area_txt = row.get('area', 'GERAL') or 'GERAL'
                    
                    st.markdown(f"""
                    <div class="rest-card" style="opacity: 0.7;">
                        <div class="rc-top">
                            <span class="rc-area">{area_txt}</span>
                            <span style="color:#10B981; font-size:0.7rem;">RESOLVIDO</span>
                        </div>
                        <div class="rc-desc" style="text-decoration: line-through;">{row['descricao']}</div>
                        <div class="rc-bott">
                             <span class="rc-resp">Resp: {row['responsavel']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

def render_management(supabase, obra_id):
    st.markdown("##### Gerenciar Tudo")
    
    query = supabase.table("pcp_restricoes").select("*").eq("obra_id", obra_id).order("id")
    response = query.execute()
    if not response.data: return
    
    df = pd.DataFrame(response.data)
    
    for i, row in df.iterrows():
        status_txt = row.get('status', 'Pendente')
        with st.expander(f"{row['descricao']} ({status_txt})"):
            c_ed = st.container()
            c1, c2 = c_ed.columns(2)
            c3, c4 = c_ed.columns(2)
            
            n_desc = c1.text_input("Descricao", value=row['descricao'], key=f"ed_d_{row['id']}")
            n_area = c2.text_input("Area", value=row.get('area', ''), key=f"ed_a_{row['id']}")
            n_resp = c3.text_input("Responsavel", value=row.get('responsavel', ''), key=f"ed_r_{row['id']}")
            n_st = c4.selectbox("Status", ["Pendente", "Removida"], index=0 if status_txt=="Pendente" else 1, key=f"ed_s_{row['id']}")
            
            c5, c6 = c_ed.columns([1,1])
            if c5.button("Salvar Edicao", key=f"sv_{row['id']}", type="primary", use_container_width=True):
                upd = {
                    "descricao": n_desc.upper(),
                    "area": n_area.upper(),
                    "responsavel": n_resp.upper(),
                    "status": n_st
                }
                if n_st == "Removida" and row['status'] == "Pendente":
                    upd["data_resolucao"] = datetime.now().strftime('%Y-%m-%d')
                
                supabase.table("pcp_restricoes").update(upd).eq("id", row['id']).execute()
                st.toast("Atualizado!")
                time.sleep(0.5)
                st.rerun()
                
            if c6.button("Excluir", key=f"del_{row['id']}", use_container_width=True):
                supabase.table("pcp_restricoes").delete().eq("id", row['id']).execute()
                st.rerun()

def app(obra_id):
    st.markdown("### Quadro de Restrições")
    
    supabase = database.get_db_client()
    user = st.session_state.get('user', {})
    is_admin = user.get('role') == 'admin'

    c1, c2 = st.columns([1, 2])
    with c1:
        data_ref = st.date_input("Semana de Referencia", datetime.now())
        start_week = data_ref - timedelta(days=data_ref.weekday())
        end_week = start_week + timedelta(days=4)
    with c2:
        st.markdown("")
        st.info(f"Periodo: {start_week.strftime('%d/%m/%Y')} a {end_week.strftime('%d/%m/%Y')}")
    
    total_mes_val = 0
    removidas_sem_val = 0
    irr_val = 0

    try:
        resp = supabase.table("pcp_restricoes").select("*").eq("obra_id", obra_id).execute()
        df_all = pd.DataFrame(resp.data) if resp.data else pd.DataFrame(columns=['status', 'data_identificacao', 'data_resolucao'])
        
        total_mes_val, removidas_sem_val, irr_val = render_kpi_cards(df_all, start_week, end_week)
    except:
        df_all = pd.DataFrame()

    tabs_list = ["Visualização"]
    if is_admin:
        tabs_list.append("Gerenciar")
        
    tabs = st.tabs(tabs_list)
    
    with tabs[0]:
        if is_admin:
            with st.expander("Nova Restrição", expanded=False):
                c_form = st.container()
                
                c1, c2 = c_form.columns(2)
                desc_in = c1.text_input("Descrição da Restrição")
                area_in = c2.text_input("Área (Ex: PROJETO, MÃO DE OBRA)")
                
                c3, c4 = c_form.columns(2)
                resp_in = c3.text_input("Responsável")
                prio_in = c4.selectbox("Prioridade", ["Alta", "Media", "Baixa"], index=1)
                
                if c_form.button("Registrar Restrição", type="primary"):
                    if not desc_in:
                        st.warning("Preencha a descrição.")
                    else:
                        payload = {
                            "obra_id": obra_id,
                            "area": area_in.upper(),
                            "descricao": desc_in.upper(),
                            "responsavel": resp_in.upper(),
                            "prioridade": prio_in,
                            "status": "Pendente",
                            "data_identificacao": datetime.now().strftime('%Y-%m-%d')
                        }
                        supabase.table("pcp_restricoes").insert(payload).execute()
                        st.success("Adicionado!")
                        time.sleep(0.5)
                        st.rerun()
        
        if not df_all.empty:
            render_boards(df_all, supabase)
        else:
            st.info("Nenhuma restrição lançada.")

    if is_admin and len(tabs) > 1:
        with tabs[1]:
            render_management(supabase, obra_id)

    st.markdown("---")
    with st.expander("Finalizar Semana"):
        st.warning("Isso salvará o histórico de restrições para o Dashboard.")
        if st.button("Confirmar Fechamento", type="primary"):
            try:
                
                mes_nome = get_month_name(start_week)
                ano_val = start_week.year
                semana_label = get_week_label(start_week) 
                supabase.table("pcp_historico_irr").delete().eq("obra_id", obra_id).eq("data_referencia", start_week.strftime('%Y-%m-%d')).execute()
                
                dados_irr = {
                    "obra_id": obra_id,
                    "mes": mes_nome,
                    "ano": ano_val,
                    "semana_ref": semana_label,
                    "restricoes_totais": total_mes_val,
                    "restricoes_removidas": removidas_sem_val,
                    "irr_percentual": irr_val,
                    "data_referencia": start_week.strftime('%Y-%m-%d'),
                    "meta_percentual": 80.0
                }
                
                supabase.table("pcp_historico_irr").insert(dados_irr).execute()
                st.success("Dados salvos no histórico!")
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
