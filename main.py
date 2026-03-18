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
    from datetime import datetime, timedelta

    def s(txt):
        if txt is None:
            return ""
        return str(txt).replace('•', '-').replace('–', '-').replace('—', '-').replace('“', '"').replace('”', '"').encode('latin-1', 'replace').decode('latin-1')

    class PDFReport(FPDF):
        def footer(self):
            _ = self.set_y(-15)
            _ = self.set_font('Arial', 'I', 8)
            _ = self.set_text_color(150, 150, 150)
            _ = self.cell(0, 10, s(f'Pagina {self.page_no()}'), 0, 0, 'C')

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

    status_resolvidos = ['removida', 'resolvida', 'concluida', 'concluído']

    for r in dados_rest:
        obra_nome = mapa_obras.get(r.get('obra_id'), "Outros")
        if obra_nome not in restricoes_por_obra:
            restricoes_por_obra[obra_nome] = {'lista': [], 'ativas': 0, 'removidas': 0}
        
        restricoes_por_obra[obra_nome]['lista'].append(r)
        
        st = str(r.get('status', '')).strip().lower()
        if st in status_resolvidos:
            restricoes_por_obra[obra_nome]['removidas'] += 1
        else:
            restricoes_por_obra[obra_nome]['ativas'] += 1

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
    
    metricas_obras = {}
    for nome in nomes_obras:
        tot_atv = dados_agrupados[nome]["atividades_totais"]
        pts = dados_agrupados[nome]["pontos_ppc"]
        d_prog = dados_agrupados[nome]["dias_prog"]
        d_exec = dados_agrupados[nome]["dias_exec"]

        ppc = (pts / tot_atv * 100) if tot_atv > 0 else 0.0
        pap = (d_exec / d_prog * 100) if d_prog > 0 else 0.0
        
        rest_removidas = restricoes_por_obra.get(nome, {}).get('removidas', 0)
        rest_ativas = restricoes_por_obra.get(nome, {}).get('ativas', 0)
        total_rest = rest_removidas + rest_ativas
        irr = (rest_removidas / total_rest * 100) if total_rest > 0 else 0.0
        
        status_txt = "Dentro do planejado" if ppc >= 80 else ("Atencao" if ppc >= 60 else "Abaixo do esperado")
        
        metricas_obras[nome] = {
            "PPC": ppc, "PAP": pap, "IRR": irr, 
            "removidas": rest_removidas, "total_rest": total_rest,
            "status": status_txt
        }

    try:
        data_obj = datetime.strptime(data_ref_str, "%Y-%m-%d")
        data_fim_obj = data_obj + timedelta(days=4)
        legenda_semana = f"Semana: {data_obj.strftime('%d/%m/%Y')} a {data_fim_obj.strftime('%d/%m/%Y')}"
    except:
        legenda_semana = f"Semana: {data_ref_str}"

    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['text.color'] = '#374151'
    
    fig = plt.figure(figsize=(14, 9.5))
    _ = fig.patch.set_facecolor('#ffffff')
    
    ax1 = plt.subplot2grid((2, 2), (0, 0))
    ax2 = plt.subplot2grid((2, 2), (0, 1))
    ax3 = plt.subplot2grid((2, 2), (1, 0))
    ax4 = plt.subplot2grid((2, 2), (1, 1))

    x = np.arange(len(nomes_obras))
    width = 0.45 
    
    def clean_ax(ax):
        _ = ax.spines['top'].set_visible(False)
        _ = ax.spines['right'].set_visible(False)
        _ = ax.spines['left'].set_visible(False)
        _ = ax.spines['bottom'].set_color('#D1D5DB')
        _ = ax.tick_params(axis='y', length=0)

    _ = ax1.grid(axis='y', linestyle='-', alpha=0.3, color='#D1D5DB')
    ppcs = [metricas_obras[n]["PPC"] for n in nomes_obras]
    rects1 = ax1.bar(x, ppcs, width, color='#E37026', zorder=3)
    _ = ax1.axhline(y=80, color='#E37026', linestyle='-', linewidth=1.5, label='META: 80%', zorder=4, alpha=0.7)
    
    _ = ax1.set_title('PPC(%) por OBRAS e SEMANAS', fontweight='bold', color='#111827', fontsize=12, pad=10)
    _ = ax1.set_xticks(x)
    _ = ax1.set_xticklabels([n[:15] for n in nomes_obras], fontweight='bold', rotation=45, ha='right', fontsize=9)
    _ = ax1.set_ylim(0, 115)
    clean_ax(ax1)
    _ = ax1.legend(loc='upper right', frameon=False, fontsize=9)
    for rect in rects1:
        height = rect.get_height()
        _ = ax1.text(rect.get_x() + rect.get_width() / 2, height + 2, f'{height:.0f}%', ha='center', va='bottom', fontweight='bold', fontsize=9)

    _ = ax2.grid(axis='y', linestyle='-', alpha=0.3, color='#D1D5DB')
    paps = [metricas_obras[n]["PAP"] for n in nomes_obras]
    rects2 = ax2.bar(x, paps, width, color='#374151', zorder=3)
    _ = ax2.axhline(y=80, color='#374151', linestyle='-', linewidth=1.5, label='META: 80%', zorder=4, alpha=0.7)
    _ = ax2.set_title('MEDIO PRAZO/PAP (%) por Obra', fontweight='bold', color='#111827', fontsize=12, pad=10)
    _ = ax2.set_xticks(x)
    _ = ax2.set_xticklabels([n[:15] for n in nomes_obras], fontweight='bold', rotation=45, ha='right', fontsize=9)
    _ = ax2.set_ylim(0, 115)
    clean_ax(ax2)
    for rect in rects2:
        height = rect.get_height()
        _ = ax2.text(rect.get_x() + rect.get_width() / 2, height + 2, f'{height:.0f}%', ha='center', va='bottom', fontweight='bold', fontsize=9)

    if contagem_causas:
        causas_ord = sorted(contagem_causas.items(), key=lambda x: x[1], reverse=True)
        labels = [c[0] for c in causas_ord]
        sizes = [c[1] for c in causas_ord]
        cores_donut = ['#4A235A', '#0E6655', '#E37026', '#B03A2E', '#D0D3D4', '#117A65', '#9A7D0A', '#17202A'][:len(labels)]
        
        wedges, texts, autotexts = ax3.pie(
            sizes, autopct='%1.1f%%', pctdistance=0.85, 
            colors=cores_donut, startangle=90, 
            textprops={'fontsize': 8, 'weight': 'bold', 'color': 'white'}
        )
        centre_circle = plt.Circle((0,0),0.65,fc='white')
        _ = ax3.add_artist(centre_circle)
        
        _ = ax3.legend(wedges, labels, title="Motivos", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), frameon=False, fontsize=8)
        _ = ax3.set_title('LISTA DE PROBLEMAS', fontweight='bold', color='#111827', fontsize=12)
    else:
        _ = ax3.text(0.5, 0.5, "Nenhum problema registrado", ha='center', va='center', fontweight='bold', color='#9CA3AF')
        _ = ax3.axis('off')

    _ = ax4.grid(axis='y', linestyle='-', alpha=0.3, color='#D1D5DB')
    obras_rest = [n for n in nomes_obras if metricas_obras[n]['total_rest'] > 0]
    
    if obras_rest:
        x_rest = np.arange(len(obras_rest))
        vol_ativas = [metricas_obras[o]['total_rest'] - metricas_obras[o]['removidas'] for o in obras_rest]
        vol_removidas = [metricas_obras[o]['removidas'] for o in obras_rest]
        
        rects_ativas = ax4.bar(x_rest, vol_ativas, color='#E37026', width=0.45, zorder=3, label='Adicionadas/Ativas')
        rects_remov = ax4.bar(x_rest, vol_removidas, bottom=vol_ativas, color='#374151', width=0.45, zorder=3, label='Removidas')
        
        _ = ax4.set_xticks(x_rest)
        _ = ax4.set_xticklabels([o[:15] for o in obras_rest], fontweight='bold', rotation=45, ha='right', fontsize=9)
        _ = ax4.set_title('Restricoes por Obra', fontweight='bold', color='#111827', fontsize=12, pad=10)
        _ = ax4.legend(loc='upper right', frameon=False, fontsize=9)
        clean_ax(ax4)
    else:
        _ = ax4.text(0.5, 0.5, "Nenhuma restricao registrada", ha='center', va='center', fontweight='bold', color='#9CA3AF')
        clean_ax(ax4)

    _ = plt.tight_layout(pad=3.0)
    tmp_dash = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    _ = plt.savefig(tmp_dash.name, dpi=300, bbox_inches='tight')
    _ = plt.close(fig)

    pdf = PDFReport()
    _ = pdf.set_margins(15, 15, 15)
    _ = pdf.add_page()

    _ = pdf.set_font("Arial", size=18, style='B')
    _ = pdf.set_text_color(31, 41, 55)
    _ = pdf.cell(0, 8, txt=s("Relatorio de Acompanhamento Semanal de Obras"), ln=True, align='L')
    
    _ = pdf.set_font("Arial", size=11)
    _ = pdf.set_text_color(107, 114, 128)
    _ = pdf.cell(0, 6, txt=s(f"- {legenda_semana}"), ln=True, align='L')
    _ = pdf.cell(0, 6, txt=s("Responsaveis pelo relatorio: Central de Planejamento"), ln=True, align='L')
    _ = pdf.ln(5)

    _ = pdf.set_font("Arial", size=12, style='B')
    _ = pdf.set_text_color(227, 112, 38)
    _ = pdf.cell(0, 8, txt=s("1. Indicadores Semanais"), ln=True)
    
    _ = pdf.set_fill_color(55, 65, 81)
    _ = pdf.set_text_color(255, 255, 255)
    _ = pdf.set_draw_color(209, 213, 219)
    _ = pdf.set_font("Arial", size=9, style='B')
    
    larguras_ind = [10, 50, 25, 30, 25, 40]
    
    _ = pdf.cell(larguras_ind[0], 8, txt=s("Item"), border=1, fill=True, align='C')
    _ = pdf.cell(larguras_ind[1], 8, txt=s("Obra"), border=1, fill=True)
    _ = pdf.cell(larguras_ind[2], 8, txt=s("PPC (%)"), border=1, fill=True, align='C')
    _ = pdf.cell(larguras_ind[3], 8, txt=s("Medio Prazo (%)"), border=1, fill=True, align='C')
    _ = pdf.cell(larguras_ind[4], 8, txt=s("IRR (%)"), border=1, fill=True, align='C')
    _ = pdf.cell(larguras_ind[5], 8, txt=s("Status"), border=1, fill=True, ln=True, align='C')

    _ = pdf.set_text_color(75, 85, 99)
    _ = pdf.set_font("Arial", size=9)
    
    zebra = False
    for i, nome in enumerate(nomes_obras):
        if zebra:
            _ = pdf.set_fill_color(249, 250, 251)
        else:
            _ = pdf.set_fill_color(255, 255, 255)
        zebra = not zebra
        
        m = metricas_obras[nome]
        _ = pdf.cell(larguras_ind[0], 7, txt=s(str(i+1)), border=1, fill=True, align='C')
        _ = pdf.cell(larguras_ind[1], 7, txt=s(f" {nome[:30]}"), border=1, fill=True)
        _ = pdf.cell(larguras_ind[2], 7, txt=s(f"{m['PPC']:.2f}%"), border=1, fill=True, align='C')
        _ = pdf.cell(larguras_ind[3], 7, txt=s(f"{m['PAP']:.2f}%"), border=1, fill=True, align='C')
        _ = pdf.cell(larguras_ind[4], 7, txt=s(f"{m['IRR']:.2f}%"), border=1, fill=True, align='C')
        _ = pdf.cell(larguras_ind[5], 7, txt=s(m['status']), border=1, fill=True, align='C', ln=True)

    _ = pdf.ln(5)

    _ = pdf.image(tmp_dash.name, x=10, y=pdf.get_y(), w=190)
    try:
        os.remove(tmp_dash.name)
    except:
        pass

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

    for i, obra in enumerate(nomes_obras):
        _ = pdf.add_page()
        
        if i == 0:
            _ = pdf.set_font("Arial", size=14, style='B')
            _ = pdf.set_text_color(31, 41, 55)
            _ = pdf.cell(0, 10, txt=s("2. Evolucao Fisica por Obra"), ln=True)
            _ = pdf.ln(2)

        _ = pdf.set_fill_color(243, 244, 246)
        _ = pdf.set_draw_color(227, 112, 38)
        _ = pdf.set_line_width(0.5)
        _ = pdf.rect(15, pdf.get_y(), 180, 10, 'DF')
        
        _ = pdf.set_font("Arial", size=12, style='B')
        _ = pdf.set_text_color(31, 41, 55)
        _ = pdf.set_xy(18, pdf.get_y() + 2)
        _ = pdf.cell(0, 6, txt=s(f"{obra.upper()}"), ln=True, align='L', border=0)
        _ = pdf.set_line_width(0.2)
        _ = pdf.ln(6)

        m = metricas_obras[obra]
        _ = pdf.set_font("Arial", size=10)
        _ = pdf.set_text_color(55, 65, 81)
        
        _ = pdf.cell(0, 6, txt=s(f"- PPC Semanal: {m['PPC']:.2f}%"), ln=True)
        _ = pdf.cell(0, 6, txt=s(f"- Medio Prazo (PAP): {m['PAP']:.2f}%"), ln=True)
        _ = pdf.cell(0, 6, txt=s(f"- Restricoes - IRR: {m['IRR']:.2f}% ({m['removidas']} restricoes removidas de {m['total_rest']} ativas/adicionadas)"), ln=True)
        _ = pdf.ln(4)

        _ = pdf.set_font("Arial", size=10, style='B')
        _ = pdf.set_text_color(227, 112, 38)
        _ = pdf.cell(0, 6, txt=s("Detalhamento da Programacao"), ln=True)
        _ = pdf.ln(1)
        
        _ = pdf.set_fill_color(55, 65, 81)
        _ = pdf.set_text_color(255, 255, 255)
        _ = pdf.set_draw_color(55, 65, 81)
        _ = pdf.set_font("Arial", size=9, style='B')
        
        # Novas larguras da tabela: Atividade, Detalhe, Status, Motivo/Problema
        larguras_prog = [45, 65, 25, 45]
        _ = pdf.cell(larguras_prog[0], 8, txt=s(" Atividade"), border=1, fill=True)
        _ = pdf.cell(larguras_prog[1], 8, txt=s(" Detalhe"), border=1, fill=True)
        _ = pdf.cell(larguras_prog[2], 8, txt=s("Status"), border=1, fill=True, align='C')
        _ = pdf.cell(larguras_prog[3], 8, txt=s(" Motivo/Problema"), border=1, fill=True, ln=True)

        _ = pdf.set_text_color(75, 85, 99)
        _ = pdf.set_font("Arial", size=8)
        _ = pdf.set_draw_color(209, 213, 219)
        zebra_prog = False
        
        for atv in dados_agrupados[obra]["lista_atividades"]:
            # Só exibe o motivo se a tarefa não foi concluída
            motivo_txt = s(atv.get('causa', '')) if atv.get('status') in ['Nao Concluido', 'Em Andamento'] else ''
            
            textos_linha = [
                s(atv.get('atividade', '')), 
                s(atv.get('detalhe', '')), 
                s(atv.get('status', '')), 
                motivo_txt
            ]
            
            h_linha = calcular_altura_linha(pdf, textos_linha, larguras_prog)
            
            if pdf.get_y() + h_linha > 270:
                _ = pdf.add_page()

            x_start, y_start = pdf.get_x(), pdf.get_y()
            _ = pdf.set_fill_color(249, 250, 251) if zebra_prog else pdf.set_fill_color(255, 255, 255)
            zebra_prog = not zebra_prog
            
            for i, txt in enumerate(textos_linha):
                _ = pdf.rect(x_start, y_start, larguras_prog[i], h_linha, 'DF')
                _ = pdf.set_xy(x_start + 1, y_start + 2)
                _ = pdf.multi_cell(larguras_prog[i] - 2, 5, txt, border=0, align='C' if i == 2 else 'L')
                x_start += larguras_prog[i]
            _ = pdf.set_xy(15, y_start + h_linha)
            
        _ = pdf.ln(8)

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
