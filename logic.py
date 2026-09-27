import sqlite3
from config import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from math import radians, sin, cos, sqrt, atan2


class DB_Map():
    def __init__(self, database):
        self.database = database

    def create_user_table(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users_cities (
                                user_id INTEGER,
                                city_id TEXT,
                                FOREIGN KEY(city_id) REFERENCES cities(id)
                            )''')
            conn.commit()

    def add_city(self, user_id, city_name):
        conn = sqlite3.connect(self.database)
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM cities WHERE LOWER(city)=LOWER(?)", (city_name,))
            city_data = cursor.fetchone()
            if city_data:
                city_id = city_data[0]
                conn.execute('INSERT INTO users_cities VALUES (?, ?)', (user_id, city_id))
                conn.commit()
                return 1
            else:
                return 0

    def select_cities(self, user_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT cities.city 
                            FROM users_cities  
                            JOIN cities ON users_cities.city_id = cities.id
                            WHERE users_cities.user_id = ?''', (user_id,))
            cities = [row[0] for row in cursor.fetchall()]
            return cities

    def get_coordinates(self, city_name):
        conn = sqlite3.connect(self.database)
        with conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT lat, lng
                            FROM cities  
                            WHERE LOWER(city) = LOWER(?)''', (city_name,))
            coordinates = cursor.fetchone()
            return coordinates

    # ---------- НОВЫЕ МЕТОДЫ ----------

    def get_cities_by_country(self, country, limit=None):
        """Все города страны, отсортированные по населению (убыв.)."""
        conn = sqlite3.connect(self.database)
        with conn:
            cursor = conn.cursor()
            sql = '''SELECT city FROM cities
                     WHERE LOWER(country) = LOWER(?)
                     ORDER BY population DESC'''
            params = [country]
            if limit is not None:
                sql += ' LIMIT ?'
                params.append(limit)
            cursor.execute(sql, params)
            return [row[0] for row in cursor.fetchall()]

    def get_top_cities_by_population(self, limit=10):
        """Топ-N городов мира по населению (убыв.)."""
        conn = sqlite3.connect(self.database)
        with conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT city FROM cities
                              ORDER BY population DESC
                              LIMIT ?''', (limit,))
            return [row[0] for row in cursor.fetchall()]

    def get_top_cities_by_country(self, country, limit=10):
        """Топ-N городов конкретной страны по населению (убыв.)."""
        return self.get_cities_by_country(country, limit=limit)

    def get_countries(self):
        """Список всех стран в БД (для подсказки пользователю)."""
        conn = sqlite3.connect(self.database)
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT country FROM cities ORDER BY country')
            return [row[0] for row in cursor.fetchall()]

    def get_city_stats(self, city_name):
        """Возвращает страну и население города (для подписи к карте)."""
        conn = sqlite3.connect(self.database)
        with conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT country, population FROM cities
                              WHERE LOWER(city) = LOWER(?)''', (city_name,))
            return cursor.fetchone()

    # ---------- ОТРИСОВКА ----------

    def create_graph(self, path, cities):
        fig = plt.figure(figsize=(12, 6))
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.stock_img()
        ax.set_global()
        for city in cities:
            coordinates = self.get_coordinates(city)
            if coordinates is None:
                continue
            lat, lng = coordinates
            ax.plot(lng, lat, marker='o', color='red', markersize=6,
                    transform=ccrs.PlateCarree())
            ax.text(lng + 2, lat + 2, city, fontsize=9, color='black',
                    transform=ccrs.PlateCarree())
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)


if __name__ == "__main__":
    m = DB_Map(DATABASE)
    m.create_user_table()
