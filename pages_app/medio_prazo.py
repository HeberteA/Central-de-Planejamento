import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from modules import database
from modules import ui

def update_status(id, new_status):
    supabase = database.get_db_client()
    try:
        supabase.table("pcp_medio_prazo").update({"status_liberacao": new_status}).eq("id", id).execute()
        st.toast(f"Status alterado para {new_status}", icon="🔄")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")

def delete_package(id):
    supabase = database.get_db_client()
    try:
        supabase.table("pcp_medio_prazo").delete().eq("id", id).execute()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")

def app(obra_id):
    st.markdown("""
    <style>
        /* Container Geral da Semana */
        .week-container {
            margin-bottom: 30px;
            border-bottom: 1px solid #333;
            padding-bottom: 20px;
        }
        
        /* Header da Semana (Data) */
        .week-header {
            font-size: 1.5rem;
            color: #E37026;
            font-weight: 700;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .week-header::before {
            content: '';
            display: block;
            width: 8px;
            height: 25px;
            background: #E37026;
            border-radius: 2px;
        }

        /* Card do Pacote */
        .mp-card {
            background-color: #1E1E1E;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 15px;
            position: relative;
            transition: all 0.3s ease;
            height: 100%;
        }
        .mp-card:hover {
            border-color: #555;
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }

        /* Badge de Status */
        .mp-badge {
            font-size: 0.7rem;
            font-weight: 800;
            text-transform: uppercase;
            padding: 4px 8px;
            border-radius: 4px;
            margin-bottom: 15px;
            float: right;
        }
        
        /* Tipografia do Card */
        .mp-title {
            color: #fff;
            font-weight: 700;
            font-size: 1rem;
            line-height: 1.3;
            margin-bottom: 5px;
        }
        .mp-local {
            color: #aaa;
            font-size: 0.8rem;
            text-transform: uppercase;
            margin-bottom: 10px;
            border-bottom: 1px solid #333;
            padding-bottom: 5px;
        }
        .mp-resp {
            color: #ccc;
            font-size: 0.8rem;
            display: flex;
            align-items: center;
            gap: 5px;
        }

        /* Botões de Ação no Card */
        div[data-testid="stButton"] button {
            border-radius: 6px;
            font-size: 0.8rem;
            padding: 4px 10px;
            height: auto;
            min-height: 0px;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("# Médio Prazo")

    supabase = database.get_db_client()

    user = st.session_state['user']
    is_admin = user.get('role') == 'admin'
    
    if is_admin:
        with st.expander("Nova Atividade", expanded=False):
            locais = {}
            try:
                r_loc = supabase.table("pcp_locais").select("id, nome").eq("obra_id", obra_id).order("ordem").execute()
                locais = {l['nome']: l['id'] for l in r_loc.data}
            except: pass
            
            atividades = []
            try:
                r_atv = supabase.table("pcp_atividades_padrao").select("atividade").order("atividade").execute()
                atividades = [a['atividade'] for a in r_atv.data]
            except: pass
            
            hoje = datetime.now()
            segunda_atual = hoje - timedelta(days=hoje.weekday())
            lista_semanas = []
            for i in range(6):
                inicio = segunda_atual + timedelta(weeks=i)
                fim = inicio + timedelta(days=4)
                label = f"({inicio.strftime('%d/%m')} a {fim.strftime('%d/%m')})"
                lista_semanas.append(label)

            with st.form("form_novo_pacote", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    c_form = st.container()   
                    usar_texto = st.toggle("Digitar nova atividade?", key="toggle_sem")
                    if usar_texto:
                        atv_sel = st.text_input("Nome da Atividade", placeholder="Digite aqui...")
                    else:
                        atividades_padrao = []
                        try:
                            r = supabase.table("pcp_atividades_padrao").select("atividade").execute()
                            atividades_padrao = [a['atividade'] for a in r.data]
                        except: pass
                        atv_sel = st.selectbox("Selecionar Atividade", atividades_padrao) if atividades_padrao else st.text_input("Atividade")
                semana_sel = c2.selectbox("Semana", lista_semanas)
                local_sel = c3.selectbox("Local", list(locais.keys())) if locais else c2.text_input("Local")
                
                c4, c5 = st.columns(2)
                resp_input = c4.text_input("Responsavel")
                status_input = c5.selectbox("Status Inicial", ["Em Analise", "Liberado", "Bloqueado"])
                
                if st.form_submit_button("Criar Atividade", use_container_width=True):
                    local_id = locais.get(local_sel) if locais else None
                    
                    payload = {
                        "obra_id": obra_id,
                        "semana_ref": semana_sel,
                        "local_id": local_id,
                        "atividade_nome": atv_sel.upper(),
                        "responsavel_execucao": resp_input.upper(),
                        "status_liberacao": status_input
                    }
                    supabase.table("pcp_medio_prazo").insert(payload).execute()
                    st.success("Pacote criado!")
                    time.sleep(0.5)
                    st.rerun()
        st.markdown("---")
    try:
        response = supabase.table("pcp_medio_prazo").select("*, pcp_locais(nome)").eq("obra_id", obra_id).execute()
        df = pd.DataFrame(response.data)
        
        if df.empty:
            st.info("Nenhum pacote cadastrado para o medio prazo.")
            return

        if 'pcp_locais' in df.columns:
            df['local_nome'] = df['pcp_locais'].apply(lambda x: x['nome'] if x else 'Geral')
        else:
            df['local_nome'] = "Local nao definido"

        semanas_ordenadas = sorted(df['semana_ref'].unique())

        for semana in semanas_ordenadas:
            data_label = semana.split('(')[-1].replace(')', '') if '(' in semana else semana
            
            st.markdown(f"""
            <div class="week-container">
                <div class="week-header">{data_label}</div>
            """, unsafe_allow_html=True)
            
            pacotes = df[df['semana_ref'] == semana]
            
            cols = st.columns(3)
            
            for idx, row in pacotes.iterrows():
                with cols[idx % 3]:
                    status = row['status_liberacao']
                    cor_bg = "#333"
                    cor_txt = "#fff"
                    
                    if status == 'Liberado':
                        cor_bg = "rgba(74, 222, 128, 0.2)" 
                        cor_txt = "#4ADE80"
                    elif status == 'Bloqueado':
                        cor_bg = "rgba(239, 68, 68, 0.2)" 
                        cor_txt = "#EF4444"
                    elif status == 'Em Analise':
                        cor_bg = "rgba(250, 204, 21, 0.2)" 
                        cor_txt = "#FACC15"

                    st.markdown(f"""
                    <div class="mp-card">
                        <span class="mp-badge" style="background-color: {cor_bg}; color: {cor_txt}; border: 1px solid {cor_txt};">
                            {status}
                        </span>
                        <div class="mp-local">{row['local_nome']}</div>
                        <div class="mp-title">{row['atividade_nome']}</div>
                        <div class="mp-resp">{row['responsavel_execucao'] or 'Nao atribuido'}</div>
                        <div style="margin-bottom: 15px;"></div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("</div></div>", unsafe_allow_html=True)
                    
                    c_act1, c_act2 = st.columns(2)
                    with c_act1:
                        if status != "Liberado":
                            if st.button("Liberar", key=f"lib_{row['id']}", use_container_width=True):
                                update_status(row['id'], "Liberado")
                        else:
                            if st.button("Bloquear", key=f"bloq_{row['id']}", use_container_width=True):
                                update_status(row['id'], "Bloqueado")
                                
                    with c_act2:
                        if is_admin:
                            if st.button("Excluir", key=f"del_{row['id']}", use_container_width=True):
                                delete_package(row['id'])
                        else:
                             st.button("Excluir", key=f"del_{row['id']}", disabled=True, use_container_width=True)

                    st.markdown("</div>", unsafe_allow_html=True) 

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
