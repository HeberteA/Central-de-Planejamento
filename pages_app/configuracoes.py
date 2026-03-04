import streamlit as st
import pandas as pd
import time
from modules import database

def app(obra_id):
    st.markdown("""
    <style>
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
    </style>
    """, unsafe_allow_html=True)

    st.header("Configuracoes da Obra", divider="orange")

    supabase = database.get_db_client()

    tab1, tab2, tab3 = st.tabs(["Atividades Padrao", "Locais", "Problemas"])

    with tab1:
        st.markdown("### Gerenciar Atividades Padrao")
        
        with st.expander("Nova Atividade", expanded=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                nova_ativ = st.text_input("Nome da Atividade Padrao")
            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Adicionar", key="btn_add_ativ", type="primary", use_container_width=True):
                    if nova_ativ:
                        try:
                            supabase.table("pcp_atividades_padrao").insert({"atividade": str(nova_ativ).upper()}).execute()
                            st.toast("Adicionado com sucesso!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
                    else:
                        st.warning("Preencha o nome da atividade.")

        st.markdown("---")
        
        try:
            resp_ativ = supabase.table("pcp_atividades_padrao").select("*").order("atividade").execute()
            df_ativ = pd.DataFrame(resp_ativ.data)
            
            if not df_ativ.empty:
                for idx, row in df_ativ.iterrows():
                
                    st.markdown(f"""
                    <div class="task-card" style="border-left-color: #3B82F6;">
                        <div class="card-header-text">{row['atividade']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Excluir", key=f"del_atv_{row['id']}", use_container_width=True):
                        supabase.table("pcp_atividades_padrao").delete().eq("id", row['id']).execute()
                        st.rerun()
            else:
                st.info("Nenhuma atividade padrao cadastrada.")
        except Exception as e:
            st.error(f"Erro ao carregar atividades: {e}")

    with tab2:
        st.markdown("### Gerenciar Locais da Obra")
        
        with st.expander("Novo Local", expanded=False):
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                novo_local = st.text_input("Nome do Local")
            with c2:
                nova_ordem = st.number_input("Ordem", min_value=1, value=1)
            with c3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Adicionar", key="btn_add_loc", type="primary", use_container_width=True):
                    if novo_local:
                        try:
                            supabase.table("pcp_locais").insert({
                                "obra_id": obra_id,
                                "nome": str(novo_local).upper(),
                                "ordem": nova_ordem
                            }).execute()
                            st.toast("Adicionado com sucesso!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
                    else:
                        st.warning("Preencha o nome do local.")

        st.markdown("---")
        
        try:
            resp_loc = supabase.table("pcp_locais").select("*").eq("obra_id", obra_id).order("ordem").execute()
            df_loc = pd.DataFrame(resp_loc.data)
            
            if not df_loc.empty:
            
                for idx, row in df_loc.iterrows():
                    
                    st.markdown(f"""
                    <div class="task-card" style="border-left-color: #E37026;">
                        <div style="color: #aaa; font-size: 0.8rem;">Ordem: {row['ordem']}</div>
                        <div class="card-header-text">{row['nome']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Excluir", key=f"del_loc_{row['id']}", use_container_width=True):
                        supabase.table("pcp_locais").delete().eq("id", row['id']).execute()
                        st.rerun()
            else:
                st.info("Nenhum local cadastrado para esta obra.")
        except Exception as e:
            st.error(f"Erro ao carregar locais: {e}")

    with tab3:
        st.markdown("### Gerenciar Problemas Padrao")
        
        with st.expander("Novo Problema", expanded=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                novo_prob = st.text_input("Nome do Problema", key="input_novo_prob")
            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Adicionar", key="btn_add_prob", type="primary", use_container_width=True):
                    if novo_prob:
                        try:
                            supabase.table("pcp_lista_problemas").insert({"descricao": str(novo_prob).upper()}).execute()
                            st.toast("Adicionado com sucesso!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
                    else:
                        st.warning("Preencha o nome do problema.")

        st.markdown("---")
        
        busca_prob = st.text_input("Pesquisar problema...", key="busca_prob")
        
        try:
            resp_prob = supabase.table("pcp_lista_problemas").select("*").order("descricao").execute()
            df_prob = pd.DataFrame(resp_prob.data)
            
            if not df_prob.empty:
                if busca_prob:
                    df_prob = df_prob[df_prob['descricao'].str.contains(busca_prob, case=False, na=False)]
                
                if not df_prob.empty:
                    for idx, row in df_prob.iterrows():
                        
                        st.markdown(f"""
                        <div class="task-card" style="border-left-color: #EF4444;">
                            <div class="card-header-text">{row['descricao']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button("Excluir", key=f"del_prob_{row['id']}", use_container_width=True):
                            supabase.table("pcp_lista_problemas").delete().eq("id", row['id']).execute()
                            st.rerun()
                else:
                    st.info("Nenhum problema encontrado na pesquisa.")
            else:
                st.info("Nenhum problema cadastrado.")
        except Exception as e:
            st.error(f"Erro ao carregar problemas: {e}")
