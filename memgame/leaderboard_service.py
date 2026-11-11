# memgame/leaderboard_service.py
# Cliente ligero para Upstash Redis (REST API) utilizado por el módulo de Leaderboard.
# Usa comandos nativos de Redis Sorted Sets:
#   - ZADD  -> guardar/actualizar puntaje
#   - ZRANGE / ZREVRANGE / ZRANGEBYSCORE -> obtener ranking con filtros

import logging
import os

import requests

logger = logging.getLogger(__name__)

# Limpiar la URL: remover espacios y barras inclinadas al final
UPSTASH_REDIS_REST_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip().rstrip("/")
UPSTASH_REDIS_REST_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()

# Clave del Sorted Set en Redis que almacena el leaderboard global.
LEADERBOARD_KEY = "memory_game:leaderboard"


class UpstashLeaderboardError(RuntimeError):
    """Excepción lanzada cuando Upstash no está configurado o falla una operación."""


class UpstashLeaderboard:
    """Wrapper mínimo sobre la API REST de Upstash Redis para Sorted Sets."""

    def __init__(self):
        if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
            msg = (
                "Upstash Redis no está configurado. Falta UPSTASH_REDIS_REST_URL o "
                "UPSTASH_REDIS_REST_TOKEN. URL='%s' TOKEN='%s'"
            ) % (UPSTASH_REDIS_REST_URL or "(vacío)", UPSTASH_REDIS_REST_TOKEN or "(vacío)")
            logger.error(msg)
            print(msg, flush=True)
            raise UpstashLeaderboardError(msg)
        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
        )
        logger.info("UpstashLeaderboard inicializado con URL: %s", UPSTASH_REDIS_REST_URL)
        print(f"[UpstashLeaderboard] Inicializado con URL: {UPSTASH_REDIS_REST_URL}", flush=True)

    def _request(self, method, path, params=None, json=None):
        url = f"{UPSTASH_REDIS_REST_URL}/{path.lstrip('/')}"
        try:
            logger.info("Upstash request: %s %s", method, url)
            print(f"[UpstashLeaderboard] {method} {url}", flush=True)
            response = self._session.request(
                method, url, params=params, json=json, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            msg = f"Upstash Redis request failed: {method} {url} -> {exc}"
            logger.error(msg)
            print(msg, flush=True)
            raise UpstashLeaderboardError(str(exc)) from exc
        except ValueError as exc:
            msg = f"Upstash Redis response parsing failed: {method} {url} -> {exc}"
            logger.error(msg)
            print(msg, flush=True)
            raise UpstashLeaderboardError(str(exc)) from exc

    def add_score(self, member: str, score: float) -> dict:
        """
        Ejecuta ZADD LEADERBOARD_KEY score member.
        Si el miembro ya existe, su puntaje se actualiza.
        Retorna dict con la respuesta o lanza UpstashLeaderboardError.
        """
        return self._request(
            "POST",
            f"zadd/{LEADERBOARD_KEY}",
            json={"score": str(score), "member": member},
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

        Si ocurre cualquier error de conexión, autenticación o parsing,
        registra el error en los logs y retorna una lista vacía [] de forma segura.

        Devuelve lista de diccionarios: [{"member": "Juan|Avanzado", "score": 30.5}, ...]
        """
        params = {"withscores": True}

        try:
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
        except UpstashLeaderboardError as exc:
            # Si falla la conexión o autenticación, retornar lista vacía de forma segura
            msg = f"Upstash get_top falló, retornando lista vacía: {exc}"
            logger.error(msg)
            print(msg, flush=True)
            return []

        results = []
        try:
            for item in data.get("result", []):
                if len(item) >= 2:
                    results.append({"member": item[0], "score": float(item[1])})
        except (ValueError, TypeError, AttributeError) as exc:
            msg = f"Error parseando resultados de Upstash: {exc}"
            logger.error(msg)
            print(msg, flush=True)
            return []

        return results
