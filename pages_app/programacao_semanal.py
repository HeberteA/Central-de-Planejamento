import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from modules import database
from modules import ui
import json
import math

def update_record(id, field, value):
    supabase = database.get_db_client()
    try:
        supabase.table("pcp_programacao_semanal").update({field: value}).eq("id", id).execute()
        st.toast("Salvo!", icon="✅")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def get_month_name(dt):
    meses = {
        1: 'JANEIRO', 2: 'FEVEREIRO', 3: 'MARÇO', 4: 'ABRIL',
        5: 'MAIO', 6: 'JUNHO', 7: 'JULHO', 8: 'AGOSTO',
        9: 'SETEMBRO', 10: 'OUTUBRO', 11: 'NOVEMBRO', 12: 'DEZEMBRO'
    }
    return f"{meses[dt.month]}"

def get_week_label(dt):
    first_day = dt.replace(day=1)
    adjusted_day = dt.day + first_day.weekday()
    week_num = (adjusted_day - 1) // 7 + 1
    return f"SEMANA {week_num}"

def app(obra_id):
    st.markdown("""
    <style>
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
        .status-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: bold;
            text-transform: uppercase;
            float: right;
        }
        .day-input-group {
            background: #262626;
            padding: 8px;
            border-radius: 5px;
            border: 1px solid #444;
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("# Programação Semanal")

    user = st.session_state['user']
    is_admin = user.get('role') == 'admin'

    c1, c2 = st.columns([1, 2])
    with c1:
        data_ref = st.date_input("Semana de Referência", datetime.now())
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
        c_top = st.container()
        
        c_a, c_b, c_c = c_top.columns(3)
        
        with c_a:
            usar_texto = st.toggle("Digitar Manualmente?", key="tgg_atv_manual")
            if usar_texto:
                atividade_val = st.text_input("Nome da Atividade", placeholder="Digite a atividade...")
            else:
                atividade_val = st.selectbox("Atividade Padrao", lista_atividades) if lista_atividades else st.text_input("Atividade")
        local_val = c_b.selectbox("Local", lista_locais) if lista_locais else c_a.text_input("Local")
        equipe_val = c_c.text_input("Equipe")
        detalhe_val = c_top.text_input("Detalhe / Recurso")

        c_days = c_top.container()
        cols_dias = c_days.columns(5)
        dias_labels = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta"]
        dias_keys = ["seg", "ter", "qua", "qui", "sex"]
        
        valores_dias = {}

        for i, col in enumerate(cols_dias):
            dia_key = dias_keys[i]
            with col:
                st.markdown(f"<div style='text-align:center; font-weight:bold; font-size:0.8rem; margin-bottom:5px;'>{dias_labels[i]}</div>", unsafe_allow_html=True)
                use_day = st.checkbox("Incluir", key=f"chk_new_{dia_key}", label_visibility="collapsed")
                val_day = st.text_input("Qtd", key=f"txt_new_{dia_key}", disabled=not use_day, label_visibility="collapsed", placeholder="-")
                
                if use_day:
                    valores_dias[dia_key] = val_day if val_day else "1"
                else:
                    valores_dias[dia_key] = None

        st.markdown("<br>", unsafe_allow_html=True)

        if c_top.button("Lançar Atividade", type="primary", use_container_width=True):
            if not atividade_val:
                st.warning("Preencha a atividade.")
            elif not any(valores_dias.values()):
                st.warning("Selecione pelo menos um dia da semana.")
            else:
                dados = {
                    "obra_id": obra_id,
                    "data_inicio_semana": start_week.strftime('%Y-%m-%d'),
                    "local": str(local_val).upper(),
                    "atividade": str(atividade_val).upper(),
                    "detalhe": str(detalhe_val).upper(),
                    "encarregado": str(equipe_val).upper(),
                    "rec_seg": valores_dias["seg"], 
                    "rec_ter": valores_dias["ter"], 
                    "rec_qua": valores_dias["qua"],
                    "rec_qui": valores_dias["qui"], 
                    "rec_sex": valores_dias["sex"],
                    "status": "A Iniciar"
                }
                try:
                    supabase.table("pcp_programacao_semanal").insert(dados).execute()
                    st.toast("Lancado com sucesso!", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
    
    st.markdown("---")

    response = supabase.table("pcp_programacao_semanal").select("*")\
        .eq("obra_id", obra_id)\
        .eq("data_inicio_semana", start_week.strftime('%Y-%m-%d'))\
        .order("local", desc=False).execute()
    
    df = pd.DataFrame(response.data)

    total_atividades = 0
    total_concluidas = 0
    total_dias_programados = 0
    total_dias_executados = 0
    ppc_percent = 0.0
    pap_percent = 0.0

    if not df.empty and 'status' in df.columns:
        total_atividades = len(df)
        total_concluidas = len(df[df['status'] == 'Concluido'])
        
        if total_atividades > 0:
            ppc_percent = (total_concluidas / total_atividades) * 100
        
        for idx, row in df.iterrows():
            for dia in ['seg', 'ter', 'qua', 'qui', 'sex']:
                rec_val = row.get(f'rec_{dia}')
                feito_val = row.get(f'feito_{dia}')
                
                if rec_val and str(rec_val).strip() != '':
                    total_dias_programados += 1
                    if feito_val is True:
                        total_dias_executados += 1
        
        if total_dias_programados > 0:
            pap_percent = (total_dias_executados / total_dias_programados) * 100
    else:
        df = pd.DataFrame(columns=['id', 'status', 'local', 'atividade', 'detalhe', 'encarregado', 
                                   'rec_seg', 'feito_seg', 'rec_ter', 'feito_ter', 
                                   'rec_qua', 'feito_qua', 'rec_qui', 'feito_qui', 
                                   'rec_sex', 'feito_sex', 'causa'])

    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card" style="border-bottom: 3px solid #E37026;">
            <div class="kpi-title">Total Atividades</div>
            <div class="kpi-value">{total_atividades}</div>
            <div class="kpi-sub">{total_concluidas} Concluidas</div>
        </div>
        <div class="kpi-card" style="border-bottom: 3px solid #3B82F6;">
            <div class="kpi-title">PPC (Semanal)</div>
            <div class="kpi-value">{ppc_percent:.1f}%</div>
            <div class="kpi-sub">Conclusao Status</div>
        </div>
        <div class="kpi-card" style="border-bottom: 3px solid #4ADE80;">
            <div class="kpi-title">PAP (Diario)</div>
            <div class="kpi-value">{pap_percent:.1f}%</div>
            <div class="kpi-sub">Aderencia Dias</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df.empty or total_atividades == 0:
        st.info("Nenhuma atividade programada para esta semana.")
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
                    "Motivo:",
                    lista_problemas,
                    index=idx_causa,
                    key=f"causa_{row['id']}",
                    placeholder="Selecione..."
                )
            else:
                new_causa = None

            st.markdown('<div style="margin: 5px 0;"></div>', unsafe_allow_html=True)
            
            d1, d2, d3, d4, d5 = st.columns(5)
            
            def day_widget(col_obj, label, db_val_rec, db_val_chk, suffix_id):
                with col_obj:
                    is_disabled = (db_val_rec is None or str(db_val_rec).strip() == '')
                    st.markdown(f"<div class='day-label'>{label}</div>", unsafe_allow_html=True)
                    if not is_disabled:
                        chk = st.checkbox("ok", value=db_val_chk, key=f"chk_{label}_{suffix_id}", label_visibility="collapsed")
                        txt = st.text_area("r", value=db_val_rec, key=f"txt_{label}_{suffix_id}", label_visibility="collapsed", height=35)
                        return chk, txt
                    else:
                        st.markdown("<div style='height: 28px; background: #222; border-radius: 4px; opacity: 0.3;'></div>", unsafe_allow_html=True)
                        return False, None

            chk_seg, txt_seg = day_widget(d1, "SEG", row['rec_seg'], row['feito_seg'], row['id'])
            chk_ter, txt_ter = day_widget(d2, "TER", row['rec_ter'], row['feito_ter'], row['id'])
            chk_qua, txt_qua = day_widget(d3, "QUA", row['rec_qua'], row['feito_qua'], row['id'])
            chk_qui, txt_qui = day_widget(d4, "QUI", row['rec_qui'], row['feito_qui'], row['id'])
            chk_sex, txt_sex = day_widget(d5, "SEX", row['rec_sex'], row['feito_sex'], row['id'])

            st.markdown('<div style="margin-top: 5px; border-top: 1px solid #333; padding-top: 10px;">', unsafe_allow_html=True)
            c_btn1, c_btn2 = st.columns([2, 1])
            
            with c_btn1:
                if st.button("Salvar", key=f"save_{row['id']}", use_container_width=True):
                    up_data = {"status": st.session_state[f"st_{row['id']}"]}
                    if txt_seg is not None: 
                        up_data["rec_seg"] = txt_seg
                        up_data["feito_seg"] = chk_seg
                    if txt_ter is not None: 
                        up_data["rec_ter"] = txt_ter
                        up_data["feito_ter"] = chk_ter
                    if txt_qua is not None: 
                        up_data["rec_qua"] = txt_qua
                        up_data["feito_qua"] = chk_qua
                    if txt_qui is not None: 
                        up_data["rec_qui"] = txt_qui
                        up_data["feito_qui"] = chk_qui
                    if txt_sex is not None: 
                        up_data["rec_sex"] = txt_sex
                        up_data["feito_sex"] = chk_sex

                    if st.session_state[f"st_{row['id']}"] == "Nao Concluido":
                        causa_val = st.session_state.get(f"causa_{row['id']}")
                        if causa_val: up_data['causa'] = causa_val
                    else:
                        up_data['causa'] = None

                    supabase.table("pcp_programacao_semanal").update(up_data).eq("id", row['id']).execute()
                    st.toast("Salvo!", icon="✅")
                    st.rerun()

            with c_btn2:
                if st.button("Excluir", key=f"del_{row['id']}", type="primary", use_container_width=True):
                    supabase.table("pcp_programacao_semanal").delete().eq("id", row['id']).execute()
                    st.rerun()

            st.markdown("</div></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### Fechamento da Semana")
    
    with st.expander("Finalizar Semana"):
        st.info("Ao finalizar, os indicadores desta semana serao salvos no historico.")
        
        if st.button("Confirmar Fechamento", type="primary", use_container_width=True):
            try:
                data_ref_str = start_week.strftime('%Y-%m-%d')
                mes_nome = get_month_name(start_week)
                ano_val = start_week.year
                semana_lbl = get_week_label(start_week)

                supabase.table("pcp_historico_indicadores").delete()\
                    .eq("obra_id", obra_id).eq("data_referencia", data_ref_str).execute()
                
                supabase.table("pcp_historico_problemas").delete()\
                    .eq("obra_id", obra_id).eq("data_referencia", data_ref_str).execute()

                supabase.table("pcp_historico_indicadores").insert({
                    "obra_id": obra_id,
                    "mes": mes_nome,
                    "ano": ano_val,
                    "semana_ref": semana_lbl,
                    "tipo_indicador": "PPC",
                    "valor_percentual": ppc_percent,
                    "meta_percentual": 80.0,
                    "data_referencia": data_ref_str
                }).execute()
                
                supabase.table("pcp_historico_indicadores").insert({
                    "obra_id": obra_id,
                    "mes": mes_nome,
                    "ano": ano_val,
                    "semana_ref": semana_lbl,
                    "tipo_indicador": "PAP",
                    "valor_percentual": pap_percent,
                    "meta_percentual": 80.0,
                    "data_referencia": data_ref_str
                }).execute()

                causas_series = df[df['status'] == 'Nao Concluido']['causa'].value_counts()
                
                if not causas_series.empty:
                    lista_problemas_insert = []
                    for causa, qtd in causas_series.items():
                        if causa:
                            lista_problemas_insert.append({
                                "obra_id": obra_id,
                                "mes": mes_nome,
                                "ano": ano_val,
                                "semana_ref": semana_lbl,
                                "problema_descricao": causa,  
                                "quantidade": int(qtd),
                                "data_referencia": data_ref_str
                            })
                    
                    if lista_problemas_insert:
                        supabase.table("pcp_historico_problemas").insert(lista_problemas_insert).execute()
                
                st.success("Semana finalizada com sucesso!")
                st.balloons()
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"Erro ao finalizar: {e}")
