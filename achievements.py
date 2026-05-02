import json
import os
from datetime import datetime
from kivy.storage.jsonstore import JsonStore

class AchievementSystem:
    """Система достижений игры"""

    def __init__(self):
        self.achievements_file = 'achievements.json'
        self.achievements = {}
        self.unlocked_achievements = set()
        self._load_achievements()

        # Определяем все достижения
        self._define_achievements()

    def _define_achievements(self):
        """Определяет все доступные достижения"""
        self.achievements = {
            'first_victory': {
                'name': 'Первая победа',
                'description': 'Победите в первой игре',
                'icon': '🏆',
                'condition': lambda stats: stats.get('victories', 0) >= 1,
                'reward': 'Новое фоновое изображение'
            },
            'warrior': {
                'name': 'Воитель',
                'description': 'Выиграйте 10 сражений',
                'icon': '⚔️',
                'condition': lambda stats: stats.get('battles_won', 0) >= 10,
                'reward': 'Улучшенные боевые юниты'
            },
            'diplomat': {
                'name': 'Дипломат',
                'description': 'Заключите 5 союзов',
                'icon': '🤝',
                'condition': lambda stats: stats.get('alliances_made', 0) >= 5,
                'reward': 'Дополнительные дипломатические опции'
            },
            'builder': {
                'name': 'Строитель',
                'description': 'Постройте 50 зданий',
                'icon': '🏗️',
                'condition': lambda stats: stats.get('buildings_built', 0) >= 50,
                'reward': 'Скидка на строительство'
            },
            'merchant': {
                'name': 'Торговец',
                'description': 'Заработайте 1,000,000 монет',
                'icon': '💰',
                'condition': lambda stats: stats.get('total_gold_earned', 0) >= 1000000,
                'reward': 'Улучшенные торговые маршруты'
            },
            'strategist': {
                'name': 'Стратег',
                'description': 'Завершите игру за 50 ходов',
                'icon': '🎯',
                'condition': lambda stats: stats.get('fastest_victory', float('inf')) <= 50,
                'reward': 'Бонус к опыту'
            },
            'survivor': {
                'name': 'Выживальщик',
                'description': 'Выживите 100 ходов в одной игре',
                'icon': '🛡️',
                'condition': lambda stats: stats.get('longest_game', 0) >= 100,
                'reward': 'Улучшенная защита городов'
            },
            'legend': {
                'name': 'Легенда',
                'description': 'Достигните максимального уровня',
                'icon': '👑',
                'condition': lambda stats: stats.get('max_level', 0) >= 10,
                'reward': 'Эксклюзивный контент'
            }
        }

    def _load_achievements(self):
        """Загружает разблокированные достижения"""
        try:
            if os.path.exists(self.achievements_file):
                with open(self.achievements_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.unlocked_achievements = set(data.get('unlocked', []))
        except Exception as e:
            print(f"Ошибка загрузки достижений: {e}")

    def _save_achievements(self):
        """Сохраняет разблокированные достижения"""
        try:
            data = {
                'unlocked': list(self.unlocked_achievements),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.achievements_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения достижений: {e}")

    def check_achievements(self, stats):
        """Проверяет и разблокирует достижения"""
        newly_unlocked = []

        for achievement_id, achievement in self.achievements.items():
            if achievement_id not in self.unlocked_achievements:
                if achievement['condition'](stats):
                    self.unlocked_achievements.add(achievement_id)
                    newly_unlocked.append(achievement)

        if newly_unlocked:
            self._save_achievements()

        return newly_unlocked

    def get_unlocked_achievements(self):
        """Возвращает список разблокированных достижений"""
        return [self.achievements[aid] for aid in self.unlocked_achievements if aid in self.achievements]

    def get_all_achievements(self):
        """Возвращает все достижения с статусом разблокировки"""
        return {
            aid: {
                **achievement,
                'unlocked': aid in self.unlocked_achievements
            }
            for aid, achievement in self.achievements.items()
        }


class StatisticsManager:
    """Менеджер статистики игрока"""

    def __init__(self):
        self.stats_file = 'player_stats.json'
        self.stats = self._load_stats()

    def _load_stats(self):
        """Загружает статистику"""
        default_stats = {
            'games_played': 0,
            'victories': 0,
            'defeats': 0,
            'battles_won': 0,
            'battles_lost': 0,
            'alliances_made': 0,
            'wars_declared': 0,
            'buildings_built': 0,
            'total_gold_earned': 0,
            'total_gold_spent': 0,
            'longest_game': 0,
            'fastest_victory': float('inf'),
            'max_level': 0,
            'total_playtime': 0,  # в минутах
            'first_game_date': None,
            'last_game_date': None
        }

        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    loaded_stats = json.load(f)
                    default_stats.update(loaded_stats)
        except Exception as e:
            print(f"Ошибка загрузки статистики: {e}")

        return default_stats

    def _save_stats(self):
        """Сохраняет статистику"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения статистики: {e}")

    def update_stat(self, stat_name, value, operation='set'):
        """Обновляет статистику"""
        if operation == 'set':
            self.stats[stat_name] = value
        elif operation == 'add':
            self.stats[stat_name] = self.stats.get(stat_name, 0) + value
        elif operation == 'max':
            current = self.stats.get(stat_name, 0)
            self.stats[stat_name] = max(current, value)
        elif operation == 'min':
            current = self.stats.get(stat_name, float('inf'))
            self.stats[stat_name] = min(current, value)

        self._save_stats()

    def get_stat(self, stat_name):
        """Возвращает значение статистики"""
        return self.stats.get(stat_name, 0)

    def get_all_stats(self):
        """Возвращает всю статистику"""
        return self.stats.copy()

    def record_game_result(self, victory, turns, level, playtime_minutes):
        """Записывает результат игры"""
        self.update_stat('games_played', 1, 'add')

        if victory:
            self.update_stat('victories', 1, 'add')
            self.update_stat('fastest_victory', turns, 'min')
        else:
            self.update_stat('defeats', 1, 'add')

        self.update_stat('longest_game', turns, 'max')
        self.update_stat('max_level', level, 'max')
        self.update_stat('total_playtime', playtime_minutes, 'add')

        now = datetime.now().isoformat()
        if not self.stats['first_game_date']:
            self.stats['first_game_date'] = now
        self.stats['last_game_date'] = now

        self._save_stats()

# Глобальные экземпляры
achievement_system = AchievementSystem()
statistics_manager = StatisticsManager()</content>
<parameter name="filePath">c:\Users\lerdo\Desktop\AI\Lerdon_2\achievements.py