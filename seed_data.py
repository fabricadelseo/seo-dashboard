"""
Sube datos de muestra (3 clientes) al bucket para visualizar el dashboard.
Uso: python seed_data.py
"""
import json
from google.cloud import storage
from google.oauth2 import service_account

BUCKET = "seo-dashboard-data-fabricaseo"
KEY_FILE = r"C:\Users\car87\Downloads\api-gsc-430410-b607a8308759.json"

creds = service_account.Credentials.from_service_account_file(KEY_FILE)
client = storage.Client(credentials=creds, project="api-gsc-430410")
bucket = client.bucket(BUCKET)

# ── Clientes de muestra ─────────────────────────────────────────────────────

CLIENTES = {
    "Restaurante El Olivo": {
        "score": 87,
        "organic_sessions": 1420, "organic_sessions_prev": 1280,
        "direct_sessions": 310, "direct_sessions_prev": 290,
        "revenue": 0, "revenue_prev": 0,
        "ga4_ok": True,
        "gsc_clicks": 890, "gsc_clicks_prev": 810,
        "gsc_impressions": 14200, "gsc_impressions_prev": 13500,
        "gsc_ctr": 6.3, "gsc_position": 8.2,
        # Restaurante: reservas online y clics en teléfono
        "key_events": {"reserva_online": 31, "clic_telefono": 18, "ver_carta": 94},
        "key_events_prev": {"reserva_online": 24, "clic_telefono": 15, "ver_carta": 80},
        "llm": {"ChatGPT": 12, "Gemini": 5, "Claude": 2, "Copilot": 0, "Perplexity": 3},
        "llm_prev": {"ChatGPT": 8, "Gemini": 3, "Claude": 1, "Copilot": 0, "Perplexity": 1},
    },
    "Clinica Dental Sonrisa": {
        "score": 62,
        "organic_sessions": 540, "organic_sessions_prev": 610,
        "direct_sessions": 120, "direct_sessions_prev": 130,
        "revenue": 0, "revenue_prev": 0,
        "ga4_ok": True,
        "gsc_clicks": 320, "gsc_clicks_prev": 390,
        "gsc_impressions": 7800, "gsc_impressions_prev": 8900,
        "gsc_ctr": 4.1, "gsc_position": 14.7,
        # Clínica: solicitudes de cita y llamadas
        "key_events": {"solicitud_cita": 9, "llamada": 6, "formulario_contacto": 4},
        "key_events_prev": {"solicitud_cita": 17, "llamada": 11, "formulario_contacto": 6},
        "llm": {"ChatGPT": 4, "Gemini": 2, "Claude": 0, "Copilot": 0, "Perplexity": 1},
        "llm_prev": {"ChatGPT": 3, "Gemini": 1, "Claude": 0, "Copilot": 0, "Perplexity": 0},
    },
    "Tienda Online MasDeporte": {
        "score": 38,
        "organic_sessions": 210, "organic_sessions_prev": 480,
        "direct_sessions": 90, "direct_sessions_prev": 200,
        "revenue": 1850.00, "revenue_prev": 4200.00,
        "ga4_ok": True,
        "gsc_clicks": 95, "gsc_clicks_prev": 310,
        "gsc_impressions": 3200, "gsc_impressions_prev": 8100,
        "gsc_ctr": 3.0, "gsc_position": 22.1,
        # Ecommerce: compras y carritos abandonados
        "key_events": {"purchase": 12, "add_to_cart": 38},
        "key_events_prev": {"purchase": 38, "add_to_cart": 95},
        "llm": {"ChatGPT": 0, "Gemini": 0, "Claude": 0, "Copilot": 0, "Perplexity": 0},
        "llm_prev": {"ChatGPT": 1, "Gemini": 0, "Claude": 0, "Copilot": 0, "Perplexity": 0},
    },
}

FECHA = "2026-06-01"
FECHA_DESDE = "2026-05-26"
FECHA_HASTA = "2026-06-01"
FECHA_PREV_DESDE = "2026-05-19"
FECHA_PREV_HASTA = "2026-05-25"
FECHA_ANT = "2026-05-25"

scores = {c: d["score"] for c, d in CLIENTES.items()}
scores_ant = {
    "Restaurante El Olivo": 82,
    "Clinica Dental Sonrisa": 70,
    "Tienda Online MasDeporte": 55,
}

# ── informe ─────────────────────────────────────────────────────────────────

informe = {
    "fecha": FECHA,
    "fecha_desde": FECHA_DESDE,
    "fecha_hasta": FECHA_HASTA,
    "num_mensajes": 3,
    "scores": scores,
    "analisis": """## Informe semanal SEO — 26 mayo → 1 junio 2026

### Resumen ejecutivo

Esta semana destaca negativamente **Tienda Online MasDeporte**, que ha caído de 55 a 38 puntos. La caída del tráfico orgánico es del 56% respecto a la semana anterior y el revenue ha bajado de 4.200€ a 1.850€. Requiere revisión urgente de penalizaciones o problemas técnicos.

**Clínica Dental Sonrisa** también retrocede (de 70 a 62), con caídas tanto en sesiones orgánicas como en GSC. Hay que revisar el estado del proyecto de contenidos.

**Restaurante El Olivo** se mantiene sano y sigue creciendo, con +10,9% de sesiones orgánicas y +9,9% de clics en GSC.

### Alertas

- **Tienda Online MasDeporte**: caída crítica en todas las métricas. GA4 sin datos esta semana (propiedad no configurada o acceso revocado). Posible penalización algorítmica o problema técnico grave.
- **Clínica Dental Sonrisa**: descenso continuado por tercera semana consecutiva. Las palabras clave de tratamientos principales han bajado de posición media 10 a 14.7.

### Insights

- El tráfico desde IA (ChatGPT, Gemini) está creciendo especialmente en Restaurante El Olivo, que ya recibe 22 sesiones/semana desde fuentes IA.
- Los clientes con GA4 correctamente configurado tienen de media 3x más sesiones orgánicas que los que no.
""",
    "secciones": {
        "RESUMEN EJECUTIVO": """Esta semana destaca negativamente **Tienda Online MasDeporte**, que ha caído de 55 a 38 puntos. Caída del tráfico orgánico del 56% y revenue de 4.200€ a 1.850€. Requiere revisión urgente. **Clínica Dental Sonrisa** también retrocede. **Restaurante El Olivo** sigue creciendo con +10,9% sesiones orgánicas.""",
        "ALERTAS CRÍTICAS": """- **Tienda Online MasDeporte**: caída crítica en todas las métricas. GA4 sin datos (propiedad no configurada o acceso revocado). Posible penalización algorítmica o problema técnico grave.\n- **Clínica Dental Sonrisa**: descenso continuado por tercera semana consecutiva. Posición media GSC ha bajado de 10 a 14.7.""",
        "INSIGHTS Y PATRONES": """- El tráfico desde IA (ChatGPT, Gemini) crece especialmente en Restaurante El Olivo: 22 sesiones/semana desde fuentes IA, +175% vs semana anterior.\n- Los clientes con GA4 configurado tienen de media 3x más sesiones orgánicas.""",
    },
    "mensajes_input": [
        {"recurso": "Restaurante El Olivo", "tipo": "update_semanal", "fecha": FECHA, "texto": "Esta semana hemos publicado 3 posts en el blog y optimizado las fichas de Google Business. El tráfico sigue subiendo."},
        {"recurso": "Clinica Dental Sonrisa", "tipo": "update_semanal", "fecha": FECHA, "texto": "Sin novedades esta semana. Pendiente el calendario de contenidos para junio."},
        {"recurso": "Tienda Online MasDeporte", "tipo": "update_semanal", "fecha": FECHA, "texto": "Hemos migrado el servidor. Puede haber caídas temporales. Necesitamos revisar los redirects."},
    ],
}

# ── metrics ─────────────────────────────────────────────────────────────────

metricas = {
    "fecha_desde": FECHA_DESDE,
    "fecha_hasta": FECHA_HASTA,
    "fecha_prev_desde": FECHA_PREV_DESDE,
    "fecha_prev_hasta": FECHA_PREV_HASTA,
    "clientes": {
        c: {
            "organic_sessions": d["organic_sessions"],
            "organic_sessions_prev": d["organic_sessions_prev"],
            "direct_sessions": d["direct_sessions"],
            "direct_sessions_prev": d["direct_sessions_prev"],
            "revenue": d["revenue"],
            "revenue_prev": d["revenue_prev"],
            "ga4_ok": d["ga4_ok"],
            "gsc_clicks": d["gsc_clicks"],
            "gsc_clicks_prev": d["gsc_clicks_prev"],
            "gsc_impressions": d["gsc_impressions"],
            "gsc_impressions_prev": d["gsc_impressions_prev"],
            "gsc_ctr": d["gsc_ctr"],
            "gsc_position": d["gsc_position"],
            "llm": d["llm"],
            "llm_prev": d["llm_prev"],
        }
        for c, d in CLIENTES.items()
    },
}

# ── scores_history ───────────────────────────────────────────────────────────

scores_history = {
    "2026-05-04": {"Restaurante El Olivo": 74, "Clinica Dental Sonrisa": 78, "Tienda Online MasDeporte": 72},
    "2026-05-11": {"Restaurante El Olivo": 78, "Clinica Dental Sonrisa": 75, "Tienda Online MasDeporte": 68},
    "2026-05-18": {"Restaurante El Olivo": 80, "Clinica Dental Sonrisa": 73, "Tienda Online MasDeporte": 61},
    FECHA_ANT:    {"Restaurante El Olivo": 82, "Clinica Dental Sonrisa": 70, "Tienda Online MasDeporte": 55},
    FECHA:        scores,
}

# ── upload ───────────────────────────────────────────────────────────────────

def upload(name, data):
    blob = bucket.blob(name)
    blob.upload_from_string(json.dumps(data, ensure_ascii=False, indent=2), content_type="application/json")
    print(f"  OK  {name}")

print("Subiendo datos de muestra al bucket...")
upload(f"reports/report-{FECHA}.json", informe)
upload("reports/latest.json", informe)
upload(f"metrics/metrics-{FECHA}.json", metricas)
upload("metrics/latest.json", metricas)
upload("scores_history.json", scores_history)
print("Listo. Refresca el dashboard.")
