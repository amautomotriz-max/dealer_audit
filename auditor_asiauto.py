import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import random
import string

# ==========================================
# 1. CONFIGURATION & STYLES
# ==========================================
st.set_page_config(page_title="Auditoría Integral VORD & 5S", layout="wide", page_icon="🛡️")

# Custom CSS for high-density UI and badges
st.markdown("""
    <style>
    .metric-card {background-color: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
    .pass-text {color: #28a745; font-weight: bold;}
    .fail-text {color: #dc3545; font-weight: bold;}
    .cat-badge {padding: 3px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; background-color: #e9ecef; color: #1e2b3c; border: 1px solid #ccc; display: inline-block;}
    hr.slim {margin: 12px 0; border: 0; border-top: 1px solid #eee;}
    /* Compact radio buttons */
    div[data-testid="stHorizontalBlock"] { gap: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

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
        'logged_in': False, 
        'user_id': None, 
        'username': None, 
        'full_name': None, 
        'role': None, 
        'agency_id': None, 
        'agency_name': None,
        # Audit execution states
        'audit_active': False,
        'audit_marca': None,
        'audit_ag_id': None,
        'audit_ag_name': None,
        'audit_start_time': None
    })

def login(username, password):
    resp = supabase.table("audit_users").select("*").eq("username", username).execute()
    if resp.data and resp.data[0]['password_hash'] == password:
        user = resp.data[0]
        st.session_state.update({
            'logged_in': True, 
            'user_id': user['id'], 
            'username': user['username'], 
            'full_name': user.get('full_name'), 
            'role': user['role'], 
            'agency_id': user['agency_id']
        })
        if user['agency_id']:
            ag_resp = supabase.table("audit_agencies").select("name").eq("id", user['agency_id']).execute()
            if ag_resp.data:
                st.session_state['agency_name'] = ag_resp.data[0]['name']
        st.rerun()
    else:
        st.error("Credenciales incorrectas.")

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

if not st.session_state['logged_in']:
    st.title("🔐 Acceso al Sistema de Auditoría KIA / ASIAUTO")
    with st.form("login_form"):
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar", type="primary"):
            login(user_input, pass_input)
    st.stop()

# ==========================================
# 4. DYNAMIC SIDEBAR NAVIGATION
# ==========================================
display_name = st.session_state['full_name'] if st.session_state['full_name'] else st.session_state['username']
st.sidebar.title(f"👤 {display_name}")
st.sidebar.caption(f"Perfil: {st.session_state['role'].upper()}")
if st.sidebar.button("Cerrar Sesión"):
    logout()
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
    filtro_marca = col_f1.selectbox("Filtrar por Marca:", ["TODAS", "KIA", "ASIAUTO"])
    filtro_region = col_f2.selectbox("Filtrar por Región:", regiones)
    
    agencias_filtradas = agencias_raw if filtro_region == "TODAS" else [a for a in agencias_raw if a['region'] == filtro_region]
    nombres_agencias = ["TODAS"] + sorted([a['name'] for a in agencias_filtradas])
    filtro_agencia = col_f3.selectbox("Filtrar por Agencia:", nombres_agencias)

    query = supabase.table("audit_sessions").select("*, audit_agencies!inner(name, region, brand)")
    if filtro_marca != "TODAS":
        query = query.eq("marca", filtro_marca)
    if filtro_region != "TODAS":
        query = query.eq("audit_agencies.region", filtro_region)
    if filtro_agencia != "TODAS":
        query = query.eq("audit_agencies.name", filtro_agencia)
    
    sessions = query.execute().data
    total_audits = len(sessions)
    avg_score = sum([s['final_score_percentage'] for s in sessions]) / total_audits if total_audits > 0 else 0
    open_plans = supabase.table("audit_action_plans").select("id").eq("status", "🔴 ABIERTO").execute().data

    c1, c2, c3 = st.columns(3)
    c1.metric("Auditorías Ejecutadas", total_audits)
    c2.metric("Promedio Cumplimiento", f"{avg_score:.1f}%")
    c3.metric("Planes de Acción Abiertos (Red)", len(open_plans))

    st.divider()
    st.subheader("Cumplimiento por Categoría")
    if total_audits > 0:
        session_ids = [s['id'] for s in sessions]
        records = supabase.table("audit_records").select("result_pass, audit_master_catalog!inner(category)").in_("session_id", session_ids).execute().data
        if records:
            df_rec = pd.DataFrame([{'Categoria': r['audit_master_catalog']['category'], 'Pass': 1 if r['result_pass'] else 0, 'Total': 1} for r in records])
            resumen = df_rec.groupby('Categoria').sum().reset_index()
            resumen['Cumplimiento'] = (resumen['Pass'] / resumen['Total'] * 100).round(1)
            
            cols = st.columns(len(resumen))
            for i, cat in enumerate(resumen['Categoria']):
                val = resumen[resumen['Categoria'] == cat]['Cumplimiento'].values[0]
                cols[i].metric(cat, f"{val}%")

elif menu == "📋 Operaciones (Visión Red)":
    st.title("📋 Gestión de Operaciones")
    tab1, tab2, tab3 = st.tabs(["📊 Top Puntos Críticos", "📋 Catálogo Máster", "🔑 Directorio y Accesos"])
    
    with tab1:
        st.subheader("Ítems con Mayor Tasa de Falla")
        records = supabase.table("audit_records").select("result_pass, audit_master_catalog!inner(item_code, audit_question)").eq("result_pass", False).execute().data
        if records:
            fallas = [f"{r['audit_master_catalog']['item_code']}: {r['audit_master_catalog']['audit_question']}" for r in records]
            df_fallas = pd.DataFrame(fallas, columns=['Ítem']).value_counts().reset_index(name='Cantidad de Fallas').head(5)
            st.dataframe(df_fallas, use_container_width=True)
        else:
            st.info("Sin fallas registradas aún.")
            
    with tab2:
        st.subheader("Agregar Nuevo Ítem al Catálogo")
        with st.form("new_catalog_item"):
            c1, c2, c3 = st.columns([1, 2, 1])
            n_code = c1.text_input("Código (Ej. P1-3)")
            n_cat = c2.text_input("Categoría")
            n_rigor = c3.selectbox("Nivel Rigor", [1, 2, 3])
            n_q = st.text_input("Pregunta de Auditoría")
            if st.form_submit_button("Guardar Ítem", type="primary"):
                supabase.table("audit_master_catalog").insert({"item_code": n_code, "category": n_cat, "rigor_level": n_rigor, "audit_question": n_q}).execute()
                st.success("Ítem guardado.")
        
        st.divider()
        catalog_data = supabase.table("audit_master_catalog").select("*").order("id").execute().data
        if catalog_data:
            st.dataframe(pd.DataFrame(catalog_data)[['item_code', 'category', 'rigor_level', 'audit_question']], use_container_width=True)

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
                        pin = generate_pin()
                        supabase.table("audit_users").insert({"username": uname, "password_hash": pin, "role": "agency", "agency_id": ag['id']}).execute()
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
                st.download_button("📥 Descargar CSV Agencias", df_ag.to_csv(index=False), "directorio_agencias.csv", "text/csv")
        
        with col_dir2:
            st.markdown("#### 🕵️ Auditores")
            au_users = supabase.table("audit_users").select("username, password_hash, full_name").eq("role", "auditor").execute().data
            if au_users:
                df_au = pd.DataFrame([{"Usuario": u['username'], "Nombre Real": u.get('full_name') or "No Asignado", "PIN": u['password_hash']} for u in au_users])
                st.dataframe(df_au, use_container_width=True)
                st.download_button("📥 Descargar CSV Auditores", df_au.to_csv(index=False), "directorio_auditores.csv", "text/csv")
                with st.form("rename_auditor"):
                    sel_aud = st.selectbox("Asignar Nombre Real:", [u['username'] for u in au_users])
                    new_n = st.text_input("Nombre Completo")
                    if st.form_submit_button("Actualizar"):
                        supabase.table("audit_users").update({"full_name": new_n}).eq("username", sel_aud).execute()
                        st.rerun()

elif menu == "🔍 Detalle por Agencia":
    st.title("🔍 Inspección por Agencia")
    agencias = supabase.table("audit_agencies").select("id, name").order("name").execute().data
    ag_dict = {a['name']: a['id'] for a in agencias}
    sel_ag = st.selectbox("Seleccione Agencia:", list(ag_dict.keys()))
    if sel_ag:
        latest = supabase.table("audit_sessions").select("*").eq("agency_id", ag_dict[sel_ag]).order("audit_date", desc=True).limit(1).execute().data
        if latest:
            st.metric(f"Score ({latest[0]['marca']})", f"{latest[0]['final_score_percentage']:.1f}%", f"Fecha: {latest[0]['audit_date'][:10]}")
            records = supabase.table("audit_records").select("*, audit_master_catalog!inner(item_code, audit_question, category)").eq("session_id", latest[0]['id']).execute().data
            for r in records:
                icon = "✅" if r['result_pass'] else "❌"
                st.markdown(f"**[{r['audit_master_catalog']['item_code']}] {r['audit_master_catalog']['audit_question']}** | {icon}")
                if not r['result_pass']:
                    st.caption(f"Comentario Auditor: {r['auditor_comment']}")
                    if r['failure_photo_url']:
                        st.image(r['failure_photo_url'], width=300)
                st.markdown("<hr class='slim'>", unsafe_allow_html=True)
        else:
            st.info("Sin auditorías.")

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
# 6. VIEWS: AUDITOR
# ==========================================
elif menu == "📸 Ejecutar Nueva Auditoría":
    st.title("📸 Nueva Auditoría")
    
    # ---------------------------------------------------------
    # STATE 1: SETUP (BRAND & AGENCY SELECTION)
    # ---------------------------------------------------------
    if not st.session_state['audit_active']:
        st.info("Por favor, seleccione los datos del concesionario para comenzar.")
        
        c_m1, c_m2 = st.columns([1, 2])
        sel_marca = c_m1.radio("1. Marca:", ["KIA", "ASIAUTO"], horizontal=True)
        
        ag_data = supabase.table("audit_agencies").select("id, name, dealer_code, brand").eq("brand", sel_marca).order("name").execute().data
        
        if not ag_data:
            st.warning(f"No hay agencias configuradas como {sel_marca}.")
            st.stop()

        ag_dict = {f"{a['name']} ({a['dealer_code']})": a['id'] for a in ag_data}
        sel_ag_name = c_m2.selectbox(f"2. Punto de Red {sel_marca}:", list(ag_dict.keys()))
        sel_ag_id = ag_dict[sel_ag_name]
        
        st.divider()
        if st.button("🚀 COMENZAR AUDITORÍA", type="primary", use_container_width=True):
            st.session_state['audit_active'] = True
            st.session_state['audit_marca'] = sel_marca
            st.session_state['audit_ag_id'] = sel_ag_id
            st.session_state['audit_ag_name'] = sel_ag_name
            st.session_state['audit_start_time'] = datetime.now()
            st.rerun()

    # ---------------------------------------------------------
    # STATE 2: ACTIVE AUDIT EXECUTION
    # ---------------------------------------------------------
    else:
        # Calculate running time visually
        elapsed = datetime.now() - st.session_state['audit_start_time']
        mins, secs = divmod(elapsed.total_seconds(), 60)
        
        st.success(f"📍 **Agencia:** {st.session_state['audit_ag_name']} | 🚙 **Marca:** {st.session_state['audit_marca']}")
        st.info(f"⏱️ **Tiempo Transcurrido:** {int(mins)} min {int(secs)} seg")
        
        if st.button("❌ Cancelar Auditoría (Perderá el progreso)"):
            st.session_state['audit_active'] = False
            st.rerun()
            
        st.divider()
        
        catalog = supabase.table("audit_master_catalog").select("*").order("id").execute().data
        
        with st.form("audit_form"):
            st.subheader("Matriz de Evaluación")
            results, comments, photos = {}, {}, {}
            
            for item in catalog:
                cq, cr = st.columns([5, 1])
                cq.markdown(f"**[{item['item_code']}] <span class='cat-badge'>{item['category']}</span>** - {item['audit_question']}", unsafe_allow_html=True)
                results[item['id']] = cr.radio("Res", ["PASA", "NO PASA"], key=f"res_{item['id']}", horizontal=True, label_visibility="collapsed")
                
                comments[item['id']] = st.text_input("Com", key=f"com_{item['id']}", placeholder="Comentario del Auditor (Obligatorio si NO PASA)", label_visibility="collapsed")
                
                # STRICT SINGLE FILE UPLOAD: accept_multiple_files=False forces one file only.
                photos[item['id']] = st.file_uploader("Subir Evidencia", type=['jpg', 'jpeg', 'png'], key=f"pic_{item['id']}", label_visibility="collapsed", accept_multiple_files=False)
                
                st.markdown("<hr class='slim'>", unsafe_allow_html=True)
                
            if st.form_submit_button("🏁 Finalizar y Guardar Auditoría", type="primary"):
                with st.spinner('Procesando datos y subiendo imágenes a la nube...'):
                    # Final duration calculation
                    final_duration_sec = int((datetime.now() - st.session_state['audit_start_time']).total_seconds())
                    score = (sum(1 for r in results.values() if r == "PASA") / len(catalog)) * 100 if catalog else 0
                    
                    session_resp = supabase.table("audit_sessions").insert({
                        "agency_id": st.session_state['audit_ag_id'], 
                        "auditor_id": st.session_state['user_id'], 
                        "marca": st.session_state['audit_marca'], 
                        "final_score_percentage": score,
                        "rigor_level_executed": 3,
                        "duration_seconds": final_duration_sec
                    }).execute()
                    session_id = session_resp.data[0]['id']
                    
                    for cid, result in results.items():
                        is_pass = (result == "PASA")
                        
                        public_photo_url = None
                        if not is_pass and photos[cid] is not None:
                            file = photos[cid]
                            file_ext = file.name.split('.')[-1]
                            file_name = f"auditor_{session_id}_item_{cid}_{random.randint(1000,9999)}.{file_ext}"
                            
                            try:
                                supabase.storage.from_("audit_evidence").upload(
                                    path=file_name,
                                    file=file.getvalue(),
                                    file_options={"content-type": file.type}
                                )
                                public_photo_url = supabase.storage.from_("audit_evidence").get_public_url(file_name)
                            except Exception as e:
                                st.error(f"Error subiendo imagen para ítem {cid}: {e}")

                        rec_resp = supabase.table("audit_records").insert({
                            "session_id": session_id, "catalog_id": cid, "result_pass": is_pass, 
                            "auditor_comment": comments[cid], "failure_photo_url": public_photo_url
                        }).execute()
                        
                        if not is_pass:
                            supabase.table("audit_action_plans").insert({
                                "record_id": rec_resp.data[0]['id'], "failure_description": comments[cid] or "Falla documentada."
                            }).execute()
                    
                    # Reset the session state so they can do a new audit
                    st.session_state['audit_active'] = False
                    
                    st.success(f"¡Guardado exitosamente! Puntaje Final: {score:.1f}% | Tiempo: {int(final_duration_sec // 60)} min")
                    st.balloons()

elif menu == "📂 Mi Historial":
    st.title("📂 Mi Historial")
    hist = supabase.table("audit_sessions").select("*, audit_agencies(name)").eq("auditor_id", st.session_state['user_id']).order("audit_date", desc=True).execute().data
    if hist:
        df_h = pd.DataFrame([{
            "Agencia": h['audit_agencies']['name'], 
            "Marca": h['marca'], 
            "Fecha": h['audit_date'][:10], 
            "Score": f"{h['final_score_percentage']}%",
            "Tiempo": f"{int(h['duration_seconds'] // 60)} min" if h.get('duration_seconds') else "N/A"
        } for h in hist])
        st.dataframe(df_h, use_container_width=True)

# ==========================================
# 7. VIEWS: AGENCY
# ==========================================
elif menu == "📑 Mi Última Auditoría":
    st.title(f"📑 {st.session_state['agency_name']}")
    session = supabase.table("audit_sessions").select("*").eq("agency_id", st.session_state['agency_id']).order("audit_date", desc=True).limit(1).execute().data
    if session:
        st.metric(f"Último Score ({session[0]['marca']})", f"{session[0]['final_score_percentage']:.1f}%", f"Fecha: {session[0]['audit_date'][:10]}")
    else:
        st.info("Agencia sin auditorías registradas.")

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
                                with st.spinner('Subiendo evidencia...'):
                                    file_ext = corr_pic.name.split('.')[-1]
                                    file_name = f"agency_fix_plan_{plan['id']}_{random.randint(1000,9999)}.{file_ext}"
                                    
                                    try:
                                        supabase.storage.from_("audit_evidence").upload(
                                            path=file_name,
                                            file=corr_pic.getvalue(),
                                            file_options={"content-type": corr_pic.type}
                                        )
                                        pic_url = supabase.storage.from_("audit_evidence").get_public_url(file_name)
                                        
                                        supabase.table("audit_action_plans").update({
                                            "status": "🟢 CERRADO", 
                                            "corrective_action": act, 
                                            "correction_photo_url": pic_url
                                        }).eq("id", plan['id']).execute()
                                        
                                        st.success("Plan enviado exitosamente.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al subir imagen: {e}")
                            else:
                                st.error("Debe escribir la acción y subir una foto de evidencia.")
        else:
            st.success("No tiene planes de acción abiertos.")
