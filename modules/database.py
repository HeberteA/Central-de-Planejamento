import streamlit as st
from supabase import create_client, Client
import pandas as pd

@st.cache_resource
def get_db_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def check_credentials(username, password):
    supabase = get_db_client()
    try:
        response = supabase.table("pcp_users").select("*").eq("username", username).execute()
        if response.data:
            user = response.data[0]
            if user['password'] == password:
                return user
        return None
    except:
        return None

def get_obras_list(role, user_obra_id=None):
    supabase = get_db_client()
    query = supabase.table("pcp_obras").select("id, nome")
    
    if role != 'admin' and user_obra_id:
        query = query.eq("id", user_obra_id)
        
    response = query.execute()
    return pd.DataFrame(response.data)

def fetch_indicadores_historicos(obra_id):
    supabase = get_db_client()
    response = supabase.table("pcp_historico_indicadores")\
        .select("*")\
        .eq("obra_id", obra_id)\
        .order("data_referencia", desc=False)\
        .execute()
    
    return pd.DataFrame(response.data)