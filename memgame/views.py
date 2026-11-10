# memgame/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.urls import reverse
from .models import PlayerProfile, GameSession
import random, json

# ===== Orden oficial de niveles =====
LEVELS = ["Básico", "Medio", "Avanzado"]

def _next_level_name(current_name: str):
    try:
        i = LEVELS.index(str(current_name))
        return LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    except ValueError:
        return None

#  AUTH 

def login_view(request):
    """
    Login que respeta ?next= si venías de una URL protegida.
    Si no hay next, te mando a select_level.
    """
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"]
            )
            if user:
                login(request, user)
                next_url = request.POST.get("next") or request.GET.get("next")
                return redirect(next_url or "memgame:select_level")
    else:
        form = AuthenticationForm()
    return render(request, "memgame/login.html", {"form": form})

def register_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            PlayerProfile.objects.get_or_create(user=user)
            login(request, user)
            return redirect("memgame:select_level")
    else:
        form = UserCreationForm()
    return render(request, "memgame/register.html", {"form": form})

@login_required
def logout_view(request):
    logout(request)
    return redirect("memgame:login")

#  VISTAS DEL JUEGO 

@login_required
def select_level_view(request):
    # Si quieres mostrar los niveles en la plantilla:
    return render(request, "memgame/select_level.html", {"levels": LEVELS})

@login_required
def game_view(request, level):
    """
    Renderiza el juego para un nivel dado (string).
    Crea una GameSession y pasa su id al template.
    """
    level = str(level).strip()
    # Ahora, el numero de cartas es siempre 16 para un tablero 4x4.
 
    
    if level == "Básico":
        num_cards = 8
        game_time_limit, initial_attempts = 60, 10
    elif level == "Medio":
        num_cards = 12
        game_time_limit, initial_attempts = 80, 8
    elif level == "Avanzado":
        num_cards = 16
        game_time_limit, initial_attempts = 90, 6
    else:
        # Si el nivel no es valido, redirigimos.
        return redirect("memgame:select_level")

    # Generar pares (valores como strings)
    # Se generan 8 pares de cartas para un total de 16.
    card_values = [str(i) for i in range(1, (num_cards // 2) + 1)] * 2
    random.shuffle(card_values)

    # Crear sesion de juego
    game_session = GameSession.objects.create(player=request.user, level=level)

    ctx = {
        "level": level,
        "initial_attempts": initial_attempts,
        "cards": card_values,
        "game_session_id": game_session.id,
        "game_time_limit": game_time_limit,
    }
    return render(request, "memgame/game.html", ctx)

@login_required
def profile_view(request):
    profile, _ = PlayerProfile.objects.get_or_create(user=request.user)
    # Si tu modelo tiene este método:
    if hasattr(profile, "update_statistics") and callable(profile.update_statistics):
        profile.update_statistics()
    history = GameSession.objects.filter(player=request.user).order_by("-start_time")
    return render(request, "memgame/profile.html", {"profile": profile, "game_history": history})

# ================== APIs ==================

@login_required
def game_move_api(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método no permitido"}, status=405)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("JSON inválido.")
    session_id = data.get("session_id")
    if not session_id:
        return JsonResponse({"status": "error", "message": "Falta session_id."}, status=400)
    get_object_or_404(GameSession, id=session_id, player=request.user)
    return JsonResponse({"status": "success", "message": "Movimiento procesado"})

@login_required
def game_end_api(request, session_id):
    """
    ACEPTA dos formatos de payload:

    1) Formato NUEVO (el de tu game.js actual):
        {
          "result": "win" | "lose",
          "level": "Básico" | "Medio" | "Avanzado",
          "time_used": <int>,
          "attempts_left": <int>
        }

    2) Formato ANTIGUO (legado):
        {
          "is_won": true|false,
          "duration": <int>
        }

    Devuelve next_level_url si ganó.
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método no permitido"}, status=405)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("JSON inválido.")

    # --- Normalizamos payload ---
    # Nuevo
    result = data.get("result")       # 'win' | 'lose'
    level_name = data.get("level")    # string (p.ej. "Medio")
    time_used = data.get("time_used")
    attempts_left = data.get("attempts_left")

    # Antiguo
    is_won_legacy = data.get("is_won")
    duration_legacy = data.get("duration")

    # Decidir valores finales
    if result in ("win", "lose"):
        is_won = (result == "win")
        duration = int(time_used) if time_used is not None else None
    else:
        # usar formato antiguo
        is_won = bool(is_won_legacy) if is_won_legacy is not None else None
        duration = int(duration_legacy) if duration_legacy is not None else None

    if is_won is None or duration is None:
        return JsonResponse({"status": "error", "message": "Faltan datos"}, status=400)

    # Recuperar sesión
    session = get_object_or_404(GameSession, id=session_id, player=request.user)

    # Actualizar sesión
    session.is_won = bool(is_won)
    session.end_time = timezone.now()
    session.duration = int(duration)
    session.save(update_fields=["is_won", "end_time", "duration"])

    # Actualizar perfil
    profile, _ = PlayerProfile.objects.get_or_create(user=request.user)
    profile.games_played = (profile.games_played or 0) + 1
    if session.is_won:
        profile.total_wins = (profile.total_wins or 0) + 1
    else:
        profile.total_losses = (profile.total_losses or 0) + 1
    profile.save(update_fields=["games_played", "total_wins", "total_losses"])

    # Si el payload nuevo trae level_name, úsalo para calcular el siguiente
    # Si no, intenta usar level guardado en la sesión
    level_for_next = level_name or session.level

    # Respuesta con siguiente nivel si ganó
    if session.is_won:
        nxt = _next_level_name(level_for_next)
        if nxt:
            return JsonResponse({
                "status": "success",
                "message": f"Nivel {level_for_next} superado. Preparando {nxt}...",
                "is_won": session.is_won,
                "duration": session.duration,
                "session_id": session.id,
                "next_level": nxt,
                "next_level_url": reverse("memgame:game", kwargs={"level": nxt}),
            })
        else:
            return JsonResponse({
                "status": "success",
                "message": "¡Has completado todos los niveles! 🏆",
                "is_won": session.is_won,
                "duration": session.duration,
                "session_id": session.id,
                "next_level": None,
                "next_level_url": reverse("memgame:profile"),
            })

    # Si no gano, sin redireccion
    return JsonResponse({
        "status": "success",
        "message": "Sesión de juego finalizada y estadísticas actualizadas",
        "is_won": session.is_won,
        "duration": session.duration,
        "session_id": session.id,
        "next_level": None,
        "next_level_url": None,
    })

# ================== LEADERBOARD (Upstash Redis) ==================

from .leaderboard_service import UpstashLeaderboard, UpstashLeaderboardError  # noqa: E402


def leaderboard_view(request):
    """Renderiza la página del Top 10 de mejores puntuaciones (público)."""
    return render(request, "memgame/leaderboard.html")


def leaderboard_submit_api(request):
    """
    Registra/actualiza un puntaje en el leaderboard de Upstash Redis.
    Payload esperado (JSON):
        {
          "name": "Juan",
          "score": 30.5,          # tiempo en segundos (menor es mejor)
          "level": "Avanzado"     # opcional
        }
    Usa ZADD para guardar/actualizar el puntaje.
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método no permitido"}, status=405)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("JSON inválido.")

    name = (data.get("name") or "").strip()
    score = data.get("score")
    level = (data.get("level") or "").strip()

    if not name:
        return JsonResponse({"status": "error", "message": "Falta el nombre del jugador."}, status=400)
    if score is None:
        return JsonResponse({"status": "error", "message": "Falta el puntaje/tiempo."}, status=400)

    try:
        score = float(score)
    except (ValueError, TypeError):
        return JsonResponse({"status": "error", "message": "Puntaje inválido."}, status=400)

    try:
        lb = UpstashLeaderboard()
        # El miembro incluye el nivel para que el mismo jugador pueda tener
        # su mejor registro por cada nivel (nombre|nivel).
        member = f"{name}|{level}" if level else name
        lb.add_score(member, score)
    except UpstashLeaderboardError as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=502)

    return JsonResponse({
        "status": "success",
        "message": "Puntaje registrado en el leaderboard.",
        "member": member,
        "score": score,
    })


def leaderboard_top_api(request):
    """
    Devuelve el ranking con filtros opcionales:

    Parámetros GET:
        - name: filtra por nombre que contenga el texto (case insensitive).
        - level: filtra por nivel exacto (Básico, Medio, Avanzado).
        - min_score / max_score: rango de puntuación.
        - limit: cantidad máxima a devolver (default 10, max 100).
        - order: 'asc' (menor score primero, ideal para tiempos) o 'desc'.

    Usa ZRANGE / ZREVRANGE / ZRANGEBYSCORE de Redis.
    """
    if request.method != "GET":
        return JsonResponse({"status": "error", "message": "Método no permitido"}, status=405)

    name = request.GET.get("name", "").strip().lower()
    level = request.GET.get("level", "").strip()
    min_score = request.GET.get("min_score")
    max_score = request.GET.get("max_score")
    try:
        limit = min(int(request.GET.get("limit", 10)), 100)
    except ValueError:
        limit = 10
    order = request.GET.get("order", "asc")
    if order not in ("asc", "desc"):
        order = "asc"

    # Convertir scores a float si vienen
    min_score_f = float(min_score) if min_score not in (None, "") else None
    max_score_f = float(max_score) if max_score not in (None, "") else None

    try:
        lb = UpstashLeaderboard()
        # Pedimos un lote amplio a Redis para poder filtrar por nombre/nivel en Python
        raw = lb.get_top(count=200, min_score=min_score_f, max_score=max_score_f, order=order)
    except UpstashLeaderboardError as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=502)

    # Enriquecer y filtrar por nombre y nivel
    enriched = []
    for entry in raw:
        member = entry["member"]
        if "|" in member:
            member_name, member_level = member.rsplit("|", 1)
        else:
            member_name, member_level = member, "-"

        if name and name not in member_name.lower():
            continue
        if level and member_level != level:
            continue

        enriched.append({
            "name": member_name,
            "level": member_level,
            "score": entry["score"],
        })

        if len(enriched) >= limit:
            break

    return JsonResponse({
        "status": "success",
        "top": enriched,
        "count": len(enriched),
        "filters": {
            "name": name,
            "level": level,
            "min_score": min_score_f,
            "max_score": max_score_f,
            "order": order,
        },
    })
