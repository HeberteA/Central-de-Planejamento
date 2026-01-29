import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from modules import database
from modules import ui

def update_record(id, field, value):
    supabase = database.get_db_client()
    try:
        supabase.table("pcp_programacao_semanal").update({field: value}).eq("id", id).execute()
        st.toast("Salvo!", icon="✅")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def app(obra_id):
    st.markdown("""
    <style>
        /* Container KPI no Topo */
        .kpi-container {
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }
        .kpi-card {
            background: linear-gradient(135deg, #1e1e1e, #252525);
            border: 1px solid #333;
            border-radius: 10px;
            padding: 15px 20px;
            flex: 1;
            min-width: 150px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        .kpi-title {
            color: #aaa;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }
        .kpi-value {
            color: #fff;
            font-size: 1.8rem;
            font-weight: 700;
        }
        .kpi-sub {
            font-size: 0.75rem;
            color: #666;
        }
        
        /* Container do Card de Atividade */
        .task-card {
            background-color: #1E1E1E;
            border: 1px solid #333;
            border-left-width: 6px;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            transition: transform 0.2s;
        }
        .task-card:hover {
            border-color: #555;
            transform: translateY(-2px);
        }

        /* Tipografia do Card */
        .card-header-text {
            color: #fff;
            font-weight: 700;
            font-size: 1.1rem;
        }
        .card-sub-text {
            color: #aaa;
            font-size: 0.85rem;
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        
        /* Area de Inputs dos Dias */
        .day-box {
            background: rgba(255,255,255,0.03);
            padding: 5px;
            border-radius: 4px;
            text-align: center;
            border: 1px solid #333;
        }
        .day-label {
            font-size: 0.7rem;
            color: #888;
            margin-bottom: 2px;
            font-weight: bold;
        }
        
        /* Destaque para Causa Raiz */
        .problem-alert {
            background: rgba(239, 68, 68, 0.1);
            border: 1px dashed #EF4444;
            padding: 10px;
            border-radius: 6px;
            margin-top: 10px;
        }
        .status-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: bold;
            text-transform: uppercase;
            float: right;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("# Programação Semanal")

    user = st.session_state['user']
    is_admin = user.get('role') == 'admin'

    c1, c2 = st.columns([1, 2])
    with c1:
        data_ref = st.date_input("Semana de Referencia", datetime.now())
        start_week = data_ref - timedelta(days=data_ref.weekday())
        end_week = start_week + timedelta(days=4)
    
    with c2:
        st.markdown("")
        st.info(f"Periodo: {start_week.strftime('%d/%m/%Y')} a {end_week.strftime('%d/%m/%Y')}")

    supabase = database.get_db_client()

    lista_locais = []
    try:
        resp = supabase.table("pcp_locais").select("nome").eq("obra_id", obra_id).order("ordem").execute()
        if resp.data: lista_locais = [l['nome'] for l in resp.data]
    except: pass

    lista_atividades = []
    try:
        resp = supabase.table("pcp_atividades_padrao").select("atividade").order("atividade").execute()
        if resp.data: lista_atividades = [a['atividade'] for a in resp.data]
    except: pass
    
    lista_problemas = []
    try:
        resp = supabase.table("pcp_lista_problemas").select("*").execute()
        if resp.data:
            col_nome = 'descricao' if 'descricao' in resp.data[0] else 'problema'
            lista_problemas = [p[col_nome] for p in resp.data]
            lista_problemas.sort()
    except: pass

    with st.expander("Nova Atividade", expanded=False):
        with st.form("form_add"):
            c_a, c_b, c_c = st.columns(3)
            local = c_b.selectbox("Local", lista_locais) if lista_locais else c_a.text_input("Local")
            with c_a:
                usar_texto = st.toggle("Digitar nova atividade?", key="toggle_prog")
                if usar_texto:
                    atividade_input = st.text_input("Nome da Atividade", placeholder="Digite aqui...")
                else:
                    atividades_padrao = []
                    try:
                        r = supabase.table("pcp_atividades_padrao").select("atividade").execute()
                        atividades_padrao = [a['atividade'] for a in r.data]
                    except: pass
                    atividade_input = st.selectbox("Selecionar Atividade", atividades_padrao) if atividades_padrao else st.text_input("Atividade")

            equipe = c_c.text_input("Equipe")
            detalhe = st.text_input("Detalhe / Recurso")

            st.markdown("**Planejamento Inicial**")
            r1, r2, r3, r4, r5 = st.columns(5)
            rec_seg = r1.text_input("Seg", key="n_seg")
            rec_ter = r2.text_input("Ter", key="n_ter")
            rec_qua = r3.text_input("Qua", key="n_qua")
            rec_qui = r4.text_input("Qui", key="n_qui")
            rec_sex = r5.text_input("Sex", key="n_sex")

            if st.form_submit_button("Lançar Atividade", use_container_width=True):
                dados = {
                    "obra_id": obra_id,
                    "data_inicio_semana": start_week.strftime('%Y-%m-%d'),
                    "local": str(local).upper(),
                    "atividade": str(atividade_input).upper(),
                    "detalhe": str(detalhe).upper(),
                    "encarregado": str(equipe).upper(),
                    "rec_seg": rec_seg, "rec_ter": rec_ter, "rec_qua": rec_qua,
                    "rec_qui": rec_qui, "rec_sex": rec_sex,
                    "status": "A Iniciar"
                }
                supabase.table("pcp_programacao_semanal").insert(dados).execute()
                st.rerun()
    st.markdown("---")

    response = supabase.table("pcp_programacao_semanal").select("*")\
        .eq("obra_id", obra_id)\
        .eq("data_inicio_semana", start_week.strftime('%Y-%m-%d'))\
        .order("local", desc=False).execute()
    
    df = pd.DataFrame(response.data)

    if df.empty or 'status' not in df.columns:
        df = pd.DataFrame(columns=['id', 'status', 'local', 'atividade', 'detalhe', 'encarregado', 
                                   'rec_seg', 'feito_seg', 'rec_ter', 'feito_ter', 
                                   'rec_qua', 'feito_qua', 'rec_qui', 'feito_qui', 
                                   'rec_sex', 'feito_sex', 'causa'])
        total_pap = 0
        concluidas = 0
        ppc = 0
    else:
        total_pap = len(df)
        concluidas = len(df[df['status'] == 'Concluido'])
        ppc = (concluidas / total_pap * 100) if total_pap > 0 else 0

    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card" style="border-bottom: 3px solid #E37026;">
            <div class="kpi-title">PAP (Programado)</div>
            <div class="kpi-value">{total_pap}</div>
            <div class="kpi-sub">Atividades</div>
        </div>
        <div class="kpi-card" style="border-bottom: 3px solid #4ADE80;">
            <div class="kpi-title">Concluidas</div>
            <div class="kpi-value">{concluidas}</div>
            <div class="kpi-sub">Atividades</div>
        </div>
        <div class="kpi-card" style="border-bottom: 3px solid #3B82F6;">
            <div class="kpi-title">PPC Semanal</div>
            <div class="kpi-value">{ppc:.0f}%</div>
            <div class="kpi-sub">Aderencia</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("Nenhuma atividade programada.")
        return

    cols = st.columns(3)
    
    for idx, row in df.iterrows():
        col_atual = cols[idx % 3]
        
        with col_atual:
            status_color = "#888" 
            if row['status'] == 'Concluido': status_color = "#4ADE80" 
            elif row['status'] == 'Nao Concluido': status_color = "#EF4444" 
            elif row['status'] == 'Em Andamento': status_color = "#E37026" 
            st.markdown(f"""
            <div class="task-card" style="border-left-color: {status_color};">
                <div class="card-sub-text">{row['local']}</div>
                <span class="status-badge" style="color:{status_color};  border: 1px solid {status_color};">{row['status']}</span>
                <div class="card-header-text">{row['atividade']}</div>
                <div style="font-size: 0.8rem; color: #ccc; margin-bottom: 10px;">
                    {row['detalhe'] or ''} <span style="color: #666">|</span> {row['encarregado'] or 'S/ Equipe'}
                </div>
            """, unsafe_allow_html=True)
            
            opcoes_status = ["A Iniciar", "Em Andamento", "Concluido", "Nao Concluido"]
            idx_status = 0
            if row['status'] in opcoes_status:
                idx_status = opcoes_status.index(row['status'])
            
            new_status = st.selectbox(
                "Status", 
                opcoes_status,
                index=idx_status,
                key=f"st_{row['id']}",
                label_visibility="collapsed"
            )

            selected_causa = row.get('causa') 
            
            if new_status == "Nao Concluido":
                
                idx_causa = None
                if selected_causa and selected_causa in lista_problemas:
                    idx_causa = lista_problemas.index(selected_causa)
                
                new_causa = st.selectbox(
                    "Selecione a Causa do Nao Cumprimento:",
                    lista_problemas,
                    index=idx_causa,
                    key=f"causa_{row['id']}",
                    placeholder="Selecione o motivo..."
                )
            else:
                new_causa = None

            st.markdown('<div style="margin: 5px 0;"></div>', unsafe_allow_html=True)
            
            d1, d2, d3, d4, d5 = st.columns(5)
            
            def day_widget(col_obj, label, db_val_rec, db_val_chk, suffix_id):
                with col_obj:
                    st.markdown(f"<div class='day-label'>{label}</div>", unsafe_allow_html=True)
                    chk = st.checkbox("ok", value=db_val_chk, key=f"chk_{label}_{suffix_id}", label_visibility="collapsed")
                    txt = st.text_input("r", value=db_val_rec or "", key=f"txt_{label}_{suffix_id}", label_visibility="collapsed")
                    return chk, txt

            day_widget(d1, "SEG", row['rec_seg'], row['feito_seg'], row['id'])
            day_widget(d2, "TER", row['rec_ter'], row['feito_ter'], row['id'])
            day_widget(d3, "QUA", row['rec_qua'], row['feito_qua'], row['id'])
            day_widget(d4, "QUI", row['rec_qui'], row['feito_qui'], row['id'])
            day_widget(d5, "SEX", row['rec_sex'], row['feito_sex'], row['id'])

            st.markdown('<div style="margin-top: 5px; border-top: 1px solid #333; padding-top: 10px;">', unsafe_allow_html=True)
            
            c_btn1, c_btn2 = st.columns([2, 1])
            
            with c_btn1:
                if st.button("SALVAR", key=f"save_{row['id']}", use_container_width=True):
                    up_data = {
                        "status": st.session_state[f"st_{row['id']}"],
                        "rec_seg": st.session_state[f"txt_SEG_{row['id']}"],
                        "feito_seg": st.session_state[f"chk_SEG_{row['id']}"],
                        "rec_ter": st.session_state[f"txt_TER_{row['id']}"],
                        "feito_ter": st.session_state[f"chk_TER_{row['id']}"],
                        "rec_qua": st.session_state[f"txt_QUA_{row['id']}"],
                        "feito_qua": st.session_state[f"chk_QUA_{row['id']}"],
                        "rec_qui": st.session_state[f"txt_QUI_{row['id']}"],
                        "feito_qui": st.session_state[f"chk_QUI_{row['id']}"],
                        "rec_sex": st.session_state[f"txt_SEX_{row['id']}"],
                        "feito_sex": st.session_state[f"chk_SEX_{row['id']}"],
                    }
                    
                    if st.session_state[f"st_{row['id']}"] == "Nao Concluido":
                        causa_val = st.session_state.get(f"causa_{row['id']}")
                        if causa_val:
                            up_data['causa'] = causa_val
                    else:
                        up_data['causa'] = None

                    supabase.table("pcp_programacao_semanal").update(up_data).eq("id", row['id']).execute()
                    st.toast("Salvo!", icon="✅")
                    time.sleep(1)
                    st.rerun()

            with c_btn2:
                if st.button("EXCLUIR", key=f"del_{row['id']}", type="primary", use_container_width=True):
                    supabase.table("pcp_programacao_semanal").delete().eq("id", row['id']).execute()
                    st.rerun()

            st.markdown("</div></div>", unsafe_allow_html=True)
