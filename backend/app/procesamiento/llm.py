"""Cliente mínimo de DeepSeek (API compatible con OpenAI). Sin dependencias extra: usa httpx."""

import json
import os

import httpx

# Precios de deepseek-flash en horario pico, USD por millón de tokens (api-docs.deepseek.com, sep 2026).
# Solo se usan para estimar el costo en la página de prueba.
PRECIO_ENTRADA = 0.30
PRECIO_SALIDA = 1.20


def modelo() -> str:
    return os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")


def configurado() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def pedir_json(sistema: str, usuario: str, uso: dict) -> dict:
    """Llama al modelo pidiendo JSON y acumula los tokens usados en `uso`."""
    respuesta = httpx.post(
        f"{os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')}/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY'].strip()}"},
        json={
            "model": modelo(),
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            # El modo "pensar" viene activo por defecto y multiplica los tokens de salida (lo más caro).
            # Para resumir no hace falta; DEEPSEEK_THINKING=enabled lo reactiva.
            "thinking": {"type": os.environ.get("DEEPSEEK_THINKING", "disabled")},
        },
        timeout=120,
    )
    respuesta.raise_for_status()
    datos = respuesta.json()
    tokens = datos.get("usage", {})
    uso["entrada"] = uso.get("entrada", 0) + tokens.get("prompt_tokens", 0)
    uso["salida"] = uso.get("salida", 0) + tokens.get("completion_tokens", 0)
    uso["llamadas"] = uso.get("llamadas", 0) + 1
    return json.loads(datos["choices"][0]["message"]["content"])


def costo_usd(uso: dict) -> float:
    return (uso.get("entrada", 0) * PRECIO_ENTRADA + uso.get("salida", 0) * PRECIO_SALIDA) / 1_000_000
