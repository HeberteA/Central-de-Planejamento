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
    import matplotlib.pyplot as plt
    import tempfile
    import os
    from fpdf import FPDF
    from datetime import datetime

    class PDFReport(FPDF):
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    supabase = database.get_db_client()

    resp_obras = supabase.table("pcp_obras").select("id, nome").execute()
    mapa_obras = {o['id']: o['nome'] for o in resp_obras.data} if resp_obras.data else {}

    resp_prog = supabase.table("pcp_programacao_semanal").select("*").eq("data_inicio_semana", data_ref_str).execute()
    dados_prog = resp_prog.data if resp_prog.data else []

    try:
        resp_rest = supabase.table("pcp_restricoes").select("*").execute()
        dados_rest = resp_rest.data if resp_rest.data else []
    except:
        dados_rest = []

    dados_agrupados = {}
    contagem_causas = {}
    restricoes_por_obra = {}

    for r in dados_rest:
        obra_nome = mapa_obras.get(r.get('obra_id'), "Outros")
        if obra_nome not in restricoes_por_obra:
            restricoes_por_obra[obra_nome] = []
        restricoes_por_obra[obra_nome].append(r)

    for d in dados_prog:
        obra_nome = mapa_obras.get(d.get('obra_id'), "Outros")

        if obra_nome not in dados_agrupados:
            dados_agrupados[obra_nome] = {
                "atividades_totais": 0, "pontos_ppc": 0.0, "dias_prog": 0, "dias_exec": 0, "lista_atividades": []
            }

        dados_agrupados[obra_nome]["atividades_totais"] += 1
        dados_agrupados[obra_nome]["lista_atividades"].append(d)

        status_atual = d.get('status', 'A Iniciar')

        if status_atual == 'Concluido':
            dados_agrupados[obra_nome]["pontos_ppc"] += 1.0
        elif status_atual == 'Em Andamento':
            try:
                val_perc = float(d.get('percentual', 0) or 0.0)
            except:
                val_perc = 0.0
            dados_agrupados[obra_nome]["pontos_ppc"] += (val_perc / 100.0)

        for dia in ['seg', 'ter', 'qua', 'qui', 'sex']:
            if d.get(f'rec_{dia}') and str(d.get(f'rec_{dia}')).strip() != '':
                dados_agrupados[obra_nome]["dias_prog"] += 1
                if d.get(f'feito_{dia}') is True:
                    dados_agrupados[obra_nome]["dias_exec"] += 1

        if status_atual in ['Nao Concluido', 'Em Andamento'] and d.get('causa'):
            causa = d.get('causa')
            contagem_causas[causa] = contagem_causas.get(causa, 0) + 1

    nomes_obras = list(dados_agrupados.keys())
    ppc_obras, pap_obras = [], []

    for nome in nomes_obras:
        tot_atv = dados_agrupados[nome]["atividades_totais"]
        pts = dados_agrupados[nome]["pontos_ppc"]
        d_prog = dados_agrupados[nome]["dias_prog"]
        d_exec = dados_agrupados[nome]["dias_exec"]

        ppc_obras.append((pts / tot_atv * 100) if tot_atv > 0 else 0.0)
        pap_obras.append((d_exec / d_prog * 100) if d_prog > 0 else 0.0)

    try:
        data_obj = datetime.strptime(data_ref_str, "%Y-%m-%d")
        legenda_semana = f"Semana: {data_obj.strftime('%d/%m/%Y')}"
    except:
        legenda_semana = f"Semana: {data_ref_str}"

    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['text.color'] = '#374151'
    plt.rcParams['axes.labelcolor'] = '#374151'
    plt.rcParams['xtick.color'] = '#374151'
    plt.rcParams['ytick.color'] = '#374151'
    
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor('#ffffff')

    x = np.arange(len(nomes_obras))
    width = 0.45 
    
    def clean_ax(ax):
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color('#D1D5DB')
        ax.tick_params(axis='y', length=0)

    ax1 = axs[0, 0]
    ax1.grid(axis='y', linestyle='-', alpha=0.3, color='#D1D5DB')
    rects1 = ax1.bar(x, ppc_obras, width, label=legenda_semana, color='#E37026', zorder=3)
    ax1.set_title('PPC por Obra (%)', fontweight='bold', color='#111827', fontsize=14, pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels([n[:15] for n in nomes_obras], fontweight='bold', rotation=45, ha='right')
    ax1.set_ylim(0, 115)
    clean_ax(ax1)
    ax1.legend(loc='upper right', frameon=False)
    
    for rect in rects1:
        height = rect.get_height()
        ax1.text(rect.get_x() + rect.get_width() / 2, height + 2, f'{height:.0f}%', ha='center', va='bottom', fontweight='bold', fontsize=10)

    ax2 = axs[0, 1]
    ax2.grid(axis='y', linestyle='-', alpha=0.3, color='#D1D5DB')
    rects2 = ax2.bar(x, pap_obras, width, label=legenda_semana, color='#374151', zorder=3)
    ax2.set_title('PAP por Obra (%)', fontweight='bold', color='#111827', fontsize=14, pad=15)
    ax2.set_xticks(x)
    ax2.set_xticklabels([n[:15] for n in nomes_obras], fontweight='bold', rotation=45, ha='right')
    ax2.set_ylim(0, 115)
    clean_ax(ax2)
    ax2.legend(loc='upper right', frameon=False)
    
    for rect in rects2:
        height = rect.get_height()
        ax2.text(rect.get_x() + rect.get_width() / 2, height + 2, f'{height:.0f}%', ha='center', va='bottom', fontweight='bold', fontsize=10)

    ax3 = axs[1, 0]
    ax3.grid(axis='x', linestyle='-', alpha=0.3, color='#D1D5DB')
    if contagem_causas:
        causas_ord = sorted(contagem_causas.items(), key=lambda x: x[1], reverse=False)[-5:]
        y_pos = np.arange(len(causas_ord))
        ax3.barh(y_pos, [c[1] for c in causas_ord], color='#E37026', zorder=3, height=0.5)
        ax3.set_yticks(y_pos)
        ax3.set_yticklabels([c[0][:25] + "..." if len(c[0])>25 else c[0] for c in causas_ord], fontweight='bold')
        ax3.set_title('Top Motivos de Não Conclusão', fontweight='bold', color='#111827', fontsize=14, pad=15)
        for i, v in enumerate([c[1] for c in causas_ord]):
            ax3.text(v + 0.1, i, str(v), va='center', fontweight='bold')
    else:
        ax3.text(0.5, 0.5, "Nenhum problema registrado", ha='center', va='center', fontweight='bold', color='#9CA3AF')
    clean_ax(ax3)

    ax4 = axs[1, 1]
    ax4.grid(axis='y', linestyle='-', alpha=0.3, color='#D1D5DB')
    obras_rest = list(restricoes_por_obra.keys())
    vol_rest = [len(restricoes_por_obra[o]) for o in obras_rest]
    
    if vol_rest and sum(vol_rest) > 0:
        x_rest = np.arange(len(obras_rest))
        rects4 = ax4.bar(x_rest, vol_rest, color='#374151', width=0.45, zorder=3)
        ax4.set_xticks(x_rest)
        ax4.set_xticklabels([o[:15] for o in obras_rest], fontweight='bold', rotation=45, ha='right')
        ax4.set_title('Volume de Restrições Ativas', fontweight='bold', color='#111827', fontsize=14, pad=15)
        for rect in rects4:
            height = rect.get_height()
            ax4.text(rect.get_x() + rect.get_width() / 2, height + 0.2, str(height), ha='center', va='bottom', fontweight='bold')
    else:
        ax4.text(0.5, 0.5, "Nenhuma restrição ativa", ha='center', va='center', fontweight='bold', color='#9CA3AF')
    clean_ax(ax4)

    plt.tight_layout(pad=4.0)
    tmp_dash = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    plt.savefig(tmp_dash.name, dpi=300, bbox_inches='tight')
    plt.close(fig)

    pdf = PDFReport()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    try:
        pdf.image('assets/logo.png', x=15, y=12, w=35)
    except:
        pass
    
    pdf.set_font("Arial", size=22, style='B')
    pdf.set_text_color(31, 41, 55) 
    pdf.cell(0, 12, txt="RELATÓRIO SEMANAL - LAVIE", ln=True, align='R')
    
    pdf.set_font("Arial", size=12)
    pdf.set_text_color(107, 114, 128) 
    pdf.cell(0, 6, txt=f"Central de Planejamento | Ref: {data_ref_str}", ln=True, align='R')
    
    pdf.ln(5)
    pdf.set_fill_color(227, 112, 38)
    pdf.rect(15, pdf.get_y(), 180, 1, 'F')
    pdf.ln(10)

    pdf.image(tmp_dash.name, x=10, y=pdf.get_y(), w=190)
    os.remove(tmp_dash.name)

    def calcular_altura_linha(pdf, textos, larguras):
        max_h = 0
        for i, txt in enumerate(textos):
            palavras = str(txt).split()
            linhas = 1
            largura_atual = 0
            for p in palavras:
                largura_p = pdf.get_string_width(p + " ")
                if largura_atual + largura_p > (larguras[i] - 4): 
                    linhas += 1
                    largura_atual = largura_p
                else:
                    largura_atual += largura_p
            h = max(1, linhas + str(txt).count('\n')) * 6 + 4 
            if h > max_h:
                max_h = h
        return max_h

    for obra in nomes_obras:
        pdf.add_page()
        
        pdf.set_fill_color(243, 244, 246) 
        pdf.set_draw_color(227, 112, 38) 
        pdf.set_line_width(0.5)
        pdf.rect(15, 15, 180, 12, 'DF')
        
        pdf.set_font("Arial", size=14, style='B')
        pdf.set_text_color(31, 41, 55)
        pdf.set_xy(18, 17)
        pdf.cell(0, 8, txt=f"OBRA: {obra.upper()}", ln=True, align='L', border=0)
        pdf.set_line_width(0.2) 
        pdf.ln(10)

        pdf.set_font("Arial", size=12, style='B')
        pdf.set_text_color(227, 112, 38)
        pdf.cell(0, 8, txt="1. Status da Programação Semanal", ln=True)
        pdf.ln(2)
        
        pdf.set_fill_color(55, 65, 81)
        pdf.set_text_color(255, 255, 255)
        pdf.set_draw_color(55, 65, 81)
        pdf.set_font("Arial", size=9, style='B')
        
        larguras_prog = [35, 45, 75, 25]
        
        pdf.cell(larguras_prog[0], 9, txt=" Local", border=1, fill=True)
        pdf.cell(larguras_prog[1], 9, txt=" Atividade", border=1, fill=True)
        pdf.cell(larguras_prog[2], 9, txt=" Detalhe", border=1, fill=True)
        pdf.cell(larguras_prog[3], 9, txt="Status", border=1, fill=True, ln=True, align='C')

        pdf.set_text_color(75, 85, 99)
        pdf.set_font("Arial", size=8)
        pdf.set_draw_color(209, 213, 219) 
        
        zebra_prog = False 
        
        for atv in dados_agrupados[obra]["lista_atividades"]:
            loc = str(atv.get('local', ''))
            ati = str(atv.get('atividade', ''))
            det = str(atv.get('detalhe', ''))
            sta = str(atv.get('status', ''))

            textos_linha = [loc, ati, det, sta]
            h_linha = calcular_altura_linha(pdf, textos_linha, larguras_prog)
            
            if pdf.get_y() + h_linha > 270:
                pdf.add_page()

            x_start = pdf.get_x()
            y_start = pdf.get_y()
            
            if zebra_prog:
                pdf.set_fill_color(249, 250, 251)
            else:
                pdf.set_fill_color(255, 255, 255) 
            zebra_prog = not zebra_prog
            
            for i, txt in enumerate(textos_linha):
                pdf.rect(x_start, y_start, larguras_prog[i], h_linha, 'DF')
                pdf.set_xy(x_start + 1, y_start + 2)
                alinhamento = 'C' if i == 3 else 'L'
                pdf.multi_cell(larguras_prog[i] - 2, 5, txt, border=0, align=alinhamento)
                x_start += larguras_prog[i]
            
            pdf.set_xy(15, y_start + h_linha)
            
        pdf.ln(12)

        restricoes_desta_obra = restricoes_por_obra.get(obra, [])
        if restricoes_desta_obra:
            if pdf.get_y() > 220:
                pdf.add_page()
                
            pdf.set_font("Arial", size=12, style='B')
            pdf.set_text_color(227, 112, 38)
            pdf.cell(0, 8, txt="2. Quadro de Restrições Ativas", ln=True)
            pdf.ln(2)
            
            pdf.set_fill_color(55, 65, 81)
            pdf.set_text_color(255, 255, 255)
            pdf.set_draw_color(55, 65, 81)
            pdf.set_font("Arial", size=9, style='B')
            
            larguras_rest = [75, 40, 30, 35]
            
            pdf.cell(larguras_rest[0], 9, txt=" Descrição da Restrição", border=1, fill=True)
            pdf.cell(larguras_rest[1], 9, txt=" Responsável", border=1, fill=True)
            pdf.cell(larguras_rest[2], 9, txt="Data Prev.", border=1, fill=True, align='C')
            pdf.cell(larguras_rest[3], 9, txt="Status", border=1, fill=True, ln=True, align='C')

            pdf.set_text_color(75, 85, 99)
            pdf.set_font("Arial", size=8)
            pdf.set_draw_color(209, 213, 219)
            
            zebra_rest = False
            
            for rest in restricoes_desta_obra:
                desc = str(rest.get('descricao', rest.get('restricao', '')))
                resp = str(rest.get('responsavel', ''))
                data_prev = str(rest.get('data_prevista', str(rest.get('data_limite', ''))))
                stat_rest = str(rest.get('status', ''))

                textos_rest = [desc, resp, data_prev, stat_rest]
                h_linha = calcular_altura_linha(pdf, textos_rest, larguras_rest)
                
                if pdf.get_y() + h_linha > 270:
                    pdf.add_page()

                x_start = pdf.get_x()
                y_start = pdf.get_y()
                
                if zebra_rest:
                    pdf.set_fill_color(249, 250, 251)
                else:
                    pdf.set_fill_color(255, 255, 255)
                zebra_rest = not zebra_rest
                
                for i, txt in enumerate(textos_rest):
                    pdf.rect(x_start, y_start, larguras_rest[i], h_linha, 'DF')
                    pdf.set_xy(x_start + 1, y_start + 2)
                    alinhamento = 'C' if i in [2, 3] else 'L'
                    pdf.multi_cell(larguras_rest[i] - 2, 5, txt, border=0, align=alinhamento)
                    x_start += larguras_rest[i]
                
                pdf.set_xy(15, y_start + h_linha)

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
