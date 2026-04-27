import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import random
import string
import os
import plotly.express as px
import plotly.graph_objects as go
import base64
from PIL import Image
import io

# ==========================================
# 1. CONFIGURATION & STYLES (COMPACT UI)
# ==========================================
st.set_page_config(page_title="Auditoría y Visita Técnica", layout="wide", page_icon="🛡️")

st.markdown("""
    <style>
    html, body, [class*="st-"] { font-size: 14px !important; }
    h1 { font-size: 1.7rem !important; padding-bottom: 0.2rem !important; margin-bottom: 0.2rem !important; }
    h2 { font-size: 1.4rem !important; padding-bottom: 0.2rem !important; }
    h3 { font-size: 1.15rem !important; padding-bottom: 0.2rem !important; }
    .metric-card {background-color: #ffffff; padding: 10px; border-radius: 8px; border: 1px solid #dee2e6; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
    .pass-text {color: #28a745; font-weight: bold;}
    .fail-text {color: #dc3545; font-weight: bold;}
    .cat-badge {padding: 2px 6px; border-radius: 8px; font-size: 0.7rem; font-weight: bold; background-color: #e9ecef; color: #1e2b3c; border: 1px solid #ccc; display: inline-block;}
    hr.slim {margin: 8px 0; border: 0; border-top: 1px solid #eee;}
    div[data-testid="stHorizontalBlock"] { gap: 0.5rem; }
    div[data-testid="stForm"] { padding: 1rem !important; }
    div[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
    @media (max-width: 480px) {
        html, body, [class*="st-"] { font-size: 13px !important; }
        h1 { font-size: 1.5rem !important; }
        .stButton button { padding: 0.2rem 0.5rem !important; }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CUSTOM COMPONENT: FAST MOBILE CAMERA (BIDIRECTIONAL)
# ==========================================
_fast_camera_html = """
<!DOCTYPE html>
<html>
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/streamlit-component-lib@1.3.0/dist/streamlit.js"></script>
  </head>
  <body>
    <b style="font-family: sans-serif; color: #333;">Test Nativo de Cámara:</b><br><br>
    <input type="file" accept="image/*" id="cam" style="font-size: 16px;">
    
    <script>
      function init() { Streamlit.setFrameHeight(100); }
      document.getElementById('cam').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        document.body.innerHTML = "<b style='font-family: sans-serif; color: #ffc107;'>⏳ Comprimiendo en el teléfono...</b>";
        
        const reader = new FileReader();
        reader.onload = function(event) {
            const img = new Image();
            img.onload = function() {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const MAX = 1080;
                let w = img.width; let h = img.height;
                if (w > h) { if (w > MAX) { h *= MAX / w; w = MAX; } }
                else { if (h > MAX) { w *= MAX / h; h = MAX; } }
                canvas.width = w; canvas.height = h;
                ctx.drawImage(img, 0, 0, w, h);
                const b64 = canvas.toDataURL('image/jpeg', 0.7);
                
                document.body.innerHTML = "<b style='font-family: sans-serif; color: #28a745;'>✅ Foto Capturada Exitosamente</b>";
                Streamlit.setComponentValue(b64);
            }
            img.src = event.target.result;
        }
        reader.readAsDataURL(file);
      });
      window.addEventListener('load', init);
    </script>
  </body>
</html>
"""

# Force Streamlit to overwrite the HTML file on startup to apply UI changes
_COMPONENT_DIR = ".fast_camera_component"
os.makedirs(_COMPONENT_DIR, exist_ok=True)
with open(os.path.join(_COMPONENT_DIR, "index.html"), "w", encoding="utf-8") as f:
    f.write(_fast_camera_html)

_fast_camera_func = components.declare_component("fast_mobile_camera", path=_COMPONENT_DIR)

def fast_mobile_camera(key=None):
    return _fast_camera_func(key=key, default=None)

# ==========================================
# 2. SUPABASE INITIALIZATION
# ==========================================
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error(f"Error conectando a Supabase. Verifique secrets.toml. Detalles: {e}")
    st.stop()

# ==========================================
# 3. AUTHENTICATION & STATE MANAGEMENT
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.update({
        'logged_in': False, 'user_id': None, 'username': None, 
        'full_name': None, 'role': None, 'agency_id': None, 'agency_name': None
    })

def login(username, password):
    resp = supabase.table("audit_users").select("*").eq("username", username).execute()
    if resp.data and resp.data[0]['password_hash'] == password:
        user = resp.data[0]
        st.session_state.update({
            'logged_in': True, 'user_id': user['id'], 'username': user['username'], 
            'full_name': user.get('full_name'), 'role': user['role'], 'agency_id': user['agency_id']
        })
        if user['agency_id']:
            ag_resp = supabase.table("audit_agencies").select("name").eq("id", user['agency_id']).execute()
            if ag_resp.data: st.session_state['agency_name'] = ag_resp.data[0]['name']
        st.rerun()
    else:
        st.error("Credenciales incorrectas.")

def logout():
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

if not st.session_state['logged_in']:
    st.title("🔐 Acceso al Sistema")
    with st.form("login_form"):
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar", type="primary"): login(user_input, pass_input)
    st.stop()

# ==========================================
# 4. DYNAMIC SIDEBAR NAVIGATION
# ==========================================
if os.path.exists("autoplex_logo.png"): st.sidebar.image("autoplex_logo.png", use_container_width=True)
st.sidebar.markdown("""
    <div style='text-align: center; margin-bottom: 20px;'>
        <h4 style='color: #005ca9; font-weight: bold; margin-bottom: 0px; margin-top: 10px;'>SOPORTE TÉCNICO</h4>
        <h3 style='color: #000000; font-weight: bold; margin-top: 5px;'>AUDITORÍA Y VISITA TÉCNICA</h3>
    </div>
""", unsafe_allow_html=True)

display_name = st.session_state['full_name'] if st.session_state['full_name'] else st.session_state['username']
st.sidebar.markdown(f"👤 **Usuario:** {display_name}")
st.sidebar.caption(f"**Perfil:** {st.session_state['role'].upper()}")
if st.sidebar.button("Cerrar Sesión", use_container_width=True): logout()
st.sidebar.divider()

if st.session_state['role'] == 'super_admin':
    st.sidebar.header("Menú Directivo")
    menu = st.sidebar.radio("Navegación:", ["📊 Dashboard Global", "📋 Operaciones (Visión Red)", "🔍 Detalle por Agencia", "🚨 Validar Correcciones"])
elif st.session_state['role'] == 'auditor':
    st.sidebar.header("Menú Operativo")
    menu = st.sidebar.radio("Navegación:", ["📸 Ejecutar Nueva Auditoría", "📂 Mi Historial"])
elif st.session_state['role'] == 'agency':
    st.sidebar.header(f"Agencia: {st.session_state['agency_name']}")
    menu = st.sidebar.radio("Navegación:", ["📑 Mi Última Auditoría", "🛠️ Mis Planes de Acción"])

# ==========================================
# 5. VIEWS: SUPER ADMIN
# ==========================================
if menu == "📊 Dashboard Global":
    st.title("📊 Dashboard Global de la Red")
    
    agencias_raw = supabase.table("audit_agencies").select("*").execute().data
    regiones = ["TODAS"] + sorted(list(set([a['region'] for a in agencias_raw])))
    
    col_f1, col_f2, col_f3 = st.columns(3)
    filtro_marca = col_f1.selectbox("Filtrar por Marca:", ["TODAS", "KIA", "AUTOPLEX"])
    filtro_region = col_f2.selectbox("Filtrar por Región:", regiones)
    
    agencias_filtradas = agencias_raw
    if filtro_region != "TODAS": agencias_filtradas = [a for a in agencias_filtradas if a['region'] == filtro_region]
    if filtro_marca != "TODAS": agencias_filtradas = [a for a in agencias_filtradas if a['brand'] == filtro_marca]
        
    nombres_agencias = ["TODAS"] + sorted([a['name'] for a in agencias_filtradas])
    filtro_agencia = col_f3.selectbox("Filtrar por Agencia:", nombres_agencias)

    query = supabase.table("audit_sessions").select("*, audit_agencies!inner(name, region, brand)").eq("status", "FINALIZADO")
    if filtro_marca != "TODAS": query = query.eq("marca", filtro_marca)
    if filtro_region != "TODAS": query = query.eq("audit_agencies.region", filtro_region)
    if filtro_agencia != "TODAS": query = query.eq("audit_agencies.name", filtro_agencia)
    
    sessions = query.execute().data
    session_ids = [s['id'] for s in sessions] if sessions else []
    
    total_audits = len(sessions)
    avg_score = sum([s['final_score_percentage'] for s in sessions]) / total_audits if total_audits > 0 else 0
    open_plans = supabase.table("audit_action_plans").select("id").eq("status", "🔴 ABIERTO").execute().data

    c1, c2, c3 = st.columns(3)
    c1.metric("Auditorías Ejecutadas", total_audits)
    c2.metric("Promedio Cumplimiento", f"{avg_score:.1f}%")
    c3.metric("Planes de Acción Abiertos", len(open_plans))

    st.markdown("<hr class='slim'>", unsafe_allow_html=True)

    if total_audits > 0:
        col_chart1, col_chart2 = st.columns([1, 1.5])
        with col_chart1:
            st.markdown("#### Score Global")
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = avg_score, number = {'suffix': "%"},
                domain = {'x': [0, 1], 'y': [0, 1]},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 1}, 'bar': {'color': "#005ca9"},
                    'steps': [{'range': [0, 70], 'color': "#ffe6e6"}, {'range': [70, 85], 'color': "#fff0cc"}, {'range': [85, 100], 'color': "#e6ffe6"}],
                    'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 85}
                }
            ))
            fig_gauge.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_chart2:
            st.markdown("#### Evolución de Cumplimiento")
            df_sessions = pd.DataFrame(sessions)
            df_sessions['fecha'] = pd.to_datetime(df_sessions['audit_date']).dt.strftime('%Y-%m-%d')
            trend_data = df_sessions.groupby('fecha')['final_score_percentage'].mean().reset_index().sort_values('fecha')
            fig_trend = px.line(trend_data, x='fecha', y='final_score_percentage', markers=True)
            fig_trend.update_traces(line_color='#005ca9', marker=dict(size=8))
            fig_trend.update_xaxes(type='category')
            fig_trend.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20), yaxis_title="Score (%)", xaxis_title="")
            fig_trend.update_yaxes(range=[0, 105])
            st.plotly_chart(fig_trend, use_container_width=True)

        st.markdown("<hr class='slim'>", unsafe_allow_html=True)
        st.markdown("#### Cumplimiento por Categoría Evaluada")
        if session_ids:
            records = supabase.table("audit_records").select("result_pass, audit_master_catalog!inner(category)").in_("session_id", session_ids).execute().data
            if records:
                df_rec = pd.DataFrame([{'Categoria': r['audit_master_catalog']['category'], 'Pass': 1 if r['result_pass'] else 0, 'Total': 1} for r in records])
                resumen = df_rec.groupby('Categoria').sum().reset_index()
                resumen['Cumplimiento'] = (resumen['Pass'] / resumen['Total'] * 100).round(1)
                resumen = resumen.sort_values('Cumplimiento', ascending=True)
                fig_bar = px.bar(resumen, x='Cumplimiento', y='Categoria', orientation='h', text='Cumplimiento', color='Cumplimiento', color_continuous_scale='Blues')
                fig_bar.update_traces(texttemplate='%{text}%', textposition='outside')
                fig_bar.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20), xaxis_title="Cumplimiento (%)", yaxis_title="")
                fig_bar.update_xaxes(range=[0, 115])
                st.plotly_chart(fig_bar, use_container_width=True)

elif menu == "📋 Operaciones (Visión Red)":
    st.title("📋 Gestión de Operaciones")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Puntos Críticos", "📋 Catálogo Máster", "🔑 Accesos", "💾 Almacenamiento", "🏢 Agencias"])
    
    with tab1:
        st.subheader("Ítems con Mayor Tasa de Falla")
        records = supabase.table("audit_records").select("result_pass, audit_master_catalog!inner(item_code, audit_question)").eq("result_pass", False).execute().data
        if records:
            fallas = [f"{r['audit_master_catalog']['item_code']}: {r['audit_master_catalog']['audit_question']}" for r in records]
            if fallas:
                st.dataframe(pd.DataFrame(fallas, columns=['Ítem']).value_counts().reset_index(name='Cantidad de Fallas').head(10), use_container_width=True)
            else: st.info("No hay fallas para mostrar.")
        else: st.info("Sin fallas registradas aún.")
            
    with tab2:
        st.subheader("Gestión del Catálogo de Auditoría")
        
        with st.expander("📥 Carga Masiva (Excel/CSV)"):
            st.info("Columnas requeridas: **item_code**, **category**, **sub_category**, **rigor_level**, **audit_question**")
            
            replace_catalog = st.checkbox("⚠️ Reemplazar catálogo existente (Borra las preguntas actuales antes de subir el nuevo archivo)")
            
            uploaded_cat = st.file_uploader("Subir Archivo de Catálogo", type=["xlsx", "csv"])
            if uploaded_cat and st.button("Procesar Archivo Masivo", type="primary"):
                try:
                    if replace_catalog:
                        existing_ids = [item['id'] for item in supabase.table("audit_master_catalog").select("id").execute().data]
                        if existing_ids:
                            supabase.table("audit_master_catalog").delete().in_("id", existing_ids).execute()

                    df_bulk = pd.read_csv(uploaded_cat) if uploaded_cat.name.endswith('.csv') else pd.read_excel(uploaded_cat)
                    records_to_insert = df_bulk[['item_code', 'category', 'sub_category', 'rigor_level', 'audit_question']].to_dict('records')
                    supabase.table("audit_master_catalog").insert(records_to_insert).execute()
                    st.success(f"¡{len(records_to_insert)} ítems cargados exitosamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error procesando archivo. Verifique que las 5 columnas estén presentes y bien escritas. Detalles: {e}")

        st.divider()
        with st.form("new_catalog_item"):
            st.markdown("#### Agregar Ítem Individual")
            c1, c2, c_sub, c3 = st.columns([1, 2, 2, 1])
            n_code = c1.text_input("Código (Ej. P1-3)")
            n_cat = c2.text_input("Categoría")
            n_sub = c_sub.text_input("Subcategoría")
            n_rigor = c3.selectbox("Nivel Rigor", [1, 2, 3])
            n_q = st.text_input("Pregunta de Auditoría")
            if st.form_submit_button("Guardar Nuevo Ítem"):
                if n_code and n_cat and n_q:
                    supabase.table("audit_master_catalog").insert({
                        "item_code": n_code, "category": n_cat, "sub_category": n_sub, 
                        "rigor_level": n_rigor, "audit_question": n_q
                    }).execute()
                    st.success("Ítem guardado.")
                    st.rerun()
                else:
                    st.error("Los campos Código, Categoría y Pregunta son obligatorios.")
        
        st.divider()
        catalog_data = supabase.table("audit_master_catalog").select("*").order("id").execute().data
        
        if catalog_data:
            st.markdown("#### Modificar o Eliminar Ítems Existentes")
            df_cat = pd.DataFrame(catalog_data)
            
            if 'sub_category' not in df_cat.columns:
                df_cat['sub_category'] = ""
                
            sel_item_code = st.selectbox("Seleccione el Ítem a editar:", df_cat['item_code'].tolist())
            item_to_edit = next(item for item in catalog_data if item['item_code'] == sel_item_code)
            
            c_edit1, c_edit2 = st.columns([3, 1])
            with c_edit1:
                with st.form("edit_item_form"):
                    new_q = st.text_input("Pregunta:", value=item_to_edit['audit_question'])
                    col_cat1, col_cat2 = st.columns(2)
                    new_cat = col_cat1.text_input("Categoría:", value=item_to_edit['category'])
                    new_sub = col_cat2.text_input("Subcategoría:", value=item_to_edit.get('sub_category') or "")
                    
                    if st.form_submit_button("Actualizar Ítem", type="primary"):
                        supabase.table("audit_master_catalog").update({
                            "audit_question": new_q, "category": new_cat, "sub_category": new_sub
                        }).eq("id", item_to_edit['id']).execute()
                        st.success("Actualizado correctamente.")
                        st.rerun()
            with c_edit2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Eliminar Ítem", type="primary", use_container_width=True):
                    try:
                        supabase.table("audit_master_catalog").delete().eq("id", item_to_edit['id']).execute()
                        st.success("Ítem eliminado.")
                        st.rerun()
                    except Exception as e:
                        st.error("No se puede eliminar porque ya está asociado a auditorías pasadas.")

            st.dataframe(df_cat[['item_code', 'category', 'sub_category', 'rigor_level', 'audit_question']], use_container_width=True)

    with tab3:
        def generate_pin(): return ''.join(random.choices(string.digits, k=6))
        st.subheader("🔑 Generador de Credenciales")
        col_gen1, col_gen2 = st.columns(2)
        with col_gen1:
            st.markdown("#### 🏢 Agencias")
            if st.button("Sincronizar Credenciales Agencias", type="primary", use_container_width=True):
                agencias = supabase.table("audit_agencies").select("*").execute().data
                existing = {u['username']: u['id'] for u in supabase.table("audit_users").select("username, id").eq("role", "agency").execute().data}
                for ag in agencias:
                    uname = ag['dealer_code']
                    if uname not in existing:
                        supabase.table("audit_users").insert({"username": uname, "password_hash": generate_pin(), "role": "agency", "agency_id": ag['id']}).execute()
                st.success("Sincronización completada.")

        with col_gen2:
            st.markdown("#### 🕵️ Auditores")
            if st.button("Generar 10 Perfiles de Auditor", type="primary", use_container_width=True):
                users = supabase.table("audit_users").select("username").like("username", "auditor_%").execute().data
                nums = [int(u['username'].split('_')[1]) for u in users if len(u['username'].split('_')) > 1 and u['username'].split('_')[1].isdigit()]
                start = max(nums) + 1 if nums else 1
                for i in range(start, start + 10):
                    supabase.table("audit_users").insert({"username": f"auditor_{i:02d}", "password_hash": generate_pin(), "role": "auditor"}).execute()
                st.success("10 perfiles creados.")

        st.divider()
        col_dir1, col_dir2 = st.columns(2)
        with col_dir1:
            st.markdown("#### 🏢 Agencias")
            ag_users = supabase.table("audit_users").select("username, password_hash, audit_agencies(name, brand)").eq("role", "agency").execute().data
            if ag_users:
                df_ag = pd.DataFrame([{"Agencia": u['audit_agencies']['name'] if u['audit_agencies'] else "N/A", "Marca": u['audit_agencies']['brand'] if u['audit_agencies'] else "N/A", "Usuario": u['username'], "PIN": u['password_hash']} for u in ag_users])
                st.dataframe(df_ag, use_container_width=True)
                st.download_button("📥 Descargar CSV", df_ag.to_csv(index=False), "directorio_agencias.csv", "text/csv")
        
        with col_dir2:
            st.markdown("#### 🕵️ Auditores")
            au_users = supabase.table("audit_users").select("username, password_hash, full_name").eq("role", "auditor").execute().data
            if au_users:
                df_au = pd.DataFrame([{"Usuario": u['username'], "Nombre Real": u.get('full_name') or "No Asignado", "PIN": u['password_hash']} for u in au_users])
                st.dataframe(df_au, use_container_width=True)
                with st.form("rename_auditor"):
                    sel_aud = st.selectbox("Asignar Nombre Real:", [u['username'] for u in au_users])
                    new_n = st.text_input("Nombre Completo")
                    if st.form_submit_button("Actualizar"):
                        supabase.table("audit_users").update({"full_name": new_n}).eq("username", sel_aud).execute()
                        st.rerun()
                        
    with tab4:
        st.subheader("💾 Monitor de Almacenamiento")
        all_sessions = supabase.table("audit_sessions").select("id, audit_date, audit_agencies(name)").execute().data
        sess_dict = {s['id']: f"{s['audit_agencies']['name']} ({s['audit_date'][:10]})" for s in all_sessions} if all_sessions else {}
        all_records = supabase.table("audit_records").select("session_id, evidence_size_bytes").execute().data
        all_plans = supabase.table("audit_action_plans").select("correction_size_bytes").execute().data
        
        bytes_rec = sum([r.get('evidence_size_bytes') or 0 for r in all_records]) if all_records else 0
        bytes_plan = sum([p.get('correction_size_bytes') or 0 for p in all_plans]) if all_plans else 0
        total_mb = (bytes_rec + bytes_plan) / (1024 * 1024)
        
        st.metric("Total Almacenamiento Usado", f"{total_mb:.2f} MB")
        
        if all_records:
            df_size = pd.DataFrame(all_records)
            df_size['evidence_size_bytes'] = df_size['evidence_size_bytes'].fillna(0)
            df_size['Auditoria'] = df_size['session_id'].map(sess_dict)
            size_summary = df_size.groupby('Auditoria')['evidence_size_bytes'].sum().reset_index()
            size_summary['MB'] = (size_summary['evidence_size_bytes'] / (1024 * 1024)).round(2)
            size_summary = size_summary.sort_values('MB', ascending=False).head(10)
            
            if not size_summary.empty and size_summary['MB'].sum() > 0:
                fig_size = px.bar(size_summary, x='MB', y='Auditoria', orientation='h', text='MB', color_discrete_sequence=['#ff7f0e'])
                fig_size.update_traces(texttemplate='%{text} MB', textposition='outside')
                fig_size.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20), xaxis_title="Megabytes (MB)", yaxis_title="", yaxis={'categoryorder':'total ascending'})
                fig_size.update_xaxes(range=[0, size_summary['MB'].max() * 1.2])
                st.plotly_chart(fig_size, use_container_width=True)
            else: st.info("Aún no hay fotos subidas.")

        st.divider()
        with st.expander("⚠️ Zona de Peligro (Borrar Datos de Prueba)"):
            st.warning("Esta acción eliminará TODAS las sesiones de auditoría, registros y planes de acción de la base de datos. Los usuarios, agencias y el catálogo de preguntas se mantendrán intactos.")
            confirm_delete = st.checkbox("Entiendo que esto es irreversible y quiero borrar el historial de auditorías.")
            
            if st.button("🔴 BORRAR TODO EL HISTORIAL", type="primary", disabled=not confirm_delete):
                try:
                    with st.spinner("Eliminando datos..."):
                        ap_ids = [x['id'] for x in supabase.table("audit_action_plans").select("id").execute().data]
                        if ap_ids: supabase.table("audit_action_plans").delete().in_("id", ap_ids).execute()
                        
                        ar_ids = [x['id'] for x in supabase.table("audit_records").select("id").execute().data]
                        if ar_ids: supabase.table("audit_records").delete().in_("id", ar_ids).execute()
                        
                        as_ids = [x['id'] for x in supabase.table("audit_sessions").select("id").execute().data]
                        if as_ids: supabase.table("audit_sessions").delete().in_("id", as_ids).execute()
                        
                    st.success("¡Historial borrado completamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al intentar borrar la base de datos: {e}")

    with tab5:
        st.subheader("🏢 Gestión de Agencias")
        
        with st.form("new_agency_form"):
            st.markdown("#### Registrar Nueva Agencia")
            c_a1, c_a2 = st.columns(2)
            new_ag_name = c_a1.text_input("Nombre de Agencia (Ej. Kia Sur)")
            new_ag_code = c_a2.text_input("Código Dealer (Ej. KIO01)")
            c_a3, c_a4 = st.columns(2)
            new_ag_brand = c_a3.selectbox("Marca", ["KIA", "AUTOPLEX"])
            new_ag_region = c_a4.text_input("Región (Ej. Sierra, Costa)")
            
            if st.form_submit_button("Guardar Agencia", type="primary"):
                if new_ag_name and new_ag_code and new_ag_region:
                    supabase.table("audit_agencies").insert({
                        "name": new_ag_name, "dealer_code": new_ag_code, 
                        "brand": new_ag_brand, "region": new_ag_region
                    }).execute()
                    st.success("Agencia registrada exitosamente.")
                    st.rerun()
                else:
                    st.error("Por favor complete todos los campos.")
        
        st.divider()
        agencias_existentes = supabase.table("audit_agencies").select("*").order("name").execute().data
        
        if agencias_existentes:
            st.markdown("#### Editar Agencia Existente")
            ag_names = [f"{a['name']} ({a['dealer_code']})" for a in agencias_existentes]
            sel_ag_idx = st.selectbox("Seleccione la Agencia a Editar:", range(len(agencias_existentes)), format_func=lambda x: ag_names[x])
            ag_edit = agencias_existentes[sel_ag_idx]
            
            with st.form("edit_agency_form"):
                e_a1, e_a2 = st.columns(2)
                upd_ag_name = e_a1.text_input("Nombre de Agencia", value=ag_edit['name'])
                upd_ag_code = e_a2.text_input("Código Dealer", value=ag_edit['dealer_code'])
                e_a3, e_a4 = st.columns(2)
                
                brand_options = ["KIA", "AUTOPLEX"]
                current_brand = ag_edit['brand'] if ag_edit['brand'] in brand_options else "AUTOPLEX"
                upd_ag_brand = e_a3.selectbox("Marca", brand_options, index=brand_options.index(current_brand))
                
                upd_ag_region = e_a4.text_input("Región", value=ag_edit['region'])
                
                if st.form_submit_button("Actualizar Agencia"):
                    supabase.table("audit_agencies").update({
                        "name": upd_ag_name, "dealer_code": upd_ag_code, 
                        "brand": upd_ag_brand, "region": upd_ag_region
                    }).eq("id", ag_edit['id']).execute()
                    st.success("Datos de la agencia actualizados.")
                    st.rerun()

elif menu == "🔍 Detalle por Agencia":
    st.title("🔍 Inspección por Agencia")
    
    agencias_raw = supabase.table("audit_agencies").select("*").order("name").execute().data
    regiones = ["TODAS"] + sorted(list(set([a['region'] for a in agencias_raw])))
    
    col_f1, col_f2, col_f3 = st.columns(3)
    filtro_marca = col_f1.selectbox("Filtrar Marca:", ["TODAS", "KIA", "AUTOPLEX"])
    filtro_region = col_f2.selectbox("Filtrar Región:", regiones)
    
    agencias_filtradas = agencias_raw
    if filtro_marca != "TODAS": agencias_filtradas = [a for a in agencias_filtradas if a['brand'] == filtro_marca]
    if filtro_region != "TODAS": agencias_filtradas = [a for a in agencias_filtradas if a['region'] == filtro_region]
    
    ag_dict = {f"{a['name']} ({a['dealer_code']})": a['id'] for a in agencias_filtradas}
    sel_ag = col_f3.selectbox("Seleccione Agencia:", list(ag_dict.keys()) if ag_dict else ["Sin resultados"])
    
    if sel_ag != "Sin resultados":
        agency_sessions = supabase.table("audit_sessions").select("*").eq("agency_id", ag_dict[sel_ag]).eq("status", "FINALIZADO").order("audit_date", desc=True).execute().data
        
        if agency_sessions:
            st.divider()
            
            session_options = {f"🗓️ {s['audit_date'][:10]} - Score: {s['final_score_percentage']:.1f}%": s for s in agency_sessions}
            
            col_hist1, col_hist2 = st.columns([1, 2])
            with col_hist1:
                sel_session_key = st.selectbox("Seleccione la Auditoría (Historial):", list(session_options.keys()))
            
            selected_session = session_options[sel_session_key]
            
            st.metric(f"Score ({selected_session['marca']})", f"{selected_session['final_score_percentage']:.1f}%", f"Fecha: {selected_session['audit_date'][:10]}")
            
            records = supabase.table("audit_records").select("*, audit_master_catalog!inner(item_code, audit_question, category)").eq("session_id", selected_session['id']).execute().data
            
            for r in records:
                icon = "✅" if r['result_pass'] else "❌"
                st.markdown(f"**[{r['audit_master_catalog']['item_code']}] {r['audit_master_catalog']['audit_question']}** | {icon}")
                if not r['result_pass']:
                    st.caption(f"Comentario Auditor: {r['auditor_comment']}")
                    if r['failure_photo_url']: st.image(r['failure_photo_url'], width=300)
                st.markdown("<hr class='slim'>", unsafe_allow_html=True)
        else:
            st.info("Esta agencia no tiene auditorías finalizadas registradas.")
    else:
        st.warning("No hay agencias que coincidan con estos filtros.")

elif menu == "🚨 Validar Correcciones":
    st.title("🚨 Validación de Planes")
    pending = supabase.table("audit_action_plans").select("*, audit_records!inner(failure_photo_url, auditor_comment, audit_sessions!inner(marca, audit_agencies(name)), audit_master_catalog(item_code, audit_question))").eq("status", "🟢 CERRADO").eq("admin_approved", False).execute().data
    if not pending: st.success("Todo al día.")
    else:
        for plan in pending:
            st.markdown(f"### 📍 {plan['audit_records']['audit_sessions']['audit_agencies']['name']} ({plan['audit_records']['audit_sessions']['marca']})")
            c1, c2 = st.columns(2)
            with c1:
                st.error(f"Falla: {plan['failure_description']}")
                if plan['audit_records']['failure_photo_url']: st.image(plan['audit_records']['failure_photo_url'], use_container_width=True)
            with c2:
                st.success(f"Corrección: {plan['corrective_action']}")
                if plan['correction_photo_url']: st.image(plan['correction_photo_url'], use_container_width=True)
            
            ca, cb = st.columns(2)
            if ca.button("✅ Aprobar", key=f"ap_{plan['id']}", use_container_width=True):
                supabase.table("audit_action_plans").update({"admin_approved": True}).eq("id", plan['id']).execute()
                st.rerun()
            if cb.button("❌ Rechazar", key=f"rj_{plan['id']}", type="primary", use_container_width=True):
                supabase.table("audit_action_plans").update({"status": "🔴 ABIERTO", "corrective_action": None, "correction_photo_url": None}).eq("id", plan['id']).execute()
                st.rerun()
            st.divider()

# ==========================================
# 6. VIEWS: AUDITOR (THE STEP-BY-STEP ENGINE)
# ==========================================
elif menu == "📸 Ejecutar Nueva Auditoría":
    st.title("📸 Ejecutar Auditoría")
    
    in_progress = supabase.table("audit_sessions").select("*, audit_agencies(name)").eq("auditor_id", st.session_state['user_id']).eq("status", "EN PROCESO").execute().data
    
    if in_progress:
        session = in_progress[0]
        session_id = session['id']
        st.warning(f"⚠️ Tiene una auditoría en progreso en **{session['audit_agencies']['name']}** ({session['marca']}).")
        
        c_btn1, c_btn2 = st.columns(2)
        if c_btn1.button("▶️ Continuar Auditoría", type="primary", use_container_width=True):
            st.session_state['active_session_id'] = session_id
            st.rerun()
        if c_btn2.button("🗑️ Descartar y Empezar Nueva", use_container_width=True):
            supabase.table("audit_records").delete().eq("session_id", session_id).execute()
            supabase.table("audit_sessions").delete().eq("id", session_id).execute()
            if 'active_session_id' in st.session_state: del st.session_state['active_session_id']
            st.rerun()
            
        if st.session_state.get('active_session_id') == session_id:
            st.divider()
            
            catalog = supabase.table("audit_master_catalog").select("*").order("id").execute().data
            if not catalog:
                st.error("El catálogo de preguntas está vacío. Contacte al administrador.")
                st.stop()

            answered_records = supabase.table("audit_records").select("catalog_id, result_pass").eq("session_id", session_id).execute().data
            answered_ids = [r['catalog_id'] for r in answered_records]
            
            pending_items = [item for item in catalog if item['id'] not in answered_ids]
            
            if pending_items:
                current_item = pending_items[0]
                progress = len(answered_ids) / len(catalog)
                
                st.progress(progress, text=f"Progreso: {len(answered_ids)} / {len(catalog)} completados")
                st.markdown(f"### Ítem Actual: [{current_item['item_code']}]")
                st.info(f"**Categoría:** {current_item['category']} | **Subcategoría:** {current_item.get('sub_category', 'N/A')} | **Rigor:** {current_item['rigor_level']}\n\n**Pregunta:** {current_item['audit_question']}")
                
                with st.form("single_question_form", clear_on_submit=True):
                    res = st.radio("Resultado de Inspección:", ["SI", "NO"], horizontal=True)
                    com = st.text_input("Comentario del Auditor (Obligatorio si es NO)")
                    
                    st.markdown("**Evidencia Fotográfica (Opcional en SI, Obligatorio en NO)**")
                    pic_base64 = fast_mobile_camera(key=f"cam_{current_item['id']}")
                    
                    if st.form_submit_button("Guardar y Continuar", type="primary"):
                        is_pass = (res == "SI")
                        
                        if not is_pass and pic_base64 is None:
                            st.error("⚠️ La evidencia fotográfica es obligatoria cuando un ítem es NO.")
                        elif not is_pass and not com.strip():
                            st.error("⚠️ El comentario es obligatorio para explicar la falla.")
                        else:
                            with st.spinner('Guardando datos...'):
                                public_photo_url = None
                                file_size_bytes = 0
                                
                                if pic_base64 is not None:
                                    file_name = f"auditor_{session_id}_item_{current_item['id']}_{random.randint(1000,9999)}.jpg"
                                    try:
                                        image_data = base64.b64decode(pic_base64.split(",")[1])
                                        file_size_bytes = len(image_data)
                                        
                                        supabase.storage.from_("audit_evidence").upload(
                                            path=file_name, 
                                            file=image_data, 
                                            file_options={"content-type": "image/jpeg"}
                                        )
                                        public_photo_url = supabase.storage.from_("audit_evidence").get_public_url(file_name)
                                    except Exception as e:
                                        st.error(f"Error subiendo imagen comprimida: {e}")

                                try:
                                    rec_resp = supabase.table("audit_records").insert({
                                        "session_id": session_id, "catalog_id": current_item['id'], "result_pass": is_pass, 
                                        "auditor_comment": com, "failure_photo_url": public_photo_url, "evidence_size_bytes": file_size_bytes
                                    }).execute()
                                    
                                    if not is_pass:
                                        supabase.table("audit_action_plans").insert({
                                            "record_id": rec_resp.data[0]['id'], "failure_description": com or "Falla documentada."
                                        }).execute()
                                    
                                    st.rerun()
                                except Exception as e:
                                    error_msg = str(e).lower()
                                    
                                    if "duplicate key" in error_msg or "unique constraint" in error_msg:
                                        st.warning("⚠️ Registro duplicado detectado (posible doble clic). Avanzando...")
                                        st.rerun()
                                    elif "foreign key" in error_msg:
                                        st.error("🛑 La sesión de auditoría fue borrada (reseteo detectado). Por favor, inicie una nueva inspección.")
                                        if 'active_session_id' in st.session_state:
                                            del st.session_state['active_session_id']
                                    else:
                                        st.error(f"🛑 Error de base de datos: {e}")
            else:
                st.success("✅ ¡Ha respondido todas las preguntas del catálogo!")
                if st.button("🏁 Cerrar Auditoría y Calcular Score Final", type="primary", use_container_width=True):
                    final_score = (sum(1 for r in answered_records if r.get('result_pass', True)) / len(catalog)) * 100 if catalog else 0
                    
                    session_info = supabase.table("audit_sessions").select("created_at").eq("id", session_id).execute().data[0]
                    try:
                        clean_time_str = session_info['created_at'].replace('Z', '+00:00').split('.')[0]
                        start_dt = datetime.fromisoformat(clean_time_str).replace(tzinfo=None)
                        dur_sec = int((datetime.utcnow() - start_dt).total_seconds())
                    except Exception:
                        dur_sec = 0
                    
                    supabase.table("audit_sessions").update({
                        "status": "FINALIZADO", "final_score_percentage": final_score, "duration_seconds": dur_sec
                    }).eq("id", session_id).execute()
                    
                    if 'active_session_id' in st.session_state: del st.session_state['active_session_id']
                    st.balloons()
                    st.rerun()

    else:
        st.info("Seleccione los datos del concesionario para iniciar una nueva inspección.")
        c_m1, c_m2 = st.columns([1, 2])
        sel_marca = c_m1.radio("1. Marca:", ["KIA", "AUTOPLEX"], horizontal=True)
        ag_data = supabase.table("audit_agencies").select("id, name, dealer_code, brand").eq("brand", sel_marca).order("name").execute().data
        
        if not ag_data: st.warning(f"No hay agencias de {sel_marca}.")
        else:
            ag_dict = {f"{a['name']} ({a['dealer_code']})": a['id'] for a in ag_data}
            sel_ag_name = c_m2.selectbox(f"2. Punto de Red {sel_marca}:", list(ag_dict.keys()))
            
            st.divider()
            if st.button("🚀 INICIAR AUDITORÍA", type="primary", use_container_width=True):
                new_session = supabase.table("audit_sessions").insert({
                    "agency_id": ag_dict[sel_ag_name], "auditor_id": st.session_state['user_id'], 
                    "marca": sel_marca, "status": "EN PROCESO"
                }).execute()
                st.session_state['active_session_id'] = new_session.data[0]['id']
                st.rerun()

elif menu == "📂 Mi Historial":
    st.title("📂 Mi Historial")
    hist = supabase.table("audit_sessions").select("*, audit_agencies(name)").eq("auditor_id", st.session_state['user_id']).eq("status", "FINALIZADO").order("audit_date", desc=True).execute().data
    if hist:
        df_h = pd.DataFrame([{"Agencia": h['audit_agencies']['name'], "Marca": h['marca'], "Fecha": h['audit_date'][:10], "Score": f"{h['final_score_percentage']}%", "Tiempo": f"{int(h['duration_seconds'] // 60)} min" if h.get('duration_seconds') else "N/A"} for h in hist])
        st.dataframe(df_h, use_container_width=True)
    else:
        st.info("Aún no ha finalizado ninguna auditoría.")

# ==========================================
# 7. VIEWS: AGENCY
# ==========================================
elif menu == "📑 Mi Última Auditoría":
    st.title(f"📑 {st.session_state['agency_name']}")
    session = supabase.table("audit_sessions").select("*").eq("agency_id", st.session_state['agency_id']).eq("status", "FINALIZADO").order("audit_date", desc=True).limit(1).execute().data
    if session:
        st.metric(f"Último Score ({session[0]['marca']})", f"{session[0]['final_score_percentage']:.1f}%", f"Fecha: {session[0]['audit_date'][:10]}")
    else: st.info("Agencia sin auditorías registradas.")

elif menu == "🛠️ Mis Planes de Acción":
    st.title("🛠️ Gestión de Planes")
    records = supabase.table("audit_records").select("id, audit_sessions!inner(agency_id), audit_master_catalog(item_code, audit_question)").eq("audit_sessions.agency_id", st.session_state['agency_id']).execute().data
    if records:
        rec_dict = {r['id']: r['audit_master_catalog'] for r in records}
        plans = supabase.table("audit_action_plans").select("*").in_("record_id", list(rec_dict.keys())).eq("status", "🔴 ABIERTO").execute().data
        if plans:
            for plan in plans:
                cat = rec_dict[plan['record_id']]
                with st.expander(f"🔴 [{cat['item_code']}] {cat['audit_question'][:60]}..."):
                    st.error(f"Reporte del Auditor: {plan['failure_description']}")
                    with st.form(f"fix_{plan['id']}"):
                        act = st.text_input("Acción Ejecutada (Obligatorio)")
                        corr_pic = st.file_uploader("Subir Foto de la Corrección", type=['jpg', 'jpeg', 'png'], key=f"up_{plan['id']}", accept_multiple_files=False)
                        
                        if st.form_submit_button("Subir y Enviar a Validación"):
                            if act and corr_pic is not None:
                                with st.spinner('Comprimiendo y subiendo evidencia...'):
                                    file_name = f"agency_fix_plan_{plan['id']}_{random.randint(1000,9999)}.jpg"
                                    try:
                                        image = Image.open(corr_pic)
                                        if image.mode in ("RGBA", "P"): image = image.convert("RGB")
                                        image.thumbnail((1080, 1080), Image.Resampling.LANCZOS)
                                        
                                        img_byte_arr = io.BytesIO()
                                        image.save(img_byte_arr, format='JPEG', quality=70)
                                        compressed_bytes = img_byte_arr.getvalue()
                                        file_size_bytes = len(compressed_bytes)
                                        
                                        supabase.storage.from_("audit_evidence").upload(path=file_name, file=compressed_bytes, file_options={"content-type": "image/jpeg"})
                                        pic_url = supabase.storage.from_("audit_evidence").get_public_url(file_name)
                                        
                                        supabase.table("audit_action_plans").update({"status": "🟢 CERRADO", "corrective_action": act, "correction_photo_url": pic_url, "correction_size_bytes": file_size_bytes}).eq("id", plan['id']).execute()
                                        st.success("Plan enviado exitosamente.")
                                        st.rerun()
                                    except Exception as e: st.error(f"Error al subir imagen: {e}")
                            else: st.error("Debe escribir la acción y subir una foto de evidencia.")
        else: st.success("No tiene planes de acción abiertos.")
    else: st.success("No hay registros vinculados a esta agencia.")
