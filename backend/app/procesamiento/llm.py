"""Cliente mínimo de DeepSeek (API compatible con OpenAI). Sin dependencias extra: usa httpx."""

import json
import os
import time

import httpx

# Precios de deepseek-flash en horario pico, USD por millón de tokens (api-docs.deepseek.com, sep 2026).
# Solo se usan para estimar el costo. La entrada que DeepSeek ya tiene en su caché cuesta 50 veces menos.
PRECIO_ENTRADA = 0.30
PRECIO_ENTRADA_CACHE = 0.006
PRECIO_SALIDA = 1.20
# Si DeepSeek responde 429 (demasiadas peticiones) o falla de su lado (5xx), se reintenta tras estas esperas.
# Un 402 (sin saldo) no se reintenta.
ESPERAS = (2, 6)


def modelo() -> str:
    return os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")


def configurado() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def pedir_json(sistema: str, usuario: str, uso: dict) -> dict:
    """Llama al modelo pidiendo JSON y acumula los tokens usados en `uso`."""
    for espera in (*ESPERAS, None):
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
        estado = getattr(respuesta, "status_code", 200)
        if espera is None or not (estado == 429 or estado >= 500):
            break
        time.sleep(espera)
    respuesta.raise_for_status()
    datos = respuesta.json()
    tokens = datos.get("usage", {})
    uso["entrada"] = uso.get("entrada", 0) + tokens.get("prompt_tokens", 0)
    uso["cache"] = uso.get("cache", 0) + tokens.get("prompt_cache_hit_tokens", 0)  # parte de "entrada"
    uso["salida"] = uso.get("salida", 0) + tokens.get("completion_tokens", 0)
    uso["llamadas"] = uso.get("llamadas", 0) + 1
    return json.loads(datos["choices"][0]["message"]["content"])


def costo_usd(uso: dict) -> float:
    cache = uso.get("cache", 0)
    return (
        (uso.get("entrada", 0) - cache) * PRECIO_ENTRADA + cache * PRECIO_ENTRADA_CACHE + uso.get("salida", 0) * PRECIO_SALIDA
    ) / 1_000_000
