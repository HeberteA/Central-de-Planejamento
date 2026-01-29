import streamlit as st
import pandas as pd
from modules import database
from modules import ui
import time

def render_pavimentos(supabase, obra_id):
    st.markdown("""
    <style>
        .pav-card {
            background-color: #262626;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 4px solid #E37026;
            transition: transform 0.2s;
        }
        .pav-card:hover { transform: translateX(5px); background-color: #333; }
        .pav-info { display: flex; align-items: center; gap: 15px; }
        .pav-ordem { 
            background: #444; color: white; 
            width: 30px; height: 30px; 
            border-radius: 50%; 
            display: flex; align-items: center; justify-content: center;
            font-weight: bold; font-size: 0.9rem;
        }
        .pav-nome { font-size: 1rem; font-weight: 500; color: #eee; }
    </style>
    """, unsafe_allow_html=True)
    
    with st.expander("Adicionar Pavimento", expanded=False):
        c_form = st.container()
        c1, c2 = c_form.columns([3, 1])
        novo_nome = c1.text_input("Nome do Pavimento")
        nova_ordem = c2.number_input("Ordem", value=0, step=1)
        
        if c_form.button("Salvar Pavimento", type="primary"):
            if novo_nome:
                try:
                    supabase.table("pcp_locais").insert({
                        "obra_id": obra_id, "nome": novo_nome.upper(), "ordem": nova_ordem, "tipo": "Pavimento"
                    }).execute()
                    st.success("Salvo!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    try:
        resp = supabase.table("pcp_locais").select("*").eq("obra_id", obra_id).order("ordem", desc=True).execute()
        locais = resp.data
        
        if not locais:
            st.info("Nenhum pavimento cadastrado.")
        
        for loc in locais:
            c_card = st.container()
            col_a, col_b = c_card.columns([5, 1])
            
            with col_a:
                st.markdown(f"""
                <div class="pav-card">
                    <div class="pav-info">
                        <div class="pav-ordem">{loc['ordem']}</div>
                        <div class="pav-nome">{loc['nome']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_b:
                st.markdown("")
                if st.button("Excluir", key=f"del_pav_{loc['id']}", help="Excluir Pavimento"):
                    supabase.table("pcp_locais").delete().eq("id", loc['id']).execute()
                    st.rerun()
                    
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")

def render_atividades_padrao(supabase):
    st.markdown("""
    <style>
        .atv-tag {
            display: inline-flex;
            align-items: center;
            background: #1E1E1E;
            border: 1px solid #333;
            border-radius: 20px;
            padding: 8px 16px;
            margin: 5px;
            color: #ddd;
            font-size: 0.9rem;
        }
        .atv-icon { margin-right: 8px; color: #E37026; }
    </style>
    """, unsafe_allow_html=True)

    with st.expander("Nova Atividade", expanded=False):
        c_add = st.container()
        nova_atv = c_add.text_input("Nome da Atividade")
        if c_add.button("CADASTRAR ATIVIDADE"):
            if nova_atv:
                try:
                    supabase.table("pcp_atividades_padrao").insert({"atividade": nova_atv.upper()}).execute()
                    st.success("Cadastrada!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.warning(f"Erro: Essa atividade provavelmente já está cadastrada.")

    try:
        resp = supabase.table("pcp_atividades_padrao").select("*").order("atividade").execute()
        atvs = resp.data
    
        
        if not atvs:
            st.info("Nenhuma atividade padrão.")
            
        for atv in atvs:
            c1, c2 = st.columns([6, 1])
            with c1:
                st.markdown(f"""
                <div class="atv-tag">
                    <span class="atv-icon">●</span>
                    {atv['atividade']}
                </div>
                """, unsafe_allow_html=True)
            with c2:
                if st.button("Excluir", key=f"del_atv_{atv['id']}"):
                    supabase.table("pcp_atividades_padrao").delete().eq("id", atv['id']).execute()
                    st.rerun()
                    
    except Exception as e:
        st.error(f"Erro: {e}")

def render_gestao_obras(supabase):
    st.markdown("##### Gestão de Obras")
    
    with st.expander("Cadastrar Nova Obra", expanded=False):
        c_form = st.container()
        nome_obra = c_form.text_input("Nome da Obra")
        senha_inicial = c_form.text_input("Senha Inicial", value="1234")
        
        c_mod1, c_mod2 = c_form.columns(2)
        ini_lob = c_mod1.checkbox("Ativar LOB?", value=True)
        ini_pull = c_mod2.checkbox("Ativar Pull Planning?", value=True)
        
        if c_form.button("Criar Nova Obra", type="primary"):
            if nome_obra:
                supabase.table("pcp_obras").insert({
                    "nome": nome_obra.upper(),
                    "senha_acesso": senha_inicial,
                    "ativa": True,
                    "usa_lob": ini_lob,
                    "usa_pull": ini_pull
                }).execute()
                st.success("Obra criada!")
                time.sleep(1)
                st.rerun()

    st.markdown("---")
    
    try:
        resp = supabase.table("pcp_obras").select("*").order("nome").execute()
        obras = resp.data
        
        for obra in obras:
            status_txt = "ATIVA" if obra.get('ativa', True) else "INATIVA"
            
            with st.expander(f"{obra['nome']} ({status_txt})", expanded=False):
                c_edit = st.container()
                
                c1, c2 = c_edit.columns(2)
                nova_senha = c1.text_input("Senha de Acesso", value=obra.get('senha_acesso', ''), key=f"pw_{obra['id']}")
                is_ativa = c2.toggle("Obra Ativa?", value=obra.get('ativa', True), key=f"at_{obra['id']}")
                
                st.markdown("###### Módulos")
                c3, c4 = c_edit.columns(2)
                use_lob = c3.toggle("Utiliza Longo Prazo (LOB)?", value=obra.get('usa_lob', True), key=f"lob_{obra['id']}")
                use_pull = c4.toggle("Utiliza Pull Planning?", value=obra.get('usa_pull', True), key=f"pull_{obra['id']}")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if c_edit.button("Salvar Alterações", key=f"upd_{obra['id']}", type="primary"):
                    supabase.table("pcp_obras").update({
                        "senha_acesso": nova_senha,
                        "ativa": is_ativa,
                        "usa_lob": use_lob,
                        "usa_pull": use_pull
                    }).eq("id", obra['id']).execute()
                    st.toast("Dados atualizados!")
                    time.sleep(0.5)
                    st.rerun()
                    
    except Exception as e:
        st.error(f"Erro ao listar obras: {e}")

def app(obra_id):
    supabase = database.get_db_client()
    user = st.session_state.get('user', {})
    is_admin = user.get('role') == 'admin'
    
    st.markdown("# Configurações")
    
    tabs_list = []
    
    if is_admin:
        tabs_list.append("Gestão de Obras")
        
    tabs_list.extend(["Pavimentos", "Atividades Padrão"])
    
    tabs = st.tabs(tabs_list)
    
    current_tab = 0
    
    if is_admin:
        with tabs[current_tab]:
            render_gestao_obras(supabase)
        current_tab += 1
        
    with tabs[current_tab]:
        render_pavimentos(supabase, obra_id)
    current_tab += 1
        
    with tabs[current_tab]:
        render_atividades_padrao(supabase)
