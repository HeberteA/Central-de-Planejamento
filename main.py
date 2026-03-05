import streamlit as st
from streamlit_option_menu import option_menu
from PIL import Image
from modules import database
from modules import ui
import time
import os
import base64
from fpdf import FPDF
import matplotlib.pyplot as plt
import tempfile
from datetime import datetime, timedelta
import os


st.set_page_config(
    page_title="Centro de Planejamento",
    layout="wide",
    page_icon="assets/favicon.png",
    initial_sidebar_state="expanded"
)

ui.inject_css()

st.markdown("""
    <style>
        [data-testid="stImage"] {
            display: flex;
            justify-content: center;
            align-items: center;
        }
        img {
            max-width: 200px;
            margin-bottom: 20px;
        }
        
        h1, h2, h3 { color: #ffffff !important; font-weight: 600; letter-spacing: -0.5px; }
        
        .login-container {
            background-color: transparent; 
            background-image: linear-gradient(160deg, #1e1e1f 0%, #0a0a0c 100%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 10px;
        }
        .sidebar-logo-container {
            text-align: center;
            padding: 20px 0;
            margin-bottom: 20px;
        }
        .sidebar-logo-text {
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            font-size: 1.2rem;
            color: white;
            letter-spacing: 2px;
        }
        .sidebar-logo-sub {
            font-size: 0.9rem;
            color: var(--primary);
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-top: 5px
        }
        h1, h2, h3 { color: #ffffff !important; font-weight: 600; letter-spacing: -0.5px; }
    </style>
""", unsafe_allow_html=True)

if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'obra_ativa_id' not in st.session_state:
    st.session_state['obra_ativa_id'] = None

def get_obra_config(supabase, obra_id):
    if not obra_id: return {"usa_lob": True, "usa_pull": True}
    try:
        r = supabase.table("pcp_obras").select("usa_lob, usa_pull").eq("id", obra_id).single().execute()
        if r.data: return r.data
    except: pass
    return {"usa_lob": True, "usa_pull": True}

def get_base64_image(image_path):
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def gerar_pdf_semanal(data_ref_str):
    supabase = database.get_db_client()

    resp_obras = supabase.table("pcp_obras").select("id, nome").execute()
    mapa_obras = {}
    if resp_obras.data:
        for o in resp_obras.data:
            mapa_obras[o['id']] = o['nome']

    resp_prog = supabase.table("pcp_programacao_semanal").select("*").eq("data_inicio_semana", data_ref_str).execute()
    dados_prog = []
    if resp_prog.data:
        dados_prog = resp_prog.data

    total_atividades = len(dados_prog)
    total_pontos_ppc = 0.0
    total_dias_programados = 0
    total_dias_executados = 0
    contagem_causas = {}

    for d in dados_prog:
        status_atual = d.get('status')
        
        if status_atual == 'Concluido':
            total_pontos_ppc += 1.0
        elif status_atual == 'Em Andamento':
            perc = d.get('percentual', 0)
            try:
                val_perc = float(perc) if perc else 0.0
            except:
                val_perc = 0.0
            total_pontos_ppc += (val_perc / 100.0)

        for dia in ['seg', 'ter', 'qua', 'qui', 'sex']:
            rec_val = d.get(f'rec_{dia}')
            feito_val = d.get(f'feito_{dia}')
            if rec_val and str(rec_val).strip() != '':
                total_dias_programados += 1
                if feito_val is True:
                    total_dias_executados += 1

        if status_atual in ['Nao Concluido', 'Em Andamento']:
            causa = d.get('causa')
            if causa:
                contagem_causas[causa] = contagem_causas.get(causa, 0) + 1

    ppc_global = (total_pontos_ppc / total_atividades * 100) if total_atividades > 0 else 0.0
    pap_global = (total_dias_executados / total_dias_programados * 100) if total_dias_programados > 0 else 0.0

    fig1, ax1 = plt.subplots(figsize=(5, 4))
    ax1.bar(['PPC', 'PAP'], [ppc_global, pap_global], color=['#3B82F6', '#4ADE80'])
    ax1.set_ylim(0, 100)
    for i, v in enumerate([ppc_global, pap_global]):
        ax1.text(i, v + 2, f"{v:.1f}%", ha='center', va='bottom', fontweight='bold')
    plt.title("Indicadores Globais")
    plt.tight_layout()
    tmp1 = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    plt.savefig(tmp1.name)
    plt.close(fig1)

    fig2, ax2 = plt.subplots(figsize=(5, 4))
    if contagem_causas:
        causas_ordenadas = sorted(contagem_causas.items(), key=lambda x: x[1], reverse=True)
        labels = [c[0][:15] for c in causas_ordenadas]
        valores = [c[1] for c in causas_ordenadas]
        ax2.bar(labels, valores, color='#EF4444')
        plt.xticks(rotation=45, ha='right')
        for i, v in enumerate(valores):
            ax2.text(i, v + 0.1, str(v), ha='center', va='bottom', fontweight='bold')
    else:
        ax2.text(0.5, 0.5, "Nenhum problema", ha='center', va='center')
        ax2.axis('off')
    plt.title("Problemas da Semana")
    plt.tight_layout()
    tmp2 = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    plt.savefig(tmp2.name)
    plt.close(fig2)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16, style='B')
    pdf.cell(200, 10, txt="Relatorio Semanal Global - Central de Planejamento", ln=True, align='C')

    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Semana de Referencia: {data_ref_str}", ln=True, align='C')
    pdf.ln(5)

    pdf.image(tmp1.name, x=10, y=35, w=85)
    pdf.image(tmp2.name, x=105, y=35, w=85)
    pdf.ln(75)

    os.remove(tmp1.name)
    os.remove(tmp2.name)

    dados_agrupados = {}
    for d in dados_prog:
        obra_nome = mapa_obras.get(d['obra_id'], "Obra Desconhecida")
        if obra_nome not in dados_agrupados:
            dados_agrupados[obra_nome] = []
        dados_agrupados[obra_nome].append(d)

    for obra, atividades in dados_agrupados.items():
        pdf.set_font("Arial", size=14, style='B')
        pdf.cell(200, 10, txt=f"Obra: {obra}", ln=True, align='L')
        pdf.set_font("Arial", size=10, style='B')
        pdf.cell(50, 8, txt="Local", border=1)
        pdf.cell(90, 8, txt="Atividade", border=1)
        pdf.cell(40, 8, txt="Status", border=1, ln=True)

        pdf.set_font("Arial", size=10)
        for atv in atividades:
            local = str(atv.get('local', ''))[:25]
            atividade = str(atv.get('atividade', ''))[:45]
            status = str(atv.get('status', ''))[:15]
            pdf.cell(50, 8, txt=local, border=1)
            pdf.cell(90, 8, txt=atividade, border=1)
            pdf.cell(40, 8, txt=status, border=1, ln=True)
        pdf.ln(5)

    try:
        return pdf.output(dest='S').encode('latin-1')
    except TypeError:
        return bytes(pdf.output())

def login_screen():
    supabase = database.get_db_client()
    
    c_out1, c_out2, c_out3 = st.columns([1, 1, 1])
    
    with c_out2:
        
        logo_file = "assets/logo.png" if os.path.exists("assets/logo.png") else "Lavie.jpg"
        img_b64 = get_base64_image(logo_file)
        
        if img_b64:
            mime_type = "image/png" if logo_file.endswith(".png") else "image/jpeg"
            header_html = f'<img src="data:{mime_type};base64,{img_b64}" style="width: 650px; height: auto; display: block; margin: 0 auto 20px auto;">'
        else:
            header_html = "<h2 style='color:#E37026; margin-bottom: 10px;'>LAVIE</h2>"

        st.markdown(f"""
        <div class="login-container">
            {header_html}
            <h2 style='color:#ffffff; font-size: 2.3rem; margin-top: 10px; margin-bottom: 0px;'>CENTRAL DE PLANEJAMENTO</h2>
        </div>
        """, unsafe_allow_html=True)
            
        tab_obra, tab_admin = st.tabs(["EQUIPE DE OBRA", "ADMINISTRADOR"])
            
        with tab_obra:
            obras_list = []
            obras_map = {}
            try:
                r = supabase.table("pcp_obras").select("id, nome").execute()
                for item in r.data:
                    obras_list.append(item['nome'])
                    obras_map[item['nome']] = item['id']
            except: pass
                
            sel_obra = st.selectbox("Selecione a Obra", obras_list)
            senha_obra = st.text_input("Senha da Obra", type="password", key="pwd_obra")
                
            if st.button("Acessar Obra", use_container_width=True):
                    
                res = supabase.table("pcp_obras").select("*").eq("id", obras_map.get(sel_obra)).eq("senha_acesso", senha_obra).execute()
                if res.data:
                    res_user = supabase.table("pcp_users").select("*").neq("role", "admin").limit(1).execute()
                    if res_user.data:
                        st.session_state['user'] = res_user.data[0] 
                        st.session_state['obra_ativa_id'] = obras_map[sel_obra]
                        st.rerun()
                else:
                    st.error("Senha incorreta.")

        with tab_admin:
            senha_admin = st.text_input("Senha", type="password", key="pwd_admin")
                
            if st.button("Acessar Como Admin", use_container_width=True):
                    
                res = supabase.table("pcp_users").select("*").eq("password", senha_admin).eq("role", "admin").execute()
                if res.data:
                    user_data = res.data[0]
                    st.session_state['user'] = user_data
                        
                    obras_res = supabase.table("pcp_obras").select("*").execute()
                    if obras_res.data:
                        st.session_state['obra_ativa_id'] = obras_res.data[0]['id']
                    st.rerun()
                else:
                    st.error("Senha de administrador invalida.")
                    

def logout():
    st.session_state['user'] = None
    st.session_state['obra_ativa_id'] = None
    st.rerun()

if not st.session_state['user']:
    login_screen()
else:
    supabase = database.get_db_client()
    user = st.session_state['user']
    is_admin = user.get('role') == 'admin'
    
    with st.sidebar:
        try:
            st.image("assets/logo.png")
        except:
            st.markdown("### Centro de Planejamento")

        
        if is_admin:
            obras = []
            try:
                r = supabase.table("pcp_obras").select("id, nome").eq("ativa", True).execute()
                obras = r.data
            except: pass
            htp=f"""
            <div class="sidebar-logo-container">
                <div class="sidebar-logo-text">CENTRAL DE PLANEJAMENTO</div>
                <div class="sidebar-logo-sub">Administrador</div>
            </div>
            """
            st.markdown(htp, unsafe_allow_html=True)

            
            nomes_obras = [o['nome'] for o in obras]
            if nomes_obras:
                default_ix = 0
                current_id = st.session_state['obra_ativa_id']
                if current_id:
                    for i, o in enumerate(obras):
                        if o['id'] == current_id:
                            default_ix = i
                            break
                
                obra_selecionada = st.selectbox("Obra Ativa", nomes_obras, index=default_ix)
                for o in obras:
                    if o['nome'] == obra_selecionada:
                        st.session_state['obra_ativa_id'] = o['id']
        else:
            obra_nome_atual = "Obra Selecionada"
            try:
                r = supabase.table("pcp_obras").select("nome").eq("id", st.session_state['obra_ativa_id']).single().execute()
                if r.data: obra_nome_atual = r.data['nome']
            except: pass
            htt=f"""
            <div class="sidebar-logo-container">
                <div class="sidebar-logo-text">CENTRAL DE PLANEJAMENTO</div>
                <div class="sidebar-logo-sub">{obra_nome_atual}</div>
            </div>
            """
            st.markdown(htt, unsafe_allow_html=True)

        obra_id = st.session_state['obra_ativa_id']
        config_obra = get_obra_config(supabase, obra_id)
        
        menu_options = ["Prog. Semanal", "Médio Prazo"]
        menu_icons = ["calendar-week", "calendar-range"]
        
        if config_obra.get('usa_lob'):
            menu_options.append("Longo Prazo(LOB)")
            menu_icons.append("bar-chart-line")
            
        if config_obra.get('usa_pull'):
            menu_options.append("Pull Planning")
            menu_icons.append("kanban")
            
        menu_options.extend(["Restrições", "Suprimentos"])
        menu_icons.extend(["exclamation-triangle", "box-seam"])
        
        if is_admin:
            menu_options.append("Configurações")
            menu_icons.append("gear")
            
        menu_options.append("Dashboard")
        menu_icons.append("bar-chart-fill")
        
        selected = option_menu(
            menu_title="Menu",
            options=menu_options,
            icons=menu_icons,
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background": "transparent"},
                "nav-link": {"color": "#aaa", "font-size": "0.9rem", "margin":"6px", "text-align": "left"},
                "nav-link-selected": {
                    "background-color": "rgba(227, 112, 38, 0.15)", 
                    "color": "#E37026", 
                    "border-left": "3px solid #E37026"
                },
                "icon": {"font-size": "1.1rem"}
            }

        )
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Relatorios")
        
        data_ref_relatorio = st.sidebar.date_input("Escolha a semana", datetime.now())
        start_week_rel = data_ref_relatorio - timedelta(days=data_ref_relatorio.weekday())
        data_rel_str = start_week_rel.strftime('%Y-%m-%d')
        st.sidebar.info(f"Semana selecionada: {data_rel_str}")
        
        if st.sidebar.button("Preparar Relatorio PDF", use_container_width=True):
            with st.spinner("Analisando dados e desenhando graficos..."):
                st.session_state['pdf_file_data'] = gerar_pdf_semanal(data_rel_str)
                st.session_state['pdf_data_selecionada'] = data_rel_str

        if 'pdf_file_data' in st.session_state and st.session_state.get('pdf_data_selecionada') == data_rel_str:
            st.sidebar.download_button(
                label="Baixar Arquivo PDF",
                data=st.session_state['pdf_file_data'],
                file_name=f"relatorio_obras_{data_rel_str}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        
        st.markdown("---")
        if st.button("Sair", use_container_width=True):
            logout()

    if obra_id:
        if selected == "Prog. Semanal":
            from pages_app import programacao_semanal
            programacao_semanal.app(obra_id)

        elif selected == "Médio Prazo":
            from pages_app import medio_prazo
            medio_prazo.app(obra_id)

        elif selected == "Longo Prazo(LOB)":
            from pages_app import lob
            lob.app(obra_id)

        elif selected == "Pull Planning":
            from pages_app import pull_planning
            pull_planning.app(obra_id)
            
        elif selected == "Restrições":
            from pages_app import restricoes
            restricoes.app(obra_id)

        elif selected == "Suprimentos":
            from pages_app import suprimentos
            suprimentos.app(obra_id)
            
        elif selected == "Configurações":
            from pages_app import configuracoes
            configuracoes.app(obra_id)

        elif selected == "Dashboard":
            from pages_app import dashboard
            dashboard.app(obra_id)
    else:
        st.info("Nenhuma obra cadastrada ou selecionada.")
