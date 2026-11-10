# memgame/leaderboard_service.py
# Cliente ligero para Upstash Redis (REST API) utilizado por el módulo de Leaderboard.
# Usa comandos nativos de Redis Sorted Sets:
#   - ZADD  -> guardar/actualizar puntaje
#   - ZRANGE / ZREVRANGE / ZRANGEBYSCORE -> obtener ranking con filtros

import logging
import os

import requests

logger = logging.getLogger(__name__)

UPSTASH_REDIS_REST_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_REDIS_REST_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

# Clave del Sorted Set en Redis que almacena el leaderboard global.
LEADERBOARD_KEY = "memory_game:leaderboard"


class UpstashLeaderboardError(RuntimeError):
    """Excepción lanzada cuando Upstash no está configurado o falla una operación."""


class UpstashLeaderboard:
    """Wrapper mínimo sobre la API REST de Upstash Redis para Sorted Sets."""

    def __init__(self):
        if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
            raise UpstashLeaderboardError(
                "Upstash Redis no está configurado. Define UPSTASH_REDIS_REST_URL y "
                "UPSTASH_REDIS_REST_TOKEN como variables de entorno."
            )
        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
        )

    def _request(self, method, path, params=None, json=None):
        url = f"{UPSTASH_REDIS_REST_URL}/{path.lstrip('/')}"
        try:
            response = self._session.request(
                method, url, params=params, json=json, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error("Upstash Redis request failed: %s", exc)
            raise UpstashLeaderboardError(str(exc)) from exc

    def add_score(self, member: str, score: float) -> dict:
        """
        Ejecuta ZADD LEADERBOARD_KEY score member.
        Si el miembro ya existe, su puntaje se actualiza (útil para guardar el mejor tiempo).
        """
        return self._request(
            "POST",
            f"zadd/{LEADERBOARD_KEY}",
            json={"score": score, "member": member},
        )

    def get_top(
        self,
        count: int = 100,
        min_score=None,
        max_score=None,
        order: str = "asc",
    ) -> list:
        """
        Obtiene entradas del Sorted Set.

        - count: cantidad máxima de entradas a solicitar a Redis.
        - min_score / max_score: filtro de rango de puntuación (usa ZRANGEBYSCORE).
        - order: 'asc' (menor score primero, ideal para tiempos) o 'desc' (mayor primero, ideal para puntos).

        Devuelve lista de diccionarios: [{"member": "Juan|Avanzado", "score": 30.5}, ...]
        El filtrado por nombre/nivel se hace en la vista (Redis no filtra por miembro).
        """
        params = {"withscores": True}

        if min_score is not None or max_score is not None:
            start = min_score if min_score is not None else "-inf"
            stop = max_score if max_score is not None else "+inf"
            params.update({"start": start, "stop": stop})
            path = f"zrangebyscore/{LEADERBOARD_KEY}"
        else:
            params.update({"start": 0, "stop": count - 1})
            if order == "desc":
                path = f"zrevrange/{LEADERBOARD_KEY}"
            else:
                path = f"zrange/{LEADERBOARD_KEY}"

        data = self._request("GET", path, params=params)
        results = []
        for item in data.get("result", []):
            if len(item) >= 2:
                results.append({"member": item[0], "score": float(item[1])})
        return results
