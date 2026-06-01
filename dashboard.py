"""
Dashboard semanal SEO — La Fábrica del SEO
"""
import os
import json
import re
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google.cloud import storage

BUCKET = os.environ.get("DASHBOARD_BUCKET", "seo-dashboard-data-fabricaseo")

st.set_page_config(
    page_title="Dashboard SEO — La Fábrica del SEO",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth simple ────────────────────────────────
if "password" in st.secrets:
    pwd = st.text_input("🔐 Contraseña", type="password")
    if pwd != st.secrets["password"]:
        st.stop()


# ──────────────────────────────────────────────
# GCS helpers
# ──────────────────────────────────────────────

@st.cache_resource
def _client():
    if "gcp_service_account" in st.secrets:
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"])
        )
        return storage.Client(credentials=creds)
    return storage.Client()

@st.cache_data(ttl=300)
def cargar_scores_historicos():
    blob = _client().bucket(BUCKET).blob("scores_history.json")
    if not blob.exists():
        return {}
    return json.loads(blob.download_as_text())

@st.cache_data(ttl=300)
def listar_informes():
    bucket = _client().bucket(BUCKET)
    blobs = bucket.list_blobs(prefix="reports/report-")
    fechas = []
    for b in blobs:
        m = re.search(r"report-(\d{4}-\d{2}-\d{2})\.json$", b.name)
        if m:
            fechas.append(m.group(1))
    return sorted(fechas, reverse=True)

@st.cache_data(ttl=300)
def cargar_informe(fecha=None):
    bucket = _client().bucket(BUCKET)
    nombre = f"reports/report-{fecha}.json" if fecha else "reports/latest.json"
    blob = bucket.blob(nombre)
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text())

@st.cache_data(ttl=300)
def listar_metricas():
    bucket = _client().bucket(BUCKET)
    blobs = bucket.list_blobs(prefix="metrics/metrics-")
    fechas = []
    for b in blobs:
        m = re.search(r"metrics-(\d{4}-\d{2}-\d{2})\.json$", b.name)
        if m:
            fechas.append(m.group(1))
    return sorted(fechas, reverse=True)

@st.cache_data(ttl=300)
def cargar_metricas(fecha=None):
    bucket = _client().bucket(BUCKET)
    nombre = f"metrics/metrics-{fecha}.json" if fecha else "metrics/latest.json"
    blob = bucket.blob(nombre)
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text())


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def color_score(score):
    if score is None:
        return "⚪"
    if score >= 80:
        return "🟢"
    if score >= 50:
        return "🟡"
    return "🔴"

def estado_score(score):
    if score is None:
        return "Sin dato"
    if score >= 80:
        return "Sano"
    if score >= 50:
        return "Atención"
    return "Crítico"

def delta_score(actual, anterior):
    if actual is None or anterior is None:
        return None
    return actual - anterior

def pct(curr, prev):
    if not prev:
        return "—"
    d = (curr - prev) / prev * 100
    arrow = "↑" if d > 0 else "↓"
    return f"{arrow} {abs(d):.1f}%"


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────

with st.sidebar:
    st.title("Dashboard SEO")
    st.caption("La Fábrica del SEO")
    informes = listar_informes()
    if informes:
        fecha_sel = st.selectbox(
            "Semana del informe", informes, index=0,
            format_func=lambda f: datetime.strptime(f, "%Y-%m-%d").strftime("%d %b %Y"),
        )
    else:
        fecha_sel = None
        st.warning("Aún no hay informes en el bucket.")
    if st.button("Refrescar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.caption("Cron: lunes 08:10 (Madrid)")
    st.caption(f"Bucket: `{BUCKET}`")


# ──────────────────────────────────────────────
# Carga datos
# ──────────────────────────────────────────────

informe = cargar_informe(fecha_sel) if fecha_sel else None
historico = cargar_scores_historicos()
metricas = cargar_metricas(fecha_sel) if fecha_sel else cargar_metricas()

if not informe and not historico and not metricas:
    st.error("No hay datos disponibles. Espera al próximo lunes o lanza manualmente el agente.")
    st.stop()


# ──────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────

tab_overview, tab_clientes, tab_evolucion, tab_alertas, tab_informe = st.tabs([
    "Resumen", "Clientes", "Evolución", "Alertas", "Informe",
])


# ──────────── RESUMEN ────────────
with tab_overview:
    if not informe:
        st.info("Selecciona una semana en el sidebar.")
        st.stop()

    scores = informe.get("scores", {})

    # Scores semana anterior
    fechas_hist = sorted(historico.keys())
    idx_actual = fechas_hist.index(informe["fecha"]) if informe["fecha"] in fechas_hist else len(fechas_hist) - 1
    scores_ant = historico[fechas_hist[idx_actual - 1]] if idx_actual > 0 else {}

    # Conclusión de Claude arriba
    secciones = informe.get("secciones", {})
    resumen_claude = next(
        (v for k, v in secciones.items() if any(w in k.upper() for w in ("RESUMEN", "CONCLUSI", "INSIGHT"))),
        None,
    )
    if resumen_claude:
        st.info(resumen_claude)
    elif informe.get("analisis"):
        primeras = informe["analisis"][:800].strip()
        st.info(primeras + ("…" if len(informe["analisis"]) > 800 else ""))

    st.divider()

    # KPIs con delta
    n_sanos = sum(1 for s in scores.values() if s >= 80)
    n_atencion = sum(1 for s in scores.values() if 50 <= s < 80)
    n_criticos = sum(1 for s in scores.values() if s < 50)

    n_sanos_ant = sum(1 for s in scores_ant.values() if s >= 80) if scores_ant else None
    n_atencion_ant = sum(1 for s in scores_ant.values() if 50 <= s < 80) if scores_ant else None
    n_criticos_ant = sum(1 for s in scores_ant.values() if s < 50) if scores_ant else None

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total clientes", len(scores))
    with col2:
        st.metric("Sanos (≥80)", n_sanos,
                  delta=int(n_sanos - n_sanos_ant) if n_sanos_ant is not None else None)
    with col3:
        st.metric("Atención (50-79)", n_atencion,
                  delta=int(n_atencion - n_atencion_ant) if n_atencion_ant is not None else None,
                  delta_color="inverse")
    with col4:
        st.metric("Críticos (<50)", n_criticos,
                  delta=int(n_criticos - n_criticos_ant) if n_criticos_ant is not None else None,
                  delta_color="inverse")

    # KPIs de conversiones (si hay métricas)
    if metricas and "clientes" in metricas:
        total_conv = sum(
            sum(d.get("key_events", {}).values())
            for d in metricas["clientes"].values()
        )
        total_conv_prev = sum(
            sum(d.get("key_events_prev", {}).values())
            for d in metricas["clientes"].values()
        )
        total_rev = sum(d.get("revenue", 0) for d in metricas["clientes"].values())
        total_rev_prev = sum(d.get("revenue_prev", 0) for d in metricas["clientes"].values())
        clientes_sin_conv = sum(
            1 for d in metricas["clientes"].values()
            if sum(d.get("key_events", {}).values()) == 0 and d.get("ga4_ok")
        )

        st.divider()
        st.markdown("##### Conversiones")
        c1, c2, c3 = st.columns(3)
        with c1:
            delta_conv = int(total_conv - total_conv_prev) if total_conv_prev else None
            st.metric("Total conversiones", total_conv, delta=delta_conv)
        with c2:
            if total_rev:
                delta_rev = round(total_rev - total_rev_prev, 2) if total_rev_prev else None
                st.metric("Revenue total (€)", f"{total_rev:,.0f} €", delta=f"{delta_rev:+.0f} €" if delta_rev is not None else None)
            else:
                st.metric("Revenue total (€)", "—")
        with c3:
            st.metric("Clientes sin conversiones", clientes_sin_conv,
                      help="Clientes con GA4 OK pero 0 conversiones registradas esta semana")

    st.divider()

    # Barra horizontal de todos los clientes ordenados por score
    if scores:
        df_scores = pd.DataFrame([{"Cliente": k, "Score": v} for k, v in scores.items()])
        df_scores = df_scores.sort_values("Score", ascending=True)
        colores = df_scores["Score"].apply(
            lambda s: "#ef4444" if s < 50 else ("#eab308" if s < 80 else "#22c55e")
        ).tolist()

        fig = go.Figure(go.Bar(
            y=df_scores["Cliente"],
            x=df_scores["Score"],
            orientation="h",
            marker_color=colores,
            text=df_scores["Score"].astype(str),
            textposition="outside",
        ))
        fig.add_vline(x=80, line_dash="dash", line_color="#22c55e", opacity=0.4, annotation_text="80")
        fig.add_vline(x=50, line_dash="dash", line_color="#ef4444", opacity=0.4, annotation_text="50")
        fig.update_layout(
            height=max(400, len(df_scores) * 22),
            xaxis=dict(range=[0, 110], title="Score"),
            yaxis_title="",
            margin=dict(t=10, b=20, l=10, r=60),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)


# ──────────── CLIENTES ────────────
with tab_clientes:
    if not informe:
        st.info("Selecciona una semana en el sidebar.")
        st.stop()

    scores = informe.get("scores", {})
    fechas_hist = sorted(historico.keys())
    idx_actual = fechas_hist.index(informe["fecha"]) if informe["fecha"] in fechas_hist else len(fechas_hist) - 1
    scores_ant = historico[fechas_hist[idx_actual - 1]] if idx_actual > 0 else {}

    tiene_metricas = metricas and "clientes" in metricas

    filas = []
    for cliente, score in scores.items():
        ant = scores_ant.get(cliente)
        fila = {
            " ": color_score(score),
            "Cliente": cliente,
            "Score": score,
            "Δ Score": delta_score(score, ant),
            "Estado": estado_score(score),
        }
        if tiene_metricas and cliente in metricas["clientes"]:
            d = metricas["clientes"][cliente]
            conv = sum(d.get("key_events", {}).values())
            conv_prev = sum(d.get("key_events_prev", {}).values())
            fila["Conv."] = conv
            fila["Δ Conv."] = pct(conv, conv_prev)
            fila["Revenue"] = f"{d.get('revenue', 0):,.0f} €" if d.get("revenue") else "—"
            fila["Orgánico"] = d.get("organic_sessions", 0)
            fila["Δ Org."] = pct(d.get("organic_sessions", 0), d.get("organic_sessions_prev", 0))
            fila["GSC clics"] = d.get("gsc_clicks", 0)
            fila["Δ GSC"] = pct(d.get("gsc_clicks", 0), d.get("gsc_clicks_prev", 0))
            fila["IA"] = sum(d.get("llm", {}).values())
        filas.append(fila)

    df = pd.DataFrame(filas).sort_values("Score", ascending=False)

    # Filtros
    col1, col2 = st.columns([3, 1])
    with col1:
        busca = st.text_input("Buscar cliente", "", placeholder="Nombre...")
    with col2:
        estados = st.multiselect("Estado", ["Sano", "Atención", "Crítico"], default=[])

    if busca:
        df = df[df["Cliente"].str.contains(busca, case=False, na=False)]
    if estados:
        df = df[df["Estado"].isin(estados)]

    cols_show = [" ", "Cliente", "Score", "Δ Score"]
    if tiene_metricas:
        cols_show += ["Conv.", "Δ Conv.", "Revenue", "Orgánico", "Δ Org.", "GSC clics", "Δ GSC", "IA"]

    col_config = {
        "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
        "Δ Score": st.column_config.NumberColumn("Δ Score", format="%+d"),
    }

    st.dataframe(df[cols_show], use_container_width=True, hide_index=True, column_config=col_config)
    st.caption(f"Mostrando {len(df)} de {len(scores)} clientes")


# ──────────── EVOLUCIÓN ────────────
with tab_evolucion:
    if not historico:
        st.info("No hay histórico todavía.")
    else:
        todos_clientes = sorted({c for s in historico.values() for c in s.keys()})
        col1, col2 = st.columns([3, 1])
        with col1:
            seleccionados = st.multiselect(
                "Clientes",
                todos_clientes,
                default=todos_clientes[:10] if len(todos_clientes) > 10 else todos_clientes,
            )
        with col2:
            n_semanas = st.slider("Semanas", 2, 20, min(8, len(historico)))

        fechas_ord = sorted(historico.keys())[-n_semanas:]
        data = []
        for fecha in fechas_ord:
            for cliente in seleccionados:
                data.append({
                    "Fecha": fecha,
                    "Cliente": cliente,
                    "Score": historico[fecha].get(cliente),
                })
        df = pd.DataFrame(data).dropna(subset=["Score"])

        if df.empty:
            st.warning("Sin datos para los clientes seleccionados.")
        else:
            fig = go.Figure()
            for cliente in seleccionados:
                df_c = df[df["Cliente"] == cliente]
                if df_c.empty:
                    continue
                fig.add_trace(go.Scatter(
                    x=df_c["Fecha"], y=df_c["Score"],
                    mode="lines+markers", name=cliente,
                ))
            fig.add_hline(y=80, line_dash="dash", line_color="#22c55e", opacity=0.4, annotation_text="Sano")
            fig.add_hline(y=50, line_dash="dash", line_color="#ef4444", opacity=0.4, annotation_text="Crítico")
            fig.update_layout(
                height=500,
                hovermode="x unified",
                yaxis=dict(range=[0, 100], title="Score"),
                xaxis_title="",
                margin=dict(t=20, b=10, l=10, r=10),
            )
            st.plotly_chart(fig, use_container_width=True)


# ──────────── ALERTAS ────────────
with tab_alertas:
    if not informe:
        st.info("Selecciona una semana en el sidebar.")
        st.stop()

    secciones = informe.get("secciones", {})
    if not secciones:
        st.info("No hay secciones de alertas en este informe.")
    else:
        for clave_busqueda, titulo in [
            ("ALERTA", "Alertas críticas"),
            ("REPORTING", "Reporting incompleto"),
            ("PROBLEMA", "Problemas internos"),
            ("INSIGHT", "Insights y patrones"),
            ("RESUMEN", "Resumen"),
        ]:
            contenido = next((v for k, v in secciones.items() if clave_busqueda in k.upper()), None)
            if contenido:
                with st.expander(titulo, expanded=True):
                    st.markdown(contenido)


# ──────────── INFORME ────────────
with tab_informe:
    if not informe:
        st.info("Selecciona una semana en el sidebar.")
        st.stop()

    st.markdown(informe.get("analisis", ""))

    st.download_button(
        "Descargar JSON completo",
        data=json.dumps(informe, ensure_ascii=False, indent=2),
        file_name=f"informe-{informe['fecha']}.json",
        mime="application/json",
    )

    msgs = informe.get("mensajes_input", [])
    if msgs:
        st.divider()
        with st.expander(f"Mensajes input ({len(msgs)} mensajes que usó Claude como base)"):
            recurso_filtro = st.text_input("Filtrar por cliente", "", key="msg_filter")
            for m in msgs:
                if recurso_filtro and recurso_filtro.lower() not in m.get("recurso", "").lower():
                    continue
                with st.expander(f"{m.get('recurso', 'Sin nombre')} — {m.get('tipo', '')} ({m.get('fecha', '')})"):
                    st.text(m.get("texto", ""))
