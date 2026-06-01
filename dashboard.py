"""
Dashboard semanal SEO — La Fábrica del SEO
Lee informes y scores generados por asana_agent y los muestra de forma visual.
"""
import os
import json
import re
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px
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
# UI helpers
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

def evolucion_emoji(actual, anterior):
    if actual is None or anterior is None:
        return "—"
    diff = actual - anterior
    if diff > 0:
        return f"↑ +{diff}"
    if diff < 0:
        return f"↓ {diff}"
    return "="

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
    st.title("📊 Dashboard SEO")
    st.caption("La Fábrica del SEO")
    informes = listar_informes()
    if informes:
        fecha_sel = st.selectbox("Semana del informe", informes, index=0,
                                 format_func=lambda f: datetime.strptime(f, "%Y-%m-%d").strftime("%d %b %Y"))
    else:
        fecha_sel = None
        st.warning("Aún no hay informes en el bucket.")
    if st.button("🔄 Refrescar datos", use_container_width=True):
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
    st.error("No hay datos disponibles. Espera al próximo lunes o lanza manualmente el asana_agent.")
    st.stop()

# ──────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────

tab_overview, tab_salud, tab_evolucion, tab_ga4, tab_gsc, tab_ia, tab_alertas, tab_informe, tab_mensajes = st.tabs([
    "🏥 Resumen", "👥 Salud clientes", "📈 Evolución",
    "📊 GA4", "🔍 GSC", "🤖 IA Traffic",
    "🚨 Alertas", "📄 Informe completo", "💬 Mensajes input",
])

# ──────────── RESUMEN ────────────
with tab_overview:
    if informe:
        st.subheader(f"Informe semanal · {informe['fecha_desde']} → {informe['fecha_hasta']}")

        scores = informe.get("scores", {})
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Proyectos analizados", informe.get("num_mensajes", 0))
        with col2:
            n_sanos = sum(1 for s in scores.values() if s >= 80)
            st.metric("🟢 Sanos (80+)", n_sanos)
        with col3:
            n_atencion = sum(1 for s in scores.values() if 50 <= s < 80)
            st.metric("🟡 Atención (50-79)", n_atencion)
        with col4:
            n_criticos = sum(1 for s in scores.values() if s < 50)
            st.metric("🔴 Críticos (<50)", n_criticos)

        st.divider()

        if scores:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown("##### Distribución de scores")
                df_dist = pd.DataFrame({
                    "Estado": ["🟢 Sanos", "🟡 Atención", "🔴 Críticos"],
                    "Clientes": [n_sanos, n_atencion, n_criticos],
                })
                fig = px.pie(df_dist, names="Estado", values="Clientes",
                             color="Estado",
                             color_discrete_map={"🟢 Sanos": "#22c55e", "🟡 Atención": "#eab308", "🔴 Críticos": "#ef4444"})
                fig.update_traces(textinfo="value+label")
                fig.update_layout(showlegend=False, height=340, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("##### Score medio por estado")
                if scores:
                    df_scores = pd.DataFrame([{"Cliente": k, "Score": v} for k, v in scores.items()])
                    fig2 = px.histogram(df_scores, x="Score", nbins=20)
                    fig2.update_layout(height=340, margin=dict(t=10, b=10, l=10, r=10),
                                       xaxis_title="Score", yaxis_title="Nº clientes",
                                       bargap=0.1)
                    fig2.update_traces(marker_color="#3b82f6")
                    st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Selecciona un informe en el sidebar.")

# ──────────── SALUD ────────────
with tab_salud:
    if informe:
        scores = informe.get("scores", {})
        # Última semana anterior con datos
        fechas_hist = sorted(historico.keys())
        idx_actual = fechas_hist.index(informe["fecha"]) if informe["fecha"] in fechas_hist else len(fechas_hist) - 1
        scores_anteriores = historico[fechas_hist[idx_actual - 1]] if idx_actual > 0 else {}

        filas = []
        for cliente, score in scores.items():
            anterior = scores_anteriores.get(cliente)
            filas.append({
                "Estado": color_score(score),
                "Cliente": cliente,
                "Score": score,
                "Evolución": evolucion_emoji(score, anterior),
                "Semana anterior": anterior if anterior is not None else "—",
                "Categoría": estado_score(score),
            })

        df = pd.DataFrame(filas).sort_values("Score", ascending=False)

        # Filtros
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            busca = st.text_input("🔍 Buscar cliente", "")
        with col2:
            cat = st.multiselect("Categoría", ["Sano", "Atención", "Crítico", "Sin dato"], default=[])
        with col3:
            orden = st.selectbox("Ordenar por", ["Score ↓", "Score ↑", "Nombre A→Z"])

        if busca:
            df = df[df["Cliente"].str.contains(busca, case=False, na=False)]
        if cat:
            df = df[df["Categoría"].isin(cat)]
        if orden == "Score ↑":
            df = df.sort_values("Score", ascending=True)
        elif orden == "Nombre A→Z":
            df = df.sort_values("Cliente")

        st.dataframe(
            df[["Estado", "Cliente", "Score", "Evolución", "Semana anterior"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            },
        )
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
                "Clientes a comparar",
                todos_clientes,
                default=todos_clientes[:5] if len(todos_clientes) > 5 else todos_clientes,
            )
        with col2:
            n_semanas = st.slider("Últimas N semanas", 2, 20, min(8, len(historico)))

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
            fig = px.line(df, x="Fecha", y="Score", color="Cliente", markers=True)
            fig.update_layout(
                height=500,
                hovermode="x unified",
                yaxis=dict(range=[0, 100], title="Score"),
                xaxis_title="",
                margin=dict(t=30, b=10, l=10, r=10),
            )
            fig.add_hline(y=80, line_dash="dash", line_color="#22c55e", opacity=0.4, annotation_text="Sano")
            fig.add_hline(y=50, line_dash="dash", line_color="#ef4444", opacity=0.4, annotation_text="Crítico")
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.markdown("##### Heatmap de scores (todas las semanas)")
        df_full = pd.DataFrame(historico).T
        df_full.index = pd.to_datetime(df_full.index).strftime("%d %b")
        if not df_full.empty:
            fig_hm = go.Figure(data=go.Heatmap(
                z=df_full.T.values,
                x=df_full.index,
                y=df_full.columns,
                colorscale=[[0, "#ef4444"], [0.5, "#eab308"], [1, "#22c55e"]],
                zmin=0, zmax=100,
                hovertemplate="%{y}<br>%{x}<br>Score: %{z}<extra></extra>",
            ))
            fig_hm.update_layout(height=max(400, 15 * len(df_full.columns)),
                                 margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig_hm, use_container_width=True)

# ──────────── GA4 ────────────
with tab_ga4:
    if not metricas:
        st.info("Sin datos de métricas todavía. Se generan automáticamente cada lunes al ejecutar el progress_agent.")
    else:
        clientes_data = metricas["clientes"]
        st.caption(f"Semana {metricas['fecha_desde']} → {metricas['fecha_hasta']}  vs  {metricas['fecha_prev_desde']} → {metricas['fecha_prev_hasta']}")

        metrica_sel = st.radio("Métrica", ["Sesiones orgánicas", "Sesiones directas", "Revenue (€)"], horizontal=True)
        top_n = st.slider("Top N clientes", 5, len(clientes_data), min(20, len(clientes_data)), key="ga4_topn")

        if metrica_sel == "Sesiones orgánicas":
            key, key_p = "organic_sessions", "organic_sessions_prev"
        elif metrica_sel == "Sesiones directas":
            key, key_p = "direct_sessions", "direct_sessions_prev"
        else:
            key, key_p = "revenue", "revenue_prev"

        filas = sorted(
            [{"Cliente": c, "Actual": d[key], "Anterior": d[key_p]} for c, d in clientes_data.items()],
            key=lambda x: x["Actual"], reverse=True
        )[:top_n]

        df_bar = pd.DataFrame(filas)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=df_bar["Cliente"], x=df_bar["Anterior"], name="Semana anterior",
                             orientation="h", marker_color="#94a3b8"))
        fig.add_trace(go.Bar(y=df_bar["Cliente"], x=df_bar["Actual"], name="Semana actual",
                             orientation="h", marker_color="#3b82f6"))
        fig.update_layout(barmode="overlay", height=max(350, top_n * 28),
                          margin=dict(t=20, b=10, l=10, r=10),
                          xaxis_title=metrica_sel, yaxis_title="",
                          legend=dict(orientation="h", y=1.05))
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.markdown("##### Tabla completa")
        rows = []
        for c, d in clientes_data.items():
            rows.append({
                "Cliente": c,
                "Orgánico": d["organic_sessions"],
                "Org. ant.": d["organic_sessions_prev"],
                "Δ Org.": pct(d["organic_sessions"], d["organic_sessions_prev"]),
                "Directo": d["direct_sessions"],
                "Dir. ant.": d["direct_sessions_prev"],
                "Δ Dir.": pct(d["direct_sessions"], d["direct_sessions_prev"]),
                "Revenue": f"{d['revenue']:.2f}€" if d["revenue"] else "—",
                "GA4": "✓" if d["ga4_ok"] else "✗",
            })
        df_tbl = pd.DataFrame(rows).sort_values("Orgánico", ascending=False)
        busca_ga4 = st.text_input("🔍 Filtrar cliente", "", key="ga4_busca")
        if busca_ga4:
            df_tbl = df_tbl[df_tbl["Cliente"].str.contains(busca_ga4, case=False, na=False)]
        st.dataframe(df_tbl, use_container_width=True, hide_index=True)

# ──────────── GSC ────────────
with tab_gsc:
    if not metricas:
        st.info("Sin datos de métricas todavía.")
    else:
        clientes_data = metricas["clientes"]
        st.caption(f"Semana {metricas['fecha_desde']} → {metricas['fecha_hasta']}")

        top_n_gsc = st.slider("Top N clientes por clics", 5, len(clientes_data), min(20, len(clientes_data)), key="gsc_topn")

        filas_gsc = sorted(
            [{"Cliente": c, "Clics": d["gsc_clicks"], "Clics ant.": d["gsc_clicks_prev"],
              "Impresiones": d["gsc_impressions"], "CTR": d["gsc_ctr"], "Posición": d["gsc_position"]}
             for c, d in clientes_data.items()],
            key=lambda x: x["Clics"], reverse=True
        )[:top_n_gsc]

        df_gsc = pd.DataFrame(filas_gsc)
        col1, col2 = st.columns(2)
        with col1:
            fig_clics = go.Figure()
            fig_clics.add_trace(go.Bar(y=df_gsc["Cliente"], x=df_gsc["Clics ant."], name="Ant.",
                                       orientation="h", marker_color="#94a3b8"))
            fig_clics.add_trace(go.Bar(y=df_gsc["Cliente"], x=df_gsc["Clics"], name="Actual",
                                       orientation="h", marker_color="#10b981"))
            fig_clics.update_layout(barmode="overlay", height=max(350, top_n_gsc * 28),
                                    margin=dict(t=20, b=10, l=10, r=10),
                                    xaxis_title="Clics GSC", yaxis_title="",
                                    legend=dict(orientation="h", y=1.05))
            st.plotly_chart(fig_clics, use_container_width=True)

        with col2:
            scatter_data = [
                {"Cliente": c, "CTR": d["gsc_ctr"], "Posición": d["gsc_position"],
                 "Impresiones": max(d["gsc_impressions"], 1)}
                for c, d in clientes_data.items()
                if d["gsc_impressions"] > 0
            ]
            if scatter_data:
                df_sc = pd.DataFrame(scatter_data)
                fig_sc = px.scatter(df_sc, x="Posición", y="CTR", size="Impresiones",
                                    hover_name="Cliente", color="CTR",
                                    color_continuous_scale="RdYlGn",
                                    title="CTR vs Posición (tamaño = impresiones)")
                fig_sc.update_xaxes(autorange="reversed")
                fig_sc.update_layout(height=max(350, top_n_gsc * 28),
                                     margin=dict(t=40, b=10, l=10, r=10),
                                     coloraxis_showscale=False)
                st.plotly_chart(fig_sc, use_container_width=True)

        st.divider()
        st.markdown("##### Tabla completa GSC")
        rows_gsc = []
        for c, d in clientes_data.items():
            rows_gsc.append({
                "Cliente": c,
                "Clics": d["gsc_clicks"],
                "Δ Clics": pct(d["gsc_clicks"], d["gsc_clicks_prev"]),
                "Impresiones": d["gsc_impressions"],
                "Δ Impr.": pct(d["gsc_impressions"], d["gsc_impressions_prev"]),
                "CTR": f"{d['gsc_ctr']}%",
                "Posición": d["gsc_position"],
            })
        df_gsc_tbl = pd.DataFrame(rows_gsc).sort_values("Clics", ascending=False)
        busca_gsc = st.text_input("🔍 Filtrar cliente", "", key="gsc_busca")
        if busca_gsc:
            df_gsc_tbl = df_gsc_tbl[df_gsc_tbl["Cliente"].str.contains(busca_gsc, case=False, na=False)]
        st.dataframe(df_gsc_tbl, use_container_width=True, hide_index=True)

# ──────────── IA TRAFFIC ────────────
with tab_ia:
    if not metricas:
        st.info("Sin datos de métricas todavía.")
    else:
        clientes_data = metricas["clientes"]
        st.caption(f"Semana {metricas['fecha_desde']} → {metricas['fecha_hasta']}")

        llm_sources = ["ChatGPT", "Gemini", "Claude", "Copilot", "Perplexity"]
        llm_colors = {"ChatGPT": "#10a37f", "Gemini": "#4285f4", "Claude": "#d97706",
                      "Copilot": "#0078d4", "Perplexity": "#6366f1"}

        rows_ia = []
        for c, d in clientes_data.items():
            total = sum(d["llm"].values())
            if total > 0:
                row = {"Cliente": c, "Total": total}
                row.update(d["llm"])
                rows_ia.append(row)

        if not rows_ia:
            st.info("Ningún cliente tiene tráfico IA registrado esta semana.")
        else:
            df_ia = pd.DataFrame(rows_ia).sort_values("Total", ascending=False)

            fig_ia = go.Figure()
            for src in llm_sources:
                if src in df_ia.columns:
                    fig_ia.add_trace(go.Bar(
                        y=df_ia["Cliente"], x=df_ia[src], name=src,
                        orientation="h", marker_color=llm_colors[src]
                    ))
            fig_ia.update_layout(
                barmode="stack",
                height=max(300, len(df_ia) * 32),
                margin=dict(t=20, b=10, l=10, r=10),
                xaxis_title="Sesiones desde IA", yaxis_title="",
                legend=dict(orientation="h", y=1.05),
            )
            st.plotly_chart(fig_ia, use_container_width=True)

            st.divider()
            st.markdown("##### Comparativa semana anterior")
            rows_ia_cmp = []
            for c, d in clientes_data.items():
                total_curr = sum(d["llm"].values())
                total_prev = sum(d["llm_prev"].values())
                if total_curr > 0 or total_prev > 0:
                    row = {"Cliente": c, "Total": total_curr, "Anterior": total_prev,
                           "Δ": pct(total_curr, total_prev)}
                    for src in llm_sources:
                        row[src] = d["llm"].get(src, 0)
                    rows_ia_cmp.append(row)
            df_ia_cmp = pd.DataFrame(rows_ia_cmp).sort_values("Total", ascending=False)
            st.dataframe(df_ia_cmp, use_container_width=True, hide_index=True)

# ──────────── ALERTAS ────────────
with tab_alertas:
    if informe:
        secciones = informe.get("secciones", {})
        for clave_busqueda, titulo, icono in [
            ("ALERTA", "Alertas críticas", "🚨"),
            ("REPORTING", "Reporting incompleto", "📋"),
            ("PROBLEMA", "Problemas internos", "⚠️"),
            ("INSIGHT", "Insights y patrones", "💡"),
        ]:
            contenido = next((v for k, v in secciones.items() if clave_busqueda in k.upper()), None)
            if contenido:
                with st.expander(f"{icono} {titulo}", expanded=clave_busqueda == "ALERTA"):
                    st.markdown(contenido)

# ──────────── INFORME ────────────
with tab_informe:
    if informe:
        st.markdown(informe.get("analisis", ""))
        st.download_button(
            "⬇️ Descargar JSON completo",
            data=json.dumps(informe, ensure_ascii=False, indent=2),
            file_name=f"informe-{informe['fecha']}.json",
            mime="application/json",
        )

# ──────────── MENSAJES INPUT ────────────
with tab_mensajes:
    if informe:
        msgs = informe.get("mensajes_input", [])
        st.caption(f"{len(msgs)} mensajes que Claude usó como input para generar el informe")
        recurso_filtro = st.text_input("🔍 Filtrar por cliente", "", key="msg_filter")
        for m in msgs:
            if recurso_filtro and recurso_filtro.lower() not in m.get("recurso", "").lower():
                continue
            with st.expander(f"📌 {m.get('recurso', 'Sin nombre')} — {m.get('tipo', '')} ({m.get('fecha', '')})"):
                st.text(m.get("texto", ""))
