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
        return None
    return round((curr - prev) / prev * 100, 1)


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

tab_overview, tab_clientes, tab_conv, tab_evolucion, tab_alertas, tab_informe = st.tabs([
    "Resumen", "Clientes", "Conversiones", "Evolución", "Alertas", "Informe",
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

    cols_show = [" ", "Cliente"]
    if tiene_metricas:
        cols_show += ["Conv.", "Δ Conv.", "Revenue", "Orgánico", "Δ Org.", "GSC clics", "Δ GSC", "IA"]

    col_config = {
        "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
        "Δ Score": st.column_config.NumberColumn("Δ Score", format="%+d"),
        "Conv.": st.column_config.NumberColumn("Conv."),
        "Δ Conv.": st.column_config.NumberColumn("Δ Conv.", format="%+.1f%%"),
        "Orgánico": st.column_config.NumberColumn("Orgánico"),
        "Δ Org.": st.column_config.NumberColumn("Δ Org.", format="%+.1f%%"),
        "GSC clics": st.column_config.NumberColumn("GSC clics"),
        "Δ GSC": st.column_config.NumberColumn("Δ GSC", format="%+.1f%%"),
        "IA": st.column_config.NumberColumn("IA"),
    }

    delta_cols = [c for c in cols_show if c.startswith("Δ") and c != "Δ Score"]

    def _color_delta(series):
        out = []
        for v in series:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                out.append("")
            elif isinstance(v, (int, float)) and v > 0:
                out.append("color: #22c55e; font-weight: 600")
            elif isinstance(v, (int, float)) and v < 0:
                out.append("color: #ef4444; font-weight: 600")
            else:
                out.append("")
        return out

    df_show = df[cols_show]
    if delta_cols:
        styled = df_show.style.apply(_color_delta, subset=delta_cols)
    else:
        styled = df_show.style

    st.dataframe(styled, use_container_width=True, hide_index=True, column_config=col_config)
    st.caption(f"Mostrando {len(df)} de {len(scores)} clientes")


# ──────────── CONVERSIONES ────────────
with tab_conv:
    if not metricas or "clientes" not in metricas:
        st.info("Sin datos de métricas todavía.")
        st.stop()

    clientes_data = metricas["clientes"]
    st.caption(f"Semana {metricas['fecha_desde']} → {metricas['fecha_hasta']}  vs  semana anterior")

    # Interpretación de Claude si la hay
    if informe:
        secciones = informe.get("secciones", {})
        interp = next(
            (v for k, v in secciones.items() if any(w in k.upper() for w in ("CONVERS", "INSIGHT", "RESUMEN"))),
            None,
        )
        if interp:
            st.info(interp)
        else:
            analisis = informe.get("analisis", "")
            # Extraer párrafos que mencionan conversiones
            parrafos = [p for p in analisis.split("\n") if "convers" in p.lower() or "revenue" in p.lower() or "lead" in p.lower()]
            if parrafos:
                st.info("\n".join(parrafos[:5]))

    st.markdown("**Nota:** El volumen esperado de conversiones depende del sector. Un arquitecto puede tener 2-3 leads de alto valor; una clínica dental puede tener 20-30 citas. Compara siempre contra semanas anteriores del mismo cliente, no entre clientes.")

    st.divider()

    # Datos por cliente
    rows_conv = []
    for c, d in clientes_data.items():
        ke = d.get("key_events", {})
        ke_prev = d.get("key_events_prev", {})
        total = sum(ke.values())
        total_prev = sum(ke_prev.values())
        rows_conv.append({
            "Cliente": c,
            "Conversiones": total,
            "Semana anterior": total_prev,
            "Δ": pct(total, total_prev),
            "Revenue (€)": d.get("revenue", 0) or 0,
            "Eventos": ", ".join(f"{k}: {v}" for k, v in ke.items()) if ke else "—",
            "GA4": "✓" if d.get("ga4_ok") else "✗",
        })

    df_conv = pd.DataFrame(rows_conv).sort_values("Conversiones", ascending=False)

    # Alertas: clientes con GA4 ok pero sin conversiones
    sin_conv = df_conv[(df_conv["GA4"] == "✓") & (df_conv["Conversiones"] == 0)]
    if not sin_conv.empty:
        nombres = ", ".join(sin_conv["Cliente"].tolist())
        st.warning(f"Clientes con GA4 activo pero sin conversiones esta semana: **{nombres}**")

    # Gráfico barras apiladas por tipo de evento
    # Recopilar todos los nombres de evento distintos
    all_events = sorted({
        ev
        for d in clientes_data.values()
        for ev in d.get("key_events", {}).keys()
    })

    clientes_con_conv = [c for c, d in clientes_data.items() if sum(d.get("key_events", {}).values()) > 0]
    # Ordenar por total conversiones desc (invertido para barras horizontales)
    clientes_con_conv.sort(key=lambda c: sum(clientes_data[c].get("key_events", {}).values()))

    if clientes_con_conv and all_events:
        fig = go.Figure()
        colores_ev = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444",
                      "#06b6d4", "#84cc16", "#f97316", "#ec4899", "#6366f1"]
        for i, ev in enumerate(all_events):
            valores = [clientes_data[c].get("key_events", {}).get(ev, 0) for c in clientes_con_conv]
            fig.add_trace(go.Bar(
                y=clientes_con_conv,
                x=valores,
                name=ev,
                orientation="h",
                marker_color=colores_ev[i % len(colores_ev)],
                text=[str(v) if v > 0 else "" for v in valores],
                textposition="inside",
            ))
        fig.update_layout(
            barmode="stack",
            height=max(300, len(clientes_con_conv) * 40),
            margin=dict(t=10, b=10, l=10, r=10),
            xaxis_title="Conversiones",
            yaxis_title="",
            legend=dict(orientation="h", y=1.08),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Tabla completa con desglose de eventos y delta coloreado
    def _color_conv_delta(series):
        out = []
        for v in series:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                out.append("")
            elif isinstance(v, (int, float)) and v > 0:
                out.append("color: #22c55e; font-weight: 600")
            elif isinstance(v, (int, float)) and v < 0:
                out.append("color: #ef4444; font-weight: 600")
            else:
                out.append("")
        return out

    hay_revenue = df_conv["Revenue (€)"].gt(0).any()
    cols_tbl = ["Cliente", "Conversiones", "Semana anterior", "Δ", "Eventos", "GA4"]
    if hay_revenue:
        cols_tbl.insert(4, "Revenue (€)")

    col_cfg = {
        "Conversiones": st.column_config.NumberColumn("Conv. esta semana"),
        "Semana anterior": st.column_config.NumberColumn("Semana anterior"),
        "Δ": st.column_config.NumberColumn("Δ %", format="%+.1f%%"),
        "Eventos": st.column_config.TextColumn("Desglose eventos", width="large"),
    }
    if hay_revenue:
        col_cfg["Revenue (€)"] = st.column_config.NumberColumn("Revenue (€)", format="%.0f €")

    def _color_conv_total(series):
        out = []
        for cliente, v in zip(df_conv["Cliente"], series):
            prev = df_conv.loc[df_conv["Cliente"] == cliente, "Semana anterior"].values[0]
            if v > prev:
                out.append("color: #22c55e; font-weight: 600")
            elif v < prev:
                out.append("color: #ef4444; font-weight: 600")
            else:
                out.append("")
        return out

    df_tbl = df_conv[cols_tbl].reset_index(drop=True)
    styled_conv = (
        df_tbl.style
        .apply(_color_conv_delta, subset=["Δ"])
        .apply(_color_conv_total, subset=["Conversiones"])
    )
    st.dataframe(styled_conv, use_container_width=True, hide_index=True, column_config=col_cfg)


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
