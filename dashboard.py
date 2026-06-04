"""
Dashboard semanal SEO — La Fábrica del SEO
"""
import os
import json
import re
import unicodedata
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
    initial_sidebar_state="collapsed",
)

# ── Auth simple (DESACTIVADA temporalmente — reactivar cuando la herramienta esté lista) ──
# if "password" in st.secrets:
#     pwd = st.text_input("Contraseña", type="password")
#     if pwd != st.secrets["password"]:
#         st.stop()


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
def cargar_consultores():
    """Mapa {cliente: consultor} desde consultores.json en el bucket. {} si no existe."""
    blob = _client().bucket(BUCKET).blob("consultores.json")
    if not blob.exists():
        return {}
    return json.loads(blob.download_as_text())

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

def org_pct_cliente(metricas, cliente):
    """% de variación de sesiones orgánicas de un cliente, o None."""
    if not metricas or "clientes" not in metricas:
        return None
    d = metricas["clientes"].get(cliente)
    if not d:
        return None
    return pct(d.get("organic_sessions", 0), d.get("organic_sessions_prev", 0))

def _norm_cliente(s):
    """Normaliza un nombre de cliente: sin tildes, sin 'seo/+/**', solo alfanumérico."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("seo", "")
    return re.sub(r"[^a-z0-9]", "", s)

def consultor_de(cliente, consultores_norm):
    """Devuelve el consultor de un cliente usando match normalizado + contains."""
    nc = _norm_cliente(cliente)
    if not nc:
        return "Sin asignar"
    if nc in consultores_norm:
        return consultores_norm[nc]
    for k, v in consultores_norm.items():
        if len(k) >= 4 and len(nc) >= 4 and (k in nc or nc in k):
            return v
    return "Sin asignar"

def tarjeta_score_html(cliente, score, prev):
    """Tarjeta compacta de score para un cliente."""
    color = "#ef4444" if score < 50 else ("#eab308" if score < 80 else "#22c55e")
    bg = "#fef2f2" if score < 50 else ("#fffbeb" if score < 80 else "#f0fdf4")
    estado = estado_score(score)
    dl = delta_score(score, prev)
    if dl is None:
        delta_html = '<span style="color:#94a3b8;font-size:0.85rem">nuevo</span>'
    elif dl > 0:
        delta_html = f'<span style="color:#16a34a;font-weight:700;font-size:0.9rem">▲ +{dl}</span>'
    elif dl < 0:
        delta_html = f'<span style="color:#dc2626;font-weight:700;font-size:0.9rem">▼ {dl}</span>'
    else:
        delta_html = '<span style="color:#94a3b8;font-size:0.9rem">±0</span>'
    fill = max(0, min(100, score))
    return (
        f'<div style="background:{bg};border:1px solid #e5e7eb;border-radius:10px;'
        f'padding:12px 14px;margin-bottom:10px">'
        f'<div style="font-weight:600;color:#0f172a;font-size:0.95rem;margin-bottom:6px">{cliente}</div>'
        f'<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:8px">'
        f'<span style="font-size:1.9rem;font-weight:800;color:{color};line-height:1">{score}</span>'
        f'{delta_html}'
        f'<span style="margin-left:auto;font-size:0.7rem;text-transform:uppercase;'
        f'letter-spacing:.4px;color:{color};font-weight:700">{estado}</span>'
        f'</div>'
        f'<div style="background:#e5e7eb;border-radius:6px;height:8px;overflow:hidden">'
        f'<div style="width:{fill}%;background:{color};height:100%"></div>'
        f'</div>'
        f'</div>'
    )

def html_score_cards(clientes, scores, scores_ant):
    """Concatena las tarjetas de score de varios clientes (mejor a peor)."""
    cs = sorted(clientes, key=lambda c: scores[c], reverse=True)
    return "".join(tarjeta_score_html(c, scores[c], scores_ant.get(c)) for c in cs)

def fig_evolucion(clientes, historico, fechas_ord):
    """Line chart de evolución de score para un conjunto de clientes."""
    fig = go.Figure()
    for cliente in sorted(clientes):
        xs, ys = [], []
        for f in fechas_ord:
            v = historico[f].get(cliente)
            if v is not None:
                xs.append(f)
                ys.append(v)
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=cliente))
    fig.add_hline(y=80, line_dash="dash", line_color="#22c55e", opacity=0.4, annotation_text="Sano")
    fig.add_hline(y=50, line_dash="dash", line_color="#ef4444", opacity=0.4, annotation_text="Crítico")
    fig.update_layout(
        height=420, hovermode="x unified",
        yaxis=dict(range=[0, 100], title="Score"), xaxis_title="",
        margin=dict(t=20, b=10, l=10, r=10),
        legend=dict(orientation="h", y=-0.15),
    )
    return fig

def html_stats_consultor(clientes, scores):
    """Línea-resumen de un consultor: score medio, nº críticos y en atención."""
    vals = [scores[c] for c in clientes if c in scores]
    if not vals:
        return ""
    medio = round(sum(vals) / len(vals))
    crit = sum(1 for v in vals if v < 50)
    aten = sum(1 for v in vals if 50 <= v < 80)
    sanos = sum(1 for v in vals if v >= 80)
    color = "#ef4444" if medio < 50 else ("#eab308" if medio < 80 else "#22c55e")
    return (
        '<div style="font-size:0.85rem;color:#475569;margin:2px 0 12px 0">'
        f'Score medio <b style="color:{color};font-size:1.0rem">{medio}</b>'
        f'&nbsp;·&nbsp;<span style="color:#16a34a">🟢 {sanos}</span>'
        f'&nbsp;<span style="color:#b45309">🟡 {aten}</span>'
        f'&nbsp;<span style="color:#dc2626">🔴 {crit}</span>'
        '</div>'
    )

# ── Color por consultor (reutilizado en varias tabs) ──────────────
_PALETA_CONS = [
    ("#dbeafe", "#1e40af"),  # azul
    ("#fae8ff", "#86198f"),  # fucsia
    ("#fef3c7", "#92400e"),  # ámbar
    ("#ffe4e6", "#9f1239"),  # rosa
    ("#cffafe", "#155e75"),  # cian
]
_COLOR_CONS_FIJO = {
    "Javier": ("#ff00ff", "#ffffff"),  # CMYK 0/100/0/0 — magenta
    "Tania": ("#33cc80", "#ffffff"),   # CMYK 80/20/50/0 — verde
}

def color_consultor(cons):
    """(fondo, texto) para un consultor. Fijos para Tania/Javier, resto automático."""
    if not cons or cons in ("Sin asignar", "General"):
        return ("#f1f5f9", "#64748b")
    if cons in _COLOR_CONS_FIJO:
        return _COLOR_CONS_FIJO[cons]
    return _PALETA_CONS[sum(map(ord, cons)) % len(_PALETA_CONS)]

def badge_consultor_html(cons):
    bg, fg = color_consultor(cons)
    nombre = cons if cons and cons != "Sin asignar" else "Sin asignar"
    return (f'<span style="background:{bg};color:{fg};border-radius:6px;'
            f'padding:1px 8px;font-size:0.78rem;font-weight:600;margin-left:8px">👤 {nombre}</span>')

def header_consultor_html(cons, n=None):
    bg, fg = color_consultor(cons)
    return (f'<div style="background:{bg};color:{fg};border-radius:8px;'
            f'padding:6px 12px;font-weight:700;display:inline-block;margin-bottom:8px">'
            f'👤 {cons}</div>')

def tarjeta_html(fondo, borde, etiqueta, nombre, lineas):
    """Tarjeta-destacado para la portada del Resumen."""
    cuerpo = "".join(
        f'<div style="font-size:0.85rem;color:#475569;margin-top:3px">{l}</div>'
        for l in lineas
    )
    return (
        f'<div style="background:{fondo};border-left:5px solid {borde};'
        f'border-radius:10px;padding:16px 18px;min-height:140px">'
        f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.5px;'
        f'color:{borde};font-weight:700">{etiqueta}</div>'
        f'<div style="font-size:1.2rem;font-weight:700;color:#0f172a;margin-top:6px">{nombre}</div>'
        f'{cuerpo}</div>'
    )


# ──────────────────────────────────────────────
# Cabecera (barra superior, sin sidebar)
# ──────────────────────────────────────────────

head_l, head_c, head_r = st.columns([3, 2, 1])
with head_l:
    st.title("Dashboard SEO")
    st.caption("La Fábrica del SEO")
informes = listar_informes()
with head_c:
    if informes:
        fecha_sel = st.selectbox(
            "Semana del informe", informes, index=0,
            format_func=lambda f: datetime.strptime(f, "%Y-%m-%d").strftime("%d %b %Y"),
        )
    else:
        fecha_sel = None
        st.warning("Aún no hay informes en el bucket.")
with head_r:
    st.write("")
    st.write("")
    if st.button("🔄 Refrescar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ──────────────────────────────────────────────
# Carga datos
# ──────────────────────────────────────────────

informe = cargar_informe(fecha_sel) if fecha_sel else None
historico = cargar_scores_historicos()
metricas = cargar_metricas(fecha_sel) if fecha_sel else cargar_metricas()

# Asignación cliente → consultor (global, usado por varias tabs)
consultores_map = cargar_consultores()
consultores_norm = {_norm_cliente(k): v for k, v in consultores_map.items()}
hay_consultores = bool(consultores_map)

def consultor(cliente):
    return consultor_de(cliente, consultores_norm)

if not informe and not historico and not metricas:
    st.error("No hay datos disponibles. Espera al próximo lunes o lanza manualmente el agente.")
    st.stop()

# Aviso si hay clientes del informe sin consultor asignado
if hay_consultores and informe:
    sin_asignar = [c for c in informe.get("scores", {}) if consultor(c) == "Sin asignar"]
    if sin_asignar:
        st.warning(
            "⚠️ **" + str(len(sin_asignar)) + " cliente(s) sin consultor asignado:** "
            + ", ".join(sin_asignar)
            + ".  Añádelos a `consultores.json` para que aparezcan en la columna correcta."
        )


# ──────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────

tab_overview, tab_clientes, tab_conv, tab_evolucion, tab_alertas, tab_informe = st.tabs([
    "Resumen", "Clientes", "Conversiones", "Evolución", "Alertas", "Informe",
])


# ──────────── RESUMEN ────────────
with tab_overview:
    if not informe:
        st.info("Selecciona una semana arriba.")
        st.stop()

    scores = informe.get("scores", {})

    # Scores semana anterior
    fechas_hist = sorted(historico.keys())
    idx_actual = fechas_hist.index(informe["fecha"]) if informe["fecha"] in fechas_hist else len(fechas_hist) - 1
    scores_ant = historico[fechas_hist[idx_actual - 1]] if idx_actual > 0 else {}

    # Tareas accionables para Asana — clientes que necesitan revisión
    tareas = []
    for c in sorted(scores, key=scores.get):  # peor score primero
        s = scores[c]
        dl = delta_score(s, scores_ant.get(c))
        motivos = []
        if s < 50:
            motivos.append("crítico")
        if dl is not None and dl < 0:
            motivos.append(f"{dl:+d} pts")
        if metricas and "clientes" in metricas:
            d = metricas["clientes"].get(c)
            if d and d.get("ga4_ok") and sum(d.get("key_events", {}).values()) == 0:
                motivos.append("0 conversiones")
        if motivos:
            tareas.append((c, motivos, consultor(c)))

    try:
        fecha_fmt = datetime.strptime(informe["fecha"], "%Y-%m-%d").strftime("%d %b %Y")
    except Exception:
        fecha_fmt = informe.get("fecha", "")

    if tareas:
        items = "".join(
            f'<li style="margin-bottom:8px;line-height:1.6">Revisar '
            f'<strong style="color:#0f172a">{c}</strong>'
            f'<span style="color:#94a3b8;font-size:0.9rem"> — {", ".join(m)}</span>'
            f'{badge_consultor_html(cons)}</li>'
            for c, m, cons in tareas
        )
        cuerpo = f'<ul style="margin:0;padding-left:20px;color:#334155;font-size:1.0rem">{items}</ul>'
    else:
        cuerpo = '<div style="color:#16a34a;font-size:1.0rem">✓ Sin tareas pendientes esta semana</div>'

    st.markdown(
        '<div style="background:linear-gradient(180deg,#f8fafc,#eef2ff);'
        'border:1px solid #e2e8f0;border-left:5px solid #2563eb;border-radius:12px;'
        'padding:18px 22px;margin-bottom:4px">'
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">'
        '<span style="font-size:1.05rem">📋</span>'
        '<span style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.6px;'
        'color:#2563eb;font-weight:700">Tareas que añadir a Asana esta semana</span>'
        f'<span style="font-size:0.74rem;color:#94a3b8;margin-left:auto">{fecha_fmt}</span>'
        '</div>'
        f'{cuerpo}'
        '</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Portada escaneable: 3 destacados de la semana ──────────────
    n_sanos = sum(1 for s in scores.values() if s >= 80)
    n_atencion = sum(1 for s in scores.values() if 50 <= s < 80)
    n_criticos = sum(1 for s in scores.values() if s < 50)

    # Destacados automáticos
    peor_cliente = min(scores, key=scores.get) if scores else None
    deltas_validos = {
        c: delta_score(scores[c], scores_ant.get(c))
        for c in scores
        if delta_score(scores[c], scores_ant.get(c)) is not None
    }
    candidatos_mejor = {c: d for c, d in deltas_validos.items() if c != peor_cliente}
    if candidatos_mejor:
        mejor_cliente = max(candidatos_mejor, key=candidatos_mejor.get)
    elif scores:
        mejor_cliente = max(
            (c for c in scores if c != peor_cliente), key=scores.get, default=peor_cliente
        )
    else:
        mejor_cliente = None

    col_a, col_b, col_c = st.columns([1.1, 1, 1.1])

    # Necesita atención (peor score)
    with col_a:
        if peor_cliente:
            ps = scores[peor_cliente]
            pdl = delta_score(ps, scores_ant.get(peor_cliente))
            po = org_pct_cliente(metricas, peor_cliente)
            lineas = [f"Score <b>{ps}</b> · {estado_score(ps)}"]
            if pdl is not None:
                lineas.append(f"{'▼' if pdl < 0 else '▲'} {pdl:+d} pts vs semana anterior")
            if po is not None:
                lineas.append(f"Tráfico orgánico {po:+.1f}%")
            nombre_a = f"{peor_cliente} {badge_consultor_html(consultor(peor_cliente))}"
            st.markdown(
                tarjeta_html("#fef2f2", "#ef4444", "⚠️ Necesita atención", nombre_a, lineas),
                unsafe_allow_html=True,
            )

    # Salud de la cartera (donut)
    with col_b:
        fig_d = go.Figure(go.Pie(
            values=[n_sanos, n_atencion, n_criticos],
            labels=["Sanos", "Atención", "Críticos"],
            marker_colors=["#22c55e", "#eab308", "#ef4444"],
            hole=0.62, sort=False, textinfo="value",
            hovertemplate="%{label}: %{value}<extra></extra>",
        ))
        fig_d.update_layout(
            height=190, showlegend=False,
            margin=dict(t=34, b=0, l=0, r=0),
            annotations=[dict(text=f"<b>{len(scores)}</b><br>clientes", x=0.5, y=0.5,
                              font_size=15, showarrow=False)],
            title=dict(text="Salud de la cartera", x=0.0, y=0.98, font=dict(size=14)),
        )
        st.plotly_chart(fig_d, use_container_width=True, config={"displayModeBar": False})

    # Mejor evolución (mayor Δ score)
    with col_c:
        if mejor_cliente:
            ms = scores[mejor_cliente]
            mdl = delta_score(ms, scores_ant.get(mejor_cliente))
            mo = org_pct_cliente(metricas, mejor_cliente)
            lineas = [f"Score <b>{ms}</b> · {estado_score(ms)}"]
            if mdl is not None:
                lineas.append(f"{'▲' if mdl >= 0 else '▼'} {mdl:+d} pts vs semana anterior")
            if mo is not None:
                lineas.append(f"Tráfico orgánico {mo:+.1f}%")
            nombre_c = f"{mejor_cliente} {badge_consultor_html(consultor(mejor_cliente))}"
            st.markdown(
                tarjeta_html("#f0fdf4", "#22c55e", "🚀 Mejor evolución", nombre_c, lineas),
                unsafe_allow_html=True,
            )

    # Tira compacta de conversiones (si hay métricas)
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
        nombres_sin_conv = [
            c for c, d in metricas["clientes"].items()
            if sum(d.get("key_events", {}).values()) == 0 and d.get("ga4_ok")
        ]
        clientes_sin_conv = len(nombres_sin_conv)

        st.divider()
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
        with c1:
            delta_conv = int(total_conv - total_conv_prev) if total_conv_prev else None
            st.metric("Conversiones (total)", total_conv, delta=delta_conv)
        with c2:
            if total_rev:
                delta_rev = round(total_rev - total_rev_prev, 2) if total_rev_prev else None
                st.metric("Revenue total", f"{total_rev:,.0f} €",
                          delta=f"{delta_rev:+.0f} €" if delta_rev is not None else None)
            else:
                st.metric("Revenue total", "—")
        with c3:
            st.metric("Clientes sin conversiones", clientes_sin_conv,
                      delta_color="inverse",
                      help="Clientes con GA4 OK pero 0 conversiones registradas esta semana")
        with c4:
            if nombres_sin_conv:
                chips = "".join(
                    f'<span style="display:inline-block;background:#fef2f2;color:#b91c1c;'
                    f'border:1px solid #fecaca;border-radius:6px;padding:3px 9px;margin:0 6px 6px 0;'
                    f'font-size:0.85rem">{c}</span>'
                    for c in nombres_sin_conv
                )
                st.markdown(
                    '<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.5px;'
                    'color:#64748b;font-weight:700;margin-bottom:8px">Sin conversiones esta semana</div>'
                    f'<div>{chips}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.5px;'
                    'color:#64748b;font-weight:700;margin-bottom:8px">Sin conversiones esta semana</div>'
                    '<div style="color:#16a34a;font-size:0.9rem">✓ Todos con conversiones</div>',
                    unsafe_allow_html=True,
                )

    st.divider()

    # Ranking de score por consultor — tarjetas compactas en columnas
    if scores:
        st.markdown("##### Score por cliente")
        grupos = {}
        for c in scores:
            grupos.setdefault(consultor(c), []).append(c)

        # Consultores con nombre primero (alfabético); "Sin asignar" al final
        nombres = sorted(g for g in grupos if g != "Sin asignar")
        if "Sin asignar" in grupos:
            nombres.append("Sin asignar")

        if consultores_map and len(nombres) > 1:
            for col, cons in zip(st.columns(len(nombres)), nombres):
                with col:
                    st.markdown(header_consultor_html(cons), unsafe_allow_html=True)
                    st.markdown(html_stats_consultor(grupos[cons], scores), unsafe_allow_html=True)
                    st.markdown(
                        html_score_cards(grupos[cons], scores, scores_ant),
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(html_stats_consultor(list(scores), scores), unsafe_allow_html=True)
            st.markdown(
                html_score_cards(list(scores), scores, scores_ant),
                unsafe_allow_html=True,
            )
        st.caption("Δ = variación vs semana anterior · 🔴 <50 · 🟡 50-80 · 🟢 ≥80")


# ──────────── CLIENTES ────────────
with tab_clientes:
    if not informe:
        st.info("Selecciona una semana arriba.")
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
            "Consultor": consultor(cliente),
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

    # Filtros (la separación por consultor va en columnas, no en filtro)
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

    def render_tabla_clientes(df_sub):
        df_show = df_sub[cols_show]
        styled = df_show.style.apply(_color_delta, subset=delta_cols) if delta_cols else df_show.style
        st.dataframe(styled, use_container_width=True, hide_index=True, column_config=col_config)

    # Grupos por consultor (con nombre primero, "Sin asignar" al final)
    grupos = sorted(g for g in df["Consultor"].unique() if g != "Sin asignar")
    if (df["Consultor"] == "Sin asignar").any():
        grupos.append("Sin asignar")

    if hay_consultores and len(grupos) > 1:
        for g in grupos:  # una tabla debajo de la otra
            df_g = df[df["Consultor"] == g]
            st.markdown(header_consultor_html(g, len(df_g)), unsafe_allow_html=True)
            render_tabla_clientes(df_g)
    elif hay_consultores and grupos:
        st.markdown(header_consultor_html(grupos[0], len(df)), unsafe_allow_html=True)
        render_tabla_clientes(df)
    else:
        render_tabla_clientes(df)
        st.caption(f"Mostrando {len(df)} de {len(scores)} clientes")


# ──────────── CONVERSIONES ────────────
with tab_conv:
    if not metricas or "clientes" not in metricas:
        st.info("Sin datos de métricas todavía.")
        st.stop()

    clientes_data = metricas["clientes"]
    st.caption(f"Semana {metricas['fecha_desde']} → {metricas['fecha_hasta']}  vs  semana anterior")

    st.divider()

    # Datos por cliente
    rows_conv = []
    for c, d in clientes_data.items():
        ke = d.get("key_events", {})
        ke_prev = d.get("key_events_prev", {})
        total = sum(ke.values())
        total_prev = sum(ke_prev.values())
        delta = pct(total, total_prev)
        rows_conv.append({
            "Cliente": c,
            "Consultor": consultor(c),
            "Conv. actual": total,
            "Conv. anterior": total_prev,
            "Δ %": delta,
            "Revenue (€)": d.get("revenue", 0) or 0,
            "Desglose": ", ".join(f"{k} ({v})" for k, v in ke.items()) if ke else "—",
            "GA4": "✓" if d.get("ga4_ok") else "✗",
        })

    df_conv = pd.DataFrame(rows_conv).sort_values("Conv. actual", ascending=False)

    # Aviso: clientes que normalmente tienen conversiones pero esta semana tienen 0
    sin_conv = df_conv[(df_conv["Conv. actual"] == 0) & (df_conv["Conv. anterior"] > 0)]
    if not sin_conv.empty:
        for _, row in sin_conv.iterrows():
            st.warning(f"⚠️ **{row['Cliente']}** no tiene conversiones esta semana, pero la semana anterior tuvo {int(row['Conv. anterior'])}.")

    hay_revenue = df_conv["Revenue (€)"].gt(0).any()
    cols_tbl = ["Cliente", "Conv. actual", "Conv. anterior", "Δ %", "Desglose"]
    if hay_revenue:
        cols_tbl.insert(cols_tbl.index("Δ %") + 1, "Revenue (€)")

    col_cfg = {
        "Conv. actual": st.column_config.NumberColumn("Esta semana"),
        "Conv. anterior": st.column_config.NumberColumn("Semana anterior"),
        "Δ %": st.column_config.NumberColumn("Δ %", format="%+.1f%%"),
        "Desglose": st.column_config.TextColumn("Desglose por evento", width="large"),
        "Revenue (€)": st.column_config.NumberColumn("Revenue (€)", format="%.0f €"),
    }

    def _color_delta(series):
        return [
            "color: #22c55e; font-weight: 600" if (v is not None and v > 0)
            else "color: #ef4444; font-weight: 600" if (v is not None and v < 0)
            else ""
            for v in series
        ]

    def render_tabla_conv(df_sub):
        styled = df_sub[cols_tbl].style.apply(_color_delta, subset=["Δ %"])
        st.dataframe(styled, use_container_width=True, hide_index=True, column_config=col_cfg)

    grupos = sorted(g for g in df_conv["Consultor"].unique() if g != "Sin asignar")
    if (df_conv["Consultor"] == "Sin asignar").any():
        grupos.append("Sin asignar")

    if hay_consultores and len(grupos) > 1:
        for g in grupos:  # una tabla debajo de la otra
            df_g = df_conv[df_conv["Consultor"] == g]
            st.markdown(header_consultor_html(g), unsafe_allow_html=True)
            render_tabla_conv(df_g)
    elif hay_consultores and grupos:
        st.markdown(header_consultor_html(grupos[0]), unsafe_allow_html=True)
        render_tabla_conv(df_conv)
    else:
        render_tabla_conv(df_conv)


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

        if not seleccionados:
            st.warning("Selecciona al menos un cliente.")
        elif hay_consultores:
            # Un gráfico por consultor con los clientes seleccionados de cada uno
            grupos = {}
            for c in seleccionados:
                grupos.setdefault(consultor(c), []).append(c)
            nombres = sorted(g for g in grupos if g not in ("General", "Sin asignar"))
            nombres += [g for g in ("Sin asignar",) if g in grupos]
            for g in nombres:
                st.markdown(header_consultor_html(g), unsafe_allow_html=True)
                st.plotly_chart(
                    fig_evolucion(grupos[g], historico, fechas_ord),
                    use_container_width=True, key=f"evo_{g}",
                )
        else:
            st.plotly_chart(
                fig_evolucion(seleccionados, historico, fechas_ord),
                use_container_width=True,
            )


# ──────────── ALERTAS ────────────
with tab_alertas:
    if not informe:
        st.info("Selecciona una semana arriba.")
        st.stop()

    secciones = informe.get("secciones", {})
    if not secciones:
        st.info("No hay secciones de alertas en este informe.")
    else:
        clientes_inf = list(informe.get("scores", {}).keys())

        def consultor_de_linea(linea):
            """Atribuye una línea al consultor del cliente que menciona (match más largo)."""
            nt = _norm_cliente(linea)
            mejor, mlen = None, 0
            for c in clientes_inf:
                nc = _norm_cliente(c)
                if len(nc) >= 4 and nc in nt and len(nc) > mlen:
                    mejor, mlen = c, len(nc)
            return consultor(mejor) if mejor else "General"

        def orden_grupos(keys):
            nombres = sorted(k for k in keys if k not in ("General", "Sin asignar"))
            return nombres + [k for k in ("Sin asignar", "General") if k in keys]

        # Secciones por cliente → se separan por consultor; el resto, enteras
        SPLIT = {"ALERTA", "REPORTING", "PROBLEMA"}
        for clave_busqueda, titulo in [
            ("ALERTA", "Alertas críticas"),
            ("REPORTING", "Reporting incompleto"),
            ("PROBLEMA", "Problemas internos"),
            ("INSIGHT", "Insights y patrones"),
            ("RESUMEN", "Resumen"),
        ]:
            contenido = next((v for k, v in secciones.items() if clave_busqueda in k.upper()), None)
            if not contenido:
                continue
            with st.expander(titulo, expanded=True):
                grupos = {}
                if clave_busqueda in SPLIT and hay_consultores:
                    for linea in contenido.splitlines():
                        if linea.strip():
                            grupos.setdefault(consultor_de_linea(linea), []).append(linea)
                # Solo separamos si hay al menos un grupo de consultor (no todo General)
                if grupos and any(g != "General" for g in grupos):
                    for g in orden_grupos(grupos):
                        st.markdown(header_consultor_html(g), unsafe_allow_html=True)
                        st.markdown("\n".join(grupos[g]))
                else:
                    st.markdown(contenido)


# ──────────── INFORME ────────────
with tab_informe:
    if not informe:
        st.info("Selecciona una semana arriba.")
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


# ──────────── Pie ────────────
st.divider()
st.caption(f"Cron: lunes 08:10 (Madrid) · Bucket: `{BUCKET}`")
