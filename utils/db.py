import streamlit as st
from supabase import create_client

@st.cache_resource
def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def fetch(table, order=None, limit=10000):
    q = get_client().table(table).select("*")
    if order:
        q = q.order(order)
    if limit:
        q = q.limit(limit)
    return q.execute().data

def insert(table, payload):
    return get_client().table(table).insert(payload).execute().data

def upsert(table, payload, on_conflict=None):
    q = get_client().table(table).upsert(payload, on_conflict=on_conflict) if on_conflict else get_client().table(table).upsert(payload)
    return q.execute().data
