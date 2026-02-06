import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules import database
from modules import ui

def app(obra_id):
    ui.header("Suprimentos", divider="orange")

    supabase = database.get_db_client()
    user_role = st.session_state['user'].get('role', 'user')

    tab_monitor, tab_solicitacao = st.tabs(["Monitoramento de Compras", "Nova Solicitação"])

    with tab_monitor:
        try:
            response = supabase.table("pcp_suprimentos").select("*").eq("obra_id", obra_id).order("data_necessidade").execute()
            
            if response.data:
                df = pd.DataFrame(response.data)
                df['data_necessidade'] = pd.to_datetime(df['data_necessidade'])
                
                render_cards_suprimentos(df)
            else:
                st.info("Nenhuma solicitação de material cadastrada.")
                
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")

    with tab_solicitacao:
        if user_role == 'admin':
            st.markdown("#### Solicitar Material")
            
            with st.form("form_sup", clear_on_submit=True):
                c1, c2 = st.columns(2)
                item_nome = c1.text_input("Item / Material")
                data_nec = c2.date_input("Data de Necessidade na Obra")
                
                status_inicial = st.selectbox("Status Atual", ["A Cotar", "Em Cotação", "Comprado", "Entregue"])
                
                if st.form_submit_button("Salvar Solicitação"):
                    if item_nome:
                        try:
                            dados = {
                                "obra_id": obra_id,
                                "item": item_nome,
                                "data_necessidade": data_nec.isoformat(),
                                "status_compra": status_inicial
                            }
                            supabase.table("pcp_suprimentos").insert(dados).execute()
                            st.success("Solicitação salva")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
                    else:
                        st.warning("Nome do item obrigatório")
        else:
            st.info("Apenas administradores podem cadastrar solicitações.")

def render_cards_suprimentos(df):
    hoje = datetime.now()
    
    st.markdown("""
    <style>
        .sup-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
            padding: 10px 0;
        }
        .sup-card {
            background: rgba(40,40,40,0.6);
            border-radius: 8px;
            padding: 15px;
            border-left: 5px solid #555;
            position: relative;
        }
        .sup-atrasado { border-left-color: #EF4444; }
        .sup-atencao { border-left-color: #FACC15; }
        .sup-ok { border-left-color: #3B82F6; }
        .sup-entregue { border-left-color: #4ADE80; opacity: 0.6; }
        
        .sup-date { font-size: 0.8rem; color: #aaa; margin-bottom: 5px; }
        .sup-item { font-weight: bold; color: white; font-size: 1rem; margin-bottom: 5px; }
        .sup-status { 
            font-size: 0.75rem; 
            text-transform: uppercase; 
            background: rgba(255,255,255,0.1); 
            padding: 2px 6px; 
            border-radius: 4px; 
            display: inline-block;
        }
    </style>
    """, unsafe_allow_html=True)
    
    html = "<div class='sup-container'>"
    
    for _, row in df.iterrows():
        dias_restantes = (row['data_necessidade'] - today_date(hoje)).days
        
        classe = "sup-ok"
        if row['status_compra'] == 'Entregue':
            classe = "sup-entregue"
        elif dias_restantes < 0:
            classe = "sup-atrasado"
        elif dias_restantes < 15:
            classe = "sup-atencao"
            
        data_fmt = row['data_necessidade'].strftime('%d/%m/%Y')
        
        html += f"""
        <div class='sup-card {classe}'>
            <div class='sup-date'> Necessidade: {data_fmt}</div>
            <div class='sup-item'>{row['item']}</div>
            <div class='sup-status'>{row['status_compra']}</div>
        </div>
        """
        
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def today_date(dt):
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)
