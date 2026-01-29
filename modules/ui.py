import streamlit as st

def inject_css():
    try:
        with open("assets/style.css") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except:
        pass

def header(titulo, subtitulo=None):
    st.markdown(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin-bottom: 0;">{titulo}</h1>
            {f'<p style="color: #888; margin-top: 5px;">{subtitulo}</p>' if subtitulo else ''}
        </div>
    """, unsafe_allow_html=True)

def metric_card(titulo, valor, delta=None, color="#FFFFFF"):
    delta_html = ""
    if delta:
        cor_delta = "#4ADE80" if "+" in delta or "↑" in delta else "#EF4444"
        delta_html = f'<span style="color: {cor_delta}; font-size: 0.9rem; margin-left: 10px;">{delta}</span>'

    st.markdown(f"""
        <div class="glass-card">
            <h4 style="margin: 0; color: #aaa; font-size: 0.9rem; text-transform: uppercase;">{titulo}</h4>
            <div style="display: flex; align-items: baseline; margin-top: 5px;">
                <h2 style="margin: 0; font-size: 2rem; color: #fff;">{valor}</h2>
            </div>
            <div style="height: 4px; width: 100%; background: rgba(255,255,255,0.1); margin-top: 10px; border-radius: 2px;">
                <div style="height: 100%; width: 100%; background: {color}; border-radius: 2px;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def status_badge(status):
    cor = "#888"
    bg = "rgba(136, 136, 136, 0.2)"
    
    s = str(status).upper()
    if s in ["CONCLUÍDO", "OK", "EXECUTADO"]:
        cor = "#4ADE80"
        bg = "rgba(74, 222, 128, 0.2)"
    elif s in ["ATRASADO", "CRÍTICO", "BLOQUEADO"]:
        cor = "#EF4444"
        bg = "rgba(239, 68, 68, 0.2)"
    elif s in ["EM ANDAMENTO", "INICIADO"]:
        cor = "#E37026"
        bg = "rgba(227, 112, 38, 0.2)"
    
    return f"""
        <span style="
            background-color: {bg};
            color: {cor};
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid {cor};
        ">{status}</span>
    """

def table_header(colunas):
    cols_html = "".join([f'<th style="text-align: left;">{c}</th>' for c in colunas])
    return f"""
    <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
        <thead>
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: #888;">
                {cols_html}
            </tr>
        </thead>
        <tbody>
    """