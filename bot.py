import telebot
import os
import tempfile
from config import *
from logic import *

from telebot import apihelper
apihelper.proxy = {'https': 'socks5://127.0.0.1:9150'}

bot = telebot.TeleBot(TOKEN)
manager = DB_Map(DATABASE)
manager.create_user_table()


@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(
        message.chat.id,
        "Привет! Я бот, который может показывать города на карте. "
        "Напиши /help для списка команд."
    )


@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = (
        "Доступные команды:\n"
        "/start - Приветствие\n"
        "/help - Список команд\n"
        "/show_city <город> - Показать город на карте\n"
        "/remember_city <город> - Сохранить город в личный список\n"
        "/show_my_cities - Показать все сохранённые города на карте"
    )
    bot.send_message(message.chat.id, help_text)


@bot.message_handler(commands=['show_city'])
def handle_show_city(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Укажите название города: /show_city <город>")
        return
    city_name = parts[1].strip()

    # Проверяем, есть ли город в базе
    if not manager.get_coordinates(city_name):
        bot.send_message(message.chat.id, f"Город {city_name} не найден. Проверьте написание (на английском).")
        return

    path = os.path.join(tempfile.gettempdir(), f"{city_name}_map.png")
    manager.create_graph(path, [city_name])

    if os.path.exists(path):
        with open(path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo)
        os.remove(path)
    else:
        bot.send_message(message.chat.id, "Не удалось создать карту.")


@bot.message_handler(commands=['remember_city'])
def handle_remember_city(message):
    user_id = message.chat.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Укажите название города: /remember_city <город>")
        return
    city_name = parts[1].strip()

    if manager.add_city(user_id, city_name):
        bot.send_message(message.chat.id, f'Город {city_name} успешно сохранён!')
    else:
        bot.send_message(
            message.chat.id,
            'Такого города я не знаю. Убедись, что он написан на английском!'
        )


@bot.message_handler(commands=['show_my_cities'])
def handle_show_visited_cities(message):
    cities = manager.select_cities(message.chat.id)
    if not cities:
        bot.send_message(message.chat.id, "У вас пока нет сохранённых городов.")
        return

    path = os.path.join(tempfile.gettempdir(), f"user_{message.chat.id}_cities.png")
    manager.create_graph(path, cities)

    if os.path.exists(path):
        with open(path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo)
        os.remove(path)
    else:
        bot.send_message(message.chat.id, "Не удалось создать карту.")


if __name__ == "__main__":
    bot.polling(none_stop=True)