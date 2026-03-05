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
    import numpy as np
    
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

    dados_agrupados = {}
    contagem_causas = {}

    for d in dados_prog:
        obra_id = d.get('obra_id')
        obra_nome = mapa_obras.get(obra_id, "Outros")

        if obra_nome not in dados_agrupados:
            dados_agrupados[obra_nome] = {
                "atividades_totais": 0,
                "pontos_ppc": 0.0,
                "dias_prog": 0,
                "dias_exec": 0,
                "lista_atividades": []
            }

        dados_agrupados[obra_nome]["atividades_totais"] += 1
        dados_agrupados[obra_nome]["lista_atividades"].append(d)

        status_atual = d.get('status')
        if status_atual == 'Concluido':
            dados_agrupados[obra_nome]["pontos_ppc"] += 1.0
        elif status_atual == 'Em Andamento':
            perc = d.get('percentual', 0)
            try:
                val_perc = float(perc) if perc else 0.0
            except:
                val_perc = 0.0
            dados_agrupados[obra_nome]["pontos_ppc"] += (val_perc / 100.0)

        for dia in ['seg', 'ter', 'qua', 'qui', 'sex']:
            rec_val = d.get(f'rec_{dia}')
            feito_val = d.get(f'feito_{dia}')
            if rec_val and str(rec_val).strip() != '':
                dados_agrupados[obra_nome]["dias_prog"] += 1
                if feito_val is True:
                    dados_agrupados[obra_nome]["dias_exec"] += 1

        if status_atual in ['Nao Concluido', 'Em Andamento']:
            causa = d.get('causa')
            if causa:
                contagem_causas[causa] = contagem_causas.get(causa, 0) + 1

    nomes_obras = list(dados_agrupados.keys())
    ppc_obras = []
    pap_obras = []

    for nome in nomes_obras:
        tot_atv = dados_agrupados[nome]["atividades_totais"]
        pts = dados_agrupados[nome]["pontos_ppc"]
        d_prog = dados_agrupados[nome]["dias_prog"]
        d_exec = dados_agrupados[nome]["dias_exec"]

        val_ppc = (pts / tot_atv * 100) if tot_atv > 0 else 0.0
        val_pap = (d_exec / d_prog * 100) if d_prog > 0 else 0.0

        ppc_obras.append(val_ppc)
        pap_obras.append(val_pap)

    x = np.arange(len(nomes_obras))
    width = 0.35

    fig1, ax1 = plt.subplots(figsize=(10, 5))
    rects1 = ax1.bar(x - width/2, ppc_obras, width, label='PPC', color='#E37026')
    rects2 = ax1.bar(x + width/2, pap_obras, width, label='PAP', color='#1E3A8A')

    ax1.set_ylabel('Porcentagem (%)', fontweight='bold', color='#333333')
    ax1.set_title('PPC e PAP por Obra', fontweight='bold', color='#1E3A8A', fontsize=14, pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels([n[:15] for n in nomes_obras], rotation=0, ha='center', fontweight='bold')
    ax1.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False)
    ax1.set_ylim(0, 115)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax1.annotate(f'{height:.0f}%',
                         xy=(rect.get_x() + rect.get_width() / 2, height),
                         xytext=(0, 3),
                         textcoords="offset points",
                         ha='center', va='bottom', fontweight='bold', fontsize=9, color='#333333')

    autolabel(rects1)
    autolabel(rects2)

    plt.tight_layout()
    tmp1 = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    plt.savefig(tmp1.name, dpi=300, bbox_inches='tight')
    plt.close(fig1)

    fig2, ax2 = plt.subplots(figsize=(10, 4))
    if contagem_causas:
        causas_ordenadas = sorted(contagem_causas.items(), key=lambda x: x[1], reverse=False)[-7:]
        labels = [c[0][:30] for c in causas_ordenadas]
        valores = [c[1] for c in causas_ordenadas]
        ax2.barh(labels, valores, color='#E37026', height=0.6)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.set_xlabel('Quantidade de Ocorrencias (Top 7)', fontweight='bold', color='#333333')
        ax2.set_title('Principais Restricoes Gerais', fontweight='bold', color='#1E3A8A', fontsize=14, pad=15)

        for i, v in enumerate(valores):
            ax2.text(v + 0.1, i, str(v), ha='left', va='center', fontweight='bold', color='#333333')
    else:
        ax2.text(0.5, 0.5, "Nenhum problema registrado", ha='center', va='center', fontweight='bold')
        ax2.axis('off')

    plt.tight_layout()
    tmp2 = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    plt.savefig(tmp2.name, dpi=300, bbox_inches='tight')
    plt.close(fig2)

    pdf = FPDF()
    pdf.add_page()

    try:
        pdf.image('logo.png', x=10, y=8, w=30)
    except:
        pass

    pdf.set_font("Arial", size=16, style='B')
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 10, txt="Relatorio Semanal Global - Lavie", ln=True, align='C')

    pdf.set_font("Arial", size=12)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, txt=f"Semana de Referencia: {data_ref_str}", ln=True, align='C')
    pdf.ln(10)

    pdf.image(tmp1.name, x=10, y=35, w=190)
    pdf.ln(105)
    pdf.image(tmp2.name, x=10, y=145, w=190)

    os.remove(tmp1.name)
    os.remove(tmp2.name)

    pdf.add_page()
    pdf.set_font("Arial", size=14, style='B')
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 10, txt="Detalhamento das Atividades", ln=True, align='C')
    pdf.ln(5)

    for obra, dados_obra in dados_agrupados.items():
        atividades = dados_obra["lista_atividades"]

        pdf.set_font("Arial", size=12, style='B')
        pdf.set_text_color(227, 112, 38)
        pdf.cell(0, 10, txt=f"Obra: {obra}", ln=True, align='L')

        pdf.set_fill_color(30, 58, 138)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", size=9, style='B')
        pdf.cell(40, 8, txt="Local", border=1, fill=True)
        pdf.cell(60, 8, txt="Atividade", border=1, fill=True)
        pdf.cell(60, 8, txt="Detalhe", border=1, fill=True)
        pdf.cell(30, 8, txt="Status", border=1, fill=True, ln=True, align='C')

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", size=8)
        for atv in atividades:
            local = str(atv.get('local', ''))[:25]
            atividade = str(atv.get('atividade', ''))[:40]
            detalhe = str(atv.get('detalhe', ''))[:40]
            status = str(atv.get('status', ''))[:15]

            pdf.cell(40, 7, txt=local, border=1)
            pdf.cell(60, 7, txt=atividade, border=1)
            pdf.cell(60, 7, txt=detalhe, border=1)
            pdf.cell(30, 7, txt=status, border=1, ln=True, align='C')
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
