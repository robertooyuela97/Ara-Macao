# memory_game/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from collections import Counter
from django.db.models import Sum, Avg
import traceback

class PlayerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    total_wins = models.IntegerField(default=0)
    total_losses = models.IntegerField(default=0)
    games_played = models.IntegerField(default=0)
    avg_time_per_game = models.FloatField(default=0.0)
    most_played_level = models.CharField(max_length=50, default='N/A')

    def __str__(self):
        return self.user.username

    def update_statistics(self):
        """
        Recalcula y actualiza todas las estadísticas del perfil del jugador
        basándose en las GameSessions asociadas.
        """
        try:
           
            completed_sessions = self.user.gamesession_set.filter(is_won__isnull=False, duration__isnull=False)

            self.games_played = completed_sessions.count()
            self.total_wins = completed_sessions.filter(is_won=True).count()
            self.total_losses = completed_sessions.filter(is_won=False).count()

           
            avg_duration_agg = completed_sessions.aggregate(Avg('duration'))['duration__avg']
            self.avg_time_per_game = avg_duration_agg if avg_duration_agg is not None else 0.0

            
            levels = list(completed_sessions.values_list('level', flat=True))
            if levels:
                from collections import Counter
                level_counts = Counter(levels)
                self.most_played_level = level_counts.most_common(1)[0][0]
            else:
                self.most_played_level = 'N/A'
            
           
            self.save()
            print(f"[DEBUG] Estadísticas actualizadas para {self.user.username}")
        except Exception as e:
            import traceback
            print(f"[ERROR] update_statistics: {e}")
            traceback.print_exc()

class GameSession(models.Model):
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    level = models.CharField(max_length=50)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True)
    is_won = models.BooleanField(null=True, blank=True)
    attempts_left = models.IntegerField(null=True, blank=True)

    def __str__(self):
        status = 'Ganada' if self.is_won else 'Perdida' if self.is_won is False else 'En Curso'
        return f"Sesión de {self.player.username} - {self.level} ({status})"


@receiver(post_save, sender=User)
def create_player_profile(sender, instance, created, **kwargs):
    if created:
        profile, created_profile = PlayerProfile.objects.get_or_create(user=instance)
        print(f"[DEBUG] Perfil creado automáticamente para usuario: {instance.username}, creado: {created_profile}")


@receiver(post_save, sender=GameSession)
def update_player_profile_on_game_session_save(sender, instance, created, **kwargs):
    print(f"[DEBUG] Señal post_save GameSession para usuario: {instance.player.username}, is_won: {instance.is_won}")
   
    if instance.is_won is not None and hasattr(instance.player, 'playerprofile'):
        print(f"[DEBUG] Llamando a update_statistics para {instance.player.username}")
        instance.player.playerprofile.update_statistics()
    else:
        print(f"[DEBUG] No se actualizan estadísticas para {instance.player.username}")
