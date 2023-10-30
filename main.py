import time
import random
import logging

import openai
import telebot
from telebot import types

import config
from database import BotDatabase
from keyboards import markup_keyboard_accept, markup_keyboard_exercises, markup_keyboard_chill

openai.api_key = config.OPENAI_TOKEN
bot = telebot.TeleBot(token=config.TG_BOT_TOKEN)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
BotDatabase = BotDatabase('fintess-ai.sqlite')

logging.info('создаем команды боту')

bot.set_my_commands([
    telebot.types.BotCommand('/start', "Главная"),
    telebot.types.BotCommand('/start_sport', "Начать тренировку сейчас"),
    telebot.types.BotCommand('/schedule', "Запланированые тренировки"),
    telebot.types.BotCommand('/statistics', "Достижения (статистика)"),
    telebot.types.BotCommand('/edit_prog', "Поменять тренировочную программу"),
    telebot.types.BotCommand('/about', "О боте"),
])

context_messages = {}
context_messages_program = {}

tokens = {}
user_feedback = {}


@bot.message_handler(commands=['start'])
def main(message: types.Message):
    if not BotDatabase.check_user(user_id=message.from_user.id):
        logging.info(f'добваляем пользователя с user_id: {message.from_user.id} в базу данных')
        BotDatabase.add_user(message.from_user.id, message.from_user.username)

        start_msg = bot.send_message(message.chat.id, "Привет, я GymLessBot. Я составлю для тебя персонализированную программу тренировки дома.\nРасскажи в голосовом или напиши сообщением:\n*Как тебя зовут?\n*Сколько тебе лет?\n*Какие у тебя предпочтения по упражнениям?\n*Есть ли у тебя какой-либо спортивный инвентарь?")

        if not message.from_user.id in context_messages.keys():
            context_messages[message.from_user.id] = []
            context_messages_program[message.from_user.id] = []
            user_feedback[message.from_user.id] = []
            tokens[message.from_user.id] = {"prompt_1": 0, "prompt_2": 0}

        context_messages[message.from_user.id].append({"role": "system", "content": "Твоя задача сделать анкету по данным предоставлеными пользователем. Формат анкеты следующий:имя,пол,возраст,уровень физической подготовки (от 1 до 10),длительность занятия, физические ограничения,наличие спортивного инвентаря,пожелания по упражнениям. Не задавай вопрос про пол (гендер) пользователя,определи пол по имени. Общайся с пользователем на «ты». Задавай уточняющие вопросы до тех пор пока анкету не заполнишь полностью. Задавай вопросы строго по анкете. Обязательно спроси у пользователя возраст. Задавай по два вопроса за раз. Пиши кратко, не повторяй слова пользователя, не давай лишних комментариев. Начни сообщение с анкетой со слов 'Твоя анкета' .По завершению анкеты, спроси, все ли верно с ней и спроси нужно ли что-то исправить. Не выдавай анкету до тех пор пока она полностью не будет заполнена."})
        bot.register_next_step_handler(start_msg, get_info)
    else:
        if not message.from_user.id in user_feedback.keys():
            user_feedback[message.from_user.id] = []
        logging.info(f'пользователь с user_id: {message.from_user.id} уже существует')
        bot.send_message(message.from_user.id, "Привет, вижу ты уже зарегестрирован. Для того что бы начать тренировку нажми /start_sport или воспользуйся нашим меню.")


def get_info(message: types.Message):
    if message.content_type == 'voice':

        logging.info('пользователь отправил голосовое сообщение, вызываем whisper и конвертируем в текст')
        bot.send_message(message.chat.id, "Понял тебя, начинаю составлять твою анкету!")

        file_info = bot.get_file(message.voice.file_id)
        df = bot.download_file(file_info.file_path)

        logging.info('получили голосовое сообщение, скармливаем его whisper')
        with open(f'voice_messages/{message.from_user.id}.mp3', 'wb') as file:
            file.write(df)

        audio_file = open(f'voice_messages/{message.from_user.id}.mp3', 'rb')
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        transcripted_text = str(transcript['text'])

        logging.info(f'Получили текст из гс {transcripted_text}, отправляем запрос в гпт')

        context_messages[message.from_user.id].append({"role": "user", "content": transcripted_text})

        form_completion = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages[message.from_user.id],
            temperature=0.1
        )

        logging.info(f'получили ответ гпт {form_completion.choices[0].message.content}')

        tokens[message.from_user.id]['prompt_1'] += int(form_completion.usage.total_tokens)
        logging.info(f'считаем токены для пользователя: {message.from_user.id}, итого prompt_1 = {tokens[message.from_user.id]["prompt_1"]}')

        context_messages[message.from_user.id].append({"role": "assistant", "content": form_completion.choices[0].message.content})

        check_message = bot.send_message(message.chat.id, form_completion.choices[0].message.content)
        bot.register_next_step_handler(check_message, check_form)

    elif message.content_type == 'text':
        logging.info('пользователь отправил текстовое сообщение')
        text_from_user = message.text
        bot.send_message(message.chat.id, "Понял тебя, начинаю составлять твою анкету!")

        context_messages[message.from_user.id].append({"role": "user", "content": str(text_from_user)})

        form_completion = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages[message.from_user.id],
            temperature=0.1
        )

        logging.info(f'Получили ответ gpt {form_completion.choices[0].message.content}')
        tokens[message.from_user.id]['prompt_1'] += int(form_completion.usage.total_tokens)

        logging.info(f'считаем токены для пользователя: {message.from_user.id}, итого prompt_1 = {tokens[message.from_user.id]["prompt_1"]}')

        context_messages[message.from_user.id].append({"role": "assistant", "content": form_completion.choices[0].message.content})

        check_message = bot.send_message(message.chat.id, form_completion.choices[0].message.content)

        bot.register_next_step_handler(check_message, check_form)


def check_form(message: types.Message):
    logging.info(f'from check_form: {message.text}')
    user_answer = message.text

    context_messages[message.from_user.id].append({"role": "user", "content": str(user_answer)})
    logging.info(f"context: {context_messages[message.from_user.id]}")

    get_form = openai.ChatCompletion.create(
        model=config.FT_MODEL_NAME,
        messages=context_messages[message.from_user.id],
        temperature=0.1
    )

    tokens[message.from_user.id]["prompt_1"] += int(get_form.usage.total_tokens)
    logging.info(f'текущие токены пользователя: {message.from_user.id} prompt_1={tokens[message.from_user.id]["prompt_1"]}')

    key_word = 'анкета'
    logging.info(get_form)

    if key_word in str(get_form.choices[0].message.content).lower():
        s2 = bot.send_message(message.chat.id, get_form.choices[0].message.content, reply_markup=markup_keyboard_accept)
        bot.register_next_step_handler(s2, final_check_form)
    else:
        mess = bot.send_message(message.chat.id, get_form.choices[0].message.content)
        bot.register_next_step_handler(mess, check_form)


def final_check_form(message: types.Message):
    ok = message.text

    if ok == 'Да':
        bot.send_message(message.chat.id,"Отлично! Составляю для тебя программу, это займет не больше минуты.", reply_markup=markup_keyboard_accept)
        context_messages[message.from_user.id].append({"role": "assistant", "content": "Выдай полученную форму, без лишнего текста, ничего не пиши кроме анкеты"})

        get_ready_form = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages[message.from_user.id],
            temperature=0.1
        )

        tokens[message.from_user.id]["prompt_1"] += int(get_ready_form.usage.total_tokens)
        logging.info(f'текущие токены пользователя: {message.from_user.id} prompt_1={tokens[message.from_user.id]["prompt_1"]}')

        logging.info(f'Получили готовую анкету: {get_ready_form.choices[0].message.content}')

        context_messages_program[message.from_user.id].append({"role": "system", "content": "Ты - тренер по фитнесу, который составляет индивидуальную программу спортивных занятий дома. Не здоровайся с пользователем. У тебя есть анкета которую ты получаешь от пользователя. Сделай логичную программу с учётом анкеты пользователя. Сделай программу в следующем формате: название упражнения: (количество подходов, количество повторений/время в позиции) {краткая пошаговая инструкция по выполнению упражнений}.Обязательно разграничь каждое упражнение с начала и с конца символом '*' (пример:*1.Прогулка на месте: (2 минуты) {Постепенно увеличивай темп, поднимай колени выше, размахивай руками}*). Подстраивай количество подходов и повторений в зависимости от уровня физической подготовки пользователя, возраста и пола. Общайся с пользователем на «ты». Помни, тренировка начинается с разминки, далее основная часть (силовая), а в конце заминка. Предлагай не более 4-5 упражнений на каждый этап тренировки. Ты должен иметь в виду все данные предоставленные в анкете. Сделай предупреждение «с осторожностью из-за {физическое ограничение}, если упражнение затрагивает физическое ограничение. После создания программы спроси у пользователя подходит ли ему программа и что можно изменить. Если пользователя что-то не устраивает,сразу выдавай измененную программу. Не задавай лишних вопросов."})
        context_messages_program[message.from_user.id].append({"role": "user", "content": get_ready_form.choices[0].message.content})
        context_messages[message.from_user.id].clear()

        logging.info('создаем программу на основе анкеты пользователя!')

        pre_program = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages_program[message.from_user.id],
            temperature=0.1
        )

        tokens[message.from_user.id]["prompt_2"] += int(pre_program.usage.total_tokens)
        logging.info(f'текущие токены пользователя: {message.from_user.id} prompt_2={tokens[message.from_user.id]["prompt_2"]}')

        check = bot.send_message(message.chat.id, pre_program.choices[0].message.content,
                                 reply_markup=markup_keyboard_accept)
        bot.register_next_step_handler(check, check_program)
    else:

        context_messages[message.from_user.id].append({"role": "user", "content": str(ok)})
        logging.info(f"context: {context_messages[message.from_user.id]}")

        edit_form = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages[message.from_user.id],
            temperature=0.1
        )
        tokens[message.from_user.id]["prompt_1"] += int(edit_form.usage.total_tokens)
        logging.info(f'текущие токены пользователя: {message.from_user.id} prompt_1={tokens[message.from_user.id]["prompt_1"]}')

        check = bot.send_message(message.chat.id, edit_form.choices[0].message.content)
        bot.register_next_step_handler(check, check_form)


def check_program(message: types.Message):
    user_answer = message.text
    logging.info(f'from check_program {user_answer}')

    if user_answer == 'Да':
        bot.send_message(message.chat.id, "Хорошо, пожалуйста подожди, сохраняю твою программу!")
        logging.info(f'Сохраняем программу для пользователя {message.from_user.id}')

        context_messages_program[message.from_user.id].append({"role": "assistant", "content": "Выдай созданную программу"})

        get_program = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages_program[message.from_user.id],
            temperature=0.1
        )
        logging.info(f'программа {get_program.choices[0].message.content}')
        a = str(get_program.choices[0].message.content).replace("\n", " ")
        a = a.split("*")

        list_exercises = []

        for elem in a:
            if elem and elem[0].isdigit():
                list_exercises.append(elem.split("*")[0])

        BotDatabase.insert(message.from_user.id, list_exercises)

        bot.send_message(message.chat.id,"Я сохранил твою программу! Если ты хочешь начать тренировку сейчас нажми /start_sport")

    else:
        context_messages_program[message.from_user.id].append({"role": "user", "content": user_answer})
        form = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages_program[message.from_user.id],
            temperature=0.1
        )
        tokens[message.from_user.id]["prompt_2"] += int(form.usage.total_tokens)
        logging.info(f'текущие токены пользователя: {message.from_user.id} prompt_2={tokens[message.from_user.id]["prompt_2"]}')

        check = bot.send_message(message.chat.id, form.choices[0].message.content, reply_markup=markup_keyboard_accept)
        bot.register_next_step_handler(check, check_program)

@bot.message_handler(commands=['start_sport'])
def start_sport(message: types.Message):
    if not message.from_user.id in user_feedback.keys():
        user_feedback[message.from_user.id] = []
    bot.send_message(message.chat.id,"Отлично что ты решил начать тренировку! Загружаю твою программу и вперед тренироваться")
    time.sleep(0.4)
    logging.info(f"Получаем упраженения из бд для пользователя {message.from_user.id}")

    exercises = BotDatabase.get_exercises(message.from_user.id)
    count_exercises = len(exercises)

    logging.info(f"Получили упражнения пользователя, из количество - {count_exercises}, упражнения - {exercises}")

    first = bot.send_message(message.chat.id, f"Упражнение {exercises[0]}", reply_markup=markup_keyboard_exercises)
    bot.register_next_step_handler(first, check_ex, exercises, 0)


def check_ex(message: types.Message, exercises, n):
    user_answer = message.text
    logging.info(user_answer)
    if user_answer == "Я выполнил упражнение":
        rand_n = random.randint(0,len(config.chill_phrases) - 1)
        chill = bot.send_message(message.chat.id, f"{config.chill_phrases[rand_n]}\n(отдых 1 минута)", reply_markup=markup_keyboard_chill)
        n += 1
        bot.register_next_step_handler(chill, next_exercise, n, exercises)


def next_exercise(message: types.Message, n, exercises):
    logging.info(f'{message.text}, {n}, {exercises}')
    if n == len(exercises):
        bot.send_message(message.chat.id, "Поздравляю тебя! Ты завершил тренировку! Теперь, пожалуйста ответь на 3 коротких вопроса.")
        final = bot.send_message(message.chat.id, "Как твое самочувствие?")
        bot.register_next_step_handler(final, first_question)
    else:
        next = bot.send_message(message.chat.id, f"Упражнение {exercises[n]}", reply_markup=markup_keyboard_exercises)
        bot.register_next_step_handler(next, check_ex, exercises, n)


def first_question(message: types.Message):
    user_feedback[message.from_user.id].append(message.text)
    second = bot.send_message(message.chat.id, "Все ли тебе понравилось?")
    bot.register_next_step_handler(second, second_question)


def second_question(message: types.Message):
    user_feedback[message.from_user.id].append(message.text)
    third = bot.send_message(message.chat.id, "Что стоит поменять в следующий раз?")
    bot.register_next_step_handler(third, third_question)


def third_question(message: types.Message):
    user_feedback[message.from_user.id].append(message.text)
    BotDatabase.insert_feedback(message.from_user.id, '\n'.join(user_feedback[message.from_user.id]))
    bot.send_message(message.chat.id, "Спасибо за то, что оставил фидбек, это важно для нас! Удачи тебе!")
    n = random.randint(0, len(config.quotes) - 1)
    bot.send_message(message.chat.id, f"{config.quotes[n]}")


@bot.message_handler(commands=['schedule'])
def schedule():
    pass


@bot.message_handler(commands=['statistics'])
def statistics():
    pass


@bot.message_handler(commands=['edit_prog'])
def edit_prog():
    pass


@bot.message_handler(commands=['about'])
def about(message: types.Message):
    bot.send_message(message.chat.id, "Привет, я GymLessBot. Я составлю для тебя персонализированную программу тренировки дома.\nЯ учитываю различные факторы при составлении программы.\nНапример, я смотрю на твой уровень физической подготовки и пожелания по упражнениям. Также я подстрою программу, если у тебя есть какие либо травмы.")


bot.infinity_polling()
