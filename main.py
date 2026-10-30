import telebot
from telebot import types
import cloudscraper
from bs4 import BeautifulSoup
import re
import time
import urllib3
import ssl
from requests.adapters import HTTPAdapter

# Отключаем предупреждения о проверке сертификатов
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = '9270310396:AAHyjufNaud_LtmpJzlPuFDrLVTei74BR6w'
bot = telebot.TeleBot(TOKEN)


class SSLContextAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)


# Хранилище выбора пользователей и чек-листа (chat_id -> set олимпиад)
user_states = {}
user_registrations = {}

# БАЗЫ ССЫЛОК ПО ПРАВУ
law_uni = {
    "Ломоносов": "https://lomonosov.msu.ru",
    "Высшая проба": "https://olymp.hse.ru/mmo/law",
    "Кутафинская": "https://msal.ru/content/abiturientam/kutafinskaya-olimpiada-shkolnikov-po-pravu/",
    "МОШ": "https://mosh.olimpiada.ru",
    "Юр высоты": "https://usla.ru/students/yuridicheskie-vysoty.php",
    "В мир права": "https://rpa-mu.ru/abiturientu/vsemirnaya-olimpiada",
    "СПбГУ": "https://olympiada.spbu.ru",
    "КФУ": "https://admissions.kpfu.ru/",
    "Толстовская": "https://tsput.ru/olymp/"
}

law_agg = {
    "Ломоносов": "https://olimpiada.ru/activity/340",
    "Высшая проба": "https://olimpiada.ru/activity/151",
    "Кутафинская": "https://olimpiada.ru/activity/199",
    "МОШ": "https://olimpiada.ru/activity/111",
    "Юр высоты": "https://olimpiada.ru/activity/5864",
    "В мир права": "https://olimpiada.ru/activity/5726",
    "СПбГУ": "https://olimpiada.ru/activity/447",
    "КФУ": "https://olimpiada.ru/activity/203",
    "Толстовская": "https://olimpiada.ru/activity/5768"
}

# БАЗЫ ССЫЛОК ПО ОБЩЕСТВОЗНАНИЮ
social_uni = {
    "Высшая проба": "https://olymp.hse.ru/mmo/social",
    "Ломоносов": "https://lomonosov.msu.ru",
    "СПбГУ": "https://olympiada.spbu.ru",
    "РАНХиГС": "https://www.ranepa.ru/shkolnikam/olimpiada/",
    "Изумруд (УрФУ)": "https://izumrud.urfu.ru/ru/",
    "Миссия выполнима": "http://www.fa.ru/org/div/gprstm/mission/Pages/Home.aspx",
    "РГГУ": "https://rggu.ru/clever/",
    "Толстовская": "https://tsput.ru/olymp/"
}

social_agg = {
    "Высшая проба": "https://olimpiada.ru/activity/150",
    "Ломоносов": "https://olimpiada.ru/activity/351",
    "СПбГУ": "https://olimpiada.ru/activity/442",
    "РАНХиГС": "https://olimpiada.ru/activity/5009",
    "Изумруд (УрФУ)": "https://olimpiada.ru/activity/5396",
    "Миссия выполнима": "https://olimpiada.ru/activity/5296",
    "РГГУ": "https://olimpiada.ru/activity/393",
    "Толстовская": "https://olimpiada.ru/activity/5443"
}


# Генератор клавиатуры для чек-листа
def get_reg_keyboard(chat_id, olympiad_name):
    markup = types.InlineKeyboardMarkup()
    regs = user_registrations.get(chat_id, set())
    if olympiad_name in regs:
        btn = types.InlineKeyboardButton("❌ Отменить регистрацию", callback_data=f"unreg_{olympiad_name}")
    else:
        btn = types.InlineKeyboardButton("✅ Я зарегистрировался!", callback_data=f"reg_{olympiad_name}")
    markup.add(btn)
    return markup


def parse_universities_smart(url):
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        scraper.mount('https://', SSLContextAdapter())

        response = scraper.get(url, timeout=15)
        response.encoding = 'utf-8'

        if response.status_code != 200:
            return f"❌ Сайт отклонил запрос (код {response.status_code})."

        soup = BeautifulSoup(response.text, 'html.parser')

        for element in soup(["script", "style", "nav", "footer"]):
            element.extract()

        text = soup.get_text(separator='\n')
        keywords = ['регистрац', 'отборочн', 'заключительн', 'прием заяв']
        date_markers = ['сентябр', 'октябр', 'ноябр', 'декабр', 'январ', 'феврал', 'март', 'до ', '2026', '2027']
        found_info = []

        for line in text.split('\n'):
            line = line.strip().lower()
            if 10 < len(line) < 200:
                if any(kw in line for kw in keywords) and any(marker in line for marker in date_markers):
                    clean_line = re.sub(r'\s+', ' ', line).capitalize()
                    found_info.append(clean_line)

        unique = list(dict.fromkeys(found_info))
        return "🔹 " + "\n🔹 ".join(unique[:5]) if unique else "Сроки не найдены в тексте сайта."

    except Exception as e:
        print(f"Ошибка парсинга {url}: {e}")
        return "❌ Ошибка подключения к сайту вуза."


def parse_olimpiada_ru(url):
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        scraper.mount('https://', SSLContextAdapter())

        response = scraper.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        schedule_blocks = soup.find_all('table', class_='events_for_activity')
        if not schedule_blocks:
            schedule_blocks = soup.find_all('div', class_='not_archive_events')

        if schedule_blocks:
            all_lines = []
            for block in schedule_blocks:
                lines = [line.strip() for line in block.get_text('\n').split('\n') if line.strip()]
                clean_lines = [line for line in lines if line not in ["Что", "Когда", "Сегодня"]]
                all_lines.extend(clean_lines)

            unique_lines = []
            for line in all_lines:
                if line not in unique_lines:
                    unique_lines.append(line)

            return "🔹 " + "\n🔹 ".join(unique_lines)
        else:
            return "📅 Расписание на этот год еще не вывешено."

    except Exception as e:
        print(f"Ошибка парсинга {url}: {e}")
        return "❌ Ошибка подключения к агрегатору."


# ШАГ 1: ГЛАВНОЕ МЕНЮ
@bot.message_handler(commands=['start'])
def start(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    user_states[message.chat.id] = {}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("⚖️ Право", "📚 Обществознание")
    markup.row("📝 Мои регистрации")

    welcome_text = (
        "👋 <b>Привет!</b>\n"
        "Я бот для мониторинга дедлайнов олимпиад. Информация с сайтов вузов может быть не доступна.\n\n"
        "Выбери профиль для начала поиска:"
    )
    msg = bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="HTML")
    bot.register_next_step_handler(msg, step_choose_source)


# ПРОСМОТР ЧЕК-ЛИСТА
@bot.message_handler(func=lambda message: message.text == "📝 Мои регистрации")
def show_registrations(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    regs = user_registrations.get(message.chat.id, set())
    if not regs:
        bot.send_message(message.chat.id,
                         "Твой список пуст. Отмечай олимпиады здесь, чтобы ничего не забыть и вовремя распланировать поездки на очные финалы, особенно если предстоит путь на Урал или в Москву.")
    else:
        text = "✅ <b>Ты зарегистрирован на:</b>\n\n"
        for r in sorted(regs):
            text += f"🔹 {r}\n"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    start(message)


# ГЛОБАЛЬНАЯ КНОПКА ВОЗВРАТА
@bot.message_handler(func=lambda message: message.text == "🔙 На главную")
def handle_back_button(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    start(message)


# ОБРАБОТКА НАЖАТИЯ INLINE-КНОПОК ЧЕК-ЛИСТА
@bot.callback_query_handler(func=lambda call: call.data.startswith('reg_') or call.data.startswith('unreg_'))
def handle_reg_callback(call):
    chat_id = call.message.chat.id
    if chat_id not in user_registrations:
        user_registrations[chat_id] = set()

    action, olympiad_name = call.data.split('_', 1)

    if action == 'reg':
        user_registrations[chat_id].add(olympiad_name)
        bot.answer_callback_query(call.id, f"✅ Отмечено: {olympiad_name}")
    else:
        user_registrations[chat_id].discard(olympiad_name)
        bot.answer_callback_query(call.id, f"❌ Удалено: {olympiad_name}")

    # Обновляем кнопку под сообщением без переотправки самого текста
    bot.edit_message_reply_markup(
        chat_id,
        call.message.message_id,
        reply_markup=get_reg_keyboard(chat_id, olympiad_name)
    )


# ШАГ 2: ВЫБОР ИСТОЧНИКА
def step_choose_source(message):
    if message.text == "🔙 На главную":
        start(message)
        return
    if message.text == "📝 Мои регистрации":
        show_registrations(message)
        return

    if message.text not in ["⚖️ Право", "📚 Обществознание"]:
        bot.send_message(message.chat.id, "Используй кнопки внизу экрана. Нажми /start для сброса.")
        return

    user_states[message.chat.id]['subject'] = message.text

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🌐 Сайты вузов", "🎯 olimpiada.ru")
    markup.row("🔙 На главную")

    msg = bot.send_message(message.chat.id, "Откуда собирать информацию?", reply_markup=markup)
    bot.register_next_step_handler(msg, step_choose_olympiad)


# ШАГ 3: ВЫБОР ОЛИМПИАДЫ
def step_choose_olympiad(message):
    if message.text == "🔙 На главную":
        start(message)
        return
    if message.text == "📝 Мои регистрации":
        show_registrations(message)
        return

    if message.text not in ["🌐 Сайты вузов", "🎯 olimpiada.ru"]:
        bot.send_message(message.chat.id, "Используй кнопки внизу экрана. Нажми /start для сброса.")
        return

    user_states[message.chat.id]['source'] = message.text
    subject = user_states[message.chat.id]['subject']

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    target_dict = law_uni if subject == "⚖️ Право" else social_uni

    buttons = [types.KeyboardButton(name) for name in target_dict.keys()]

    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(buttons[i], buttons[i + 1])
        else:
            markup.row(buttons[i])

    markup.row("🌟 Проверить все сразу")
    markup.row("🔙 На главную")

    msg = bot.send_message(message.chat.id, "Выбери конкретную олимпиаду из списка:", reply_markup=markup)
    bot.register_next_step_handler(msg, fetch_data)


# ШАГ 4: СБОР И ВЫВОД ДАННЫХ
def fetch_data(message):
    if message.text == "🔙 На главную":
        start(message)
        return
    if message.text == "📝 Мои регистрации":
        show_registrations(message)
        return

    chat_id = message.chat.id
    state = user_states.get(chat_id, {})

    subject = state.get('subject')
    source = state.get('source')
    selected_olympiad = message.text

    if not subject or not source:
        bot.send_message(chat_id, "Сессия устарела. Начни заново через /start")
        return

    if subject == "⚖️ Право":
        target_dict = law_uni if source == "🌐 Сайты вузов" else law_agg
    else:
        target_dict = social_uni if source == "🌐 Сайты вузов" else social_agg

    parser_func = parse_universities_smart if source == "🌐 Сайты вузов" else parse_olimpiada_ru

    bot.send_message(chat_id, "⏳ Собираю данные, это займет пару секунд...")

    if selected_olympiad == "🌟 Проверить все сразу":
        for name, url in target_dict.items():
            result = parser_func(url)
            text = f"🏛 <b>{name}</b>\n🔗 <a href='{url}'>Ссылка на страницу</a>\n\n📅 <b>Сроки:</b>\n{result}"
            keyboard = get_reg_keyboard(chat_id, name)
            bot.send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=keyboard)

    elif selected_olympiad in target_dict:
        url = target_dict[selected_olympiad]
        result = parser_func(url)
        text = f"🏛 <b>{selected_olympiad}</b>\n🔗 <a href='{url}'>Ссылка на страницу</a>\n\n📅 <b>Сроки:</b>\n{result}"
        keyboard = get_reg_keyboard(chat_id, selected_olympiad)
        bot.send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=keyboard)

    else:
        msg = bot.send_message(chat_id, "Олимпиада не найдена. Попробуй выбрать из списка на клавиатуре.")
        bot.register_next_step_handler(msg, fetch_data)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔙 На главную")
    bot.send_message(chat_id, "✅ Поиск завершен. Можно вернуться в меню.", reply_markup=markup)


if __name__ == '__main__':
    print("Бот запущен. Напиши ему /start в Telegram.")

    while True:
        try:
            bot.polling(none_stop=True, timeout=20, long_polling_timeout=20)
        except Exception as e:
            print(f"Ошибка сети: {e}. Перезапуск через 3 секунды...")
            time.sleep(3)