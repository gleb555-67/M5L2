import telebot
import os
import tempfile
from config import *
from logic import *

bot = telebot.TeleBot(TOKEN)
manager = DB_Map(DATABASE)
manager.create_user_table()
from telebot import apihelper
apihelper.proxy = {'https': 'socks5://127.0.0.1:9150'}

TELEGRAM_MSG_LIMIT = 4000  # с запасом от 4096


# ---------- ВСПОМОГАТЕЛЬНОЕ ----------

def _format_cities_list(cities):
    """Формирует нумерованный список городов."""
    lines = [f"{i}. {name}" for i, name in enumerate(cities, start=1)]
    return "\n".join(lines)


def _send_long_message(chat_id, text):
    """Отправляет длинный текст, разбивая его на части при необходимости."""
    if len(text) <= TELEGRAM_MSG_LIMIT:
        bot.send_message(chat_id, text)
        return
    chunk = []
    length = 0
    for line in text.split("\n"):
        if length + len(line) + 1 > TELEGRAM_MSG_LIMIT:
            bot.send_message(chat_id, "\n".join(chunk))
            chunk = []
            length = 0
        chunk.append(line)
        length += len(line) + 1
    if chunk:
        bot.send_message(chat_id, "\n".join(chunk))


def _send_cities_map(chat_id, cities, caption, with_list=False):
    """Строит карту по списку городов и отправляет её (и, опционально, список)."""
    if not cities:
        bot.send_message(chat_id, "Список городов пуст.")
        return

    # 1) Карта
    path = os.path.join(
        tempfile.gettempdir(),
        f"cities_{chat_id}_{abs(hash(caption))}.png"
    )
    manager.create_graph(path, cities)
    if os.path.exists(path):
        with open(path, 'rb') as photo:
            bot.send_photo(chat_id, photo, caption=caption)
        os.remove(path)
    else:
        bot.send_message(chat_id, "Не удалось создать карту.")

    # 2) Текстовый список (по желанию)
    if with_list:
        header = f"📋 {caption}\n\n"
        _send_long_message(chat_id, header + _format_cities_list(cities))


# ---------- БАЗОВЫЕ КОМАНДЫ ----------

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
        "/show_my_cities - Показать все сохранённые города на карте\n"
        "/cities_by_country <страна> - Все города страны (карта + список)\n"
        "/top_cities [N] - Топ-N городов мира по населению (по умолчанию 10)\n"
        "/top_cities_by_country <страна> [N] - Топ-N городов страны по населению\n"
    )
    bot.send_message(message.chat.id, help_text)


@bot.message_handler(commands=['show_city'])
def handle_show_city(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Укажите название города: /show_city <город>")
        return
    city_name = parts[1].strip()

    if not manager.get_coordinates(city_name):
        bot.send_message(
            message.chat.id,
            f"Город {city_name} не найден. Проверьте написание (на английском)."
        )
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


# ---------- НОВЫЕ КОМАНДЫ ----------

@bot.message_handler(commands=['cities_by_country'])
def handle_cities_by_country(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        countries = ', '.join(manager.get_countries())
        bot.send_message(
            message.chat.id,
            "Укажите страну: /cities_by_country <страна>\n\n"
            f"Доступные страны:\n{countries}"
        )
        return

    country = parts[1].strip()
    cities = manager.get_cities_by_country(country)
    if not cities:
        bot.send_message(
            message.chat.id,
            f"Города страны '{country}' не найдены. "
            "Проверьте написание (на английском), например: China, India, Japan."
        )
        return

    _send_cities_map(
        message.chat.id,
        cities,
        f"Города страны {country} (всего: {len(cities)})",
        with_list=True
    )


@bot.message_handler(commands=['top_cities'])
def handle_top_cities(message):
    parts = message.text.split(maxsplit=1)
    limit = 10
    if len(parts) >= 2:
        try:
            limit = int(parts[1].strip())
            if limit <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(message.chat.id, "N должно быть положительным целым числом.")
            return

    cities = manager.get_top_cities_by_population(limit)
    _send_cities_map(
        message.chat.id,
        cities,
        f"Топ-{limit} городов мира по населению",
        with_list=True
    )


@bot.message_handler(commands=['top_cities_by_country'])
def handle_top_cities_by_country(message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        bot.send_message(
            message.chat.id,
            "Формат: /top_cities_by_country <страна> [N]\n"
            "Например: /top_cities_by_country China 5"
        )
        return

    country = parts[1].strip()
    limit = 10
    if len(parts) == 3:
        try:
            limit = int(parts[2].strip())
            if limit <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(message.chat.id, "N должно быть положительным целым числом.")
            return

    cities = manager.get_top_cities_by_country(country, limit)
    if not cities:
        bot.send_message(
            message.chat.id,
            f"Города страны '{country}' не найдены. Проверьте написание."
        )
        return

    _send_cities_map(
        message.chat.id,
        cities,
        f"Топ-{len(cities)} городов страны {country} по населению",
        with_list=True
    )


if __name__ == "__main__":
    bot.polling(none_stop=True)
