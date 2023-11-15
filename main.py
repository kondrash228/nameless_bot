import time
import json
import random
import logging

from datetime import datetime

import openai
import pytz
import telebot

from telebot import types

import config
from database import BotDatabase
from keyboards import (markup_keyboard_accept,markup_keyboard_exercises,
                       markup_keyboard_chill, markup_keyboard_change_schedule,
                       markup_keyboard_set_schedule, markup_keyboard_set_program)

tz = pytz.timezone('Europe/Moscow')
openai.api_key = config.OPENAI_TOKEN
bot = telebot.TeleBot(token=config.TG_BOT_TOKEN)

file_log = logging.FileHandler(f'{str(datetime.now(tz)).split()[0]}_gymless_bot.log')
console_out = logging.StreamHandler()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=(file_log, console_out))

BotDatabase = BotDatabase('fintess-ai.sqlite')

# if len(bot.get_my_commands()) == 0:
logging.info('У бота нет настроенных команд, устанавливаем их')
bot.set_my_commands([
        telebot.types.BotCommand('/start', "Главная"),
        telebot.types.BotCommand('/start_sport', "Начать тренировку сейчас"),
        telebot.types.BotCommand('/schedule', "Запланированые тренировки"),
        telebot.types.BotCommand('/edit_prog', "Поменять/посмотреть тренировочную программу"),
        telebot.types.BotCommand('/about', "О боте"),
    ])

context_messages = {}
context_messages_program = {}
context_messages_schedule = {}
context_messages_clear_program = {}
context_messages_remake_program = {}
context_messages_remake_program_json = {}

tokens = {}
user_feedback = {}

clear_program = []


@bot.message_handler(commands=['start'])
def main(message: types.Message):
    if not BotDatabase.check_user(user_id=message.from_user.id):
        logging.info(f'Новый пользователь с user_id: {message.from_user.id}, добавляем его в базу данных и начинаем диалог')
        BotDatabase.add_user(message.from_user.id)

        start_msg = bot.send_message(message.chat.id, "Привет, я GymLessBot. Я составлю для тебя персонализированную программу тренировки дома.\nРасскажи в голосовом или напиши сообщением:\n*Как тебя зовут?\n*Сколько тебе лет?\n*Есть ли у тебя какой-либо спортивный инвентарь?")

        if message.from_user.id not in context_messages.keys():
            logging.info(f'Для пользователя user_id: {message.from_user.id} нет контекста. Создаем контекст и счетчик токенов')
            context_messages[message.from_user.id] = []
            context_messages_program[message.from_user.id] = []
            user_feedback[message.from_user.id] = []
            context_messages_schedule[message.from_user.id] = []
            context_messages_clear_program[message.from_user.id] = []
            tokens[message.from_user.id] = {"prompt_1": {"input": 0, "output": 0}, "prompt_2": {"input": 0, "output": 0}}

        logging.info(f'Задаем system на промпт 1')

        context_messages[message.from_user.id].append({"role": "system", "content": "Твоя задача сделать анкету по данным предоставлеными пользователем. Формат анкеты следующий: имя, пол, возраст, уровень физической подготовки (от 1 до 10), продолжительность занятия, физические ограничения, наличие спортивного инвентаря, пожелания по упражнениям. Не задавай вопрос про пол (гендер) пользователя, определи пол по имени. Вопрос про продолжительность занятия должен звучать так: 'Какая продолжительность одного занятия для тебя оптимальна?'. Общайся с пользователем на «ты». Задавай уточняющие вопросы до тех пор пока анкету не заполнишь полностью. Задавай вопросы строго по анкете. Обязательно спроси про пожелания по упражнениям. Пиши кратко, не давай лишних комментариев. Покажи анкету пользователю только после того, как она будет полностью заполнена. Если анкета составлена успешно, начни своё сообщение с 'Твоя анкета'. Задавай не более двух вопросов за один раз. По завершению анкеты, спроси все ли верно с ней. Скажи, что можно написать если что-то не так. "})
        context_messages[message.from_user.id].append({"role": "assistant", "content": "Как тебя зовут? Сколько тебе лет? Если у тебя спортивный инвентарь?"})

        bot.register_next_step_handler(start_msg, get_info)

    else:
        context_messages[message.from_user.id] = []
        context_messages_program[message.from_user.id] = []
        user_feedback[message.from_user.id] = []
        context_messages_schedule[message.from_user.id] = []
        context_messages_clear_program[message.from_user.id] = []
        tokens[message.from_user.id] = {"prompt_1": {"input": 0, "output": 0}, "prompt_2": {"input": 0, "output": 0}}

        logging.info(f'Пользователь с user_id: {message.from_user.id} уже существует')
        if message.from_user.id not in user_feedback.keys():
            user_feedback[message.from_user.id] = []
        bot.send_message(message.from_user.id, "Привет, вижу ты уже зарегестрирован.\nДля того что бы начать тренировку нажимай /start_sport или воспользуйся нашим меню.")


def get_info(message: types.Message):
    if message.content_type == 'voice':

        logging.info('Пользователь отправил голосовое сообщение. Вызываем whisper и конвертируем в текст')
        bot.send_message(message.chat.id, "Понял тебя, начинаю составлять твою анкету!")

        file_info = bot.get_file(message.voice.file_id)
        df = bot.download_file(file_info.file_path)

        logging.info(f'Получили голосовое сообщение от пользователя (user_id: {message.from_user.id}),  file_info: {file_info}, передаем полученный файл в whisper')
        with open(f'voice_messages/{message.from_user.id}.mp3', 'wb') as file:
            logging.info(f'Записваем полученное голосовое сообщение')
            file.write(df)
            logging.info(f'Голосовое успешно записано')

        audio_file = open(f'voice_messages/{message.from_user.id}.mp3', 'rb')
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        transcripted_text = str(transcript['text'])

        logging.info(f'Получили распознанный текст из голосового сообщения пользователя с user_id: {message.from_user.id}, сообщение: {transcripted_text}')
        logging.info(f'Добавляем полученный текст в контекст пользователя (user_id: {message.from_user.id})')

        context_messages[message.from_user.id].append({"role": "user", "content": transcripted_text})

        form_completion = openai.ChatCompletion.create(
            model=config.GPT_4_TURBO,
            messages=context_messages[message.from_user.id],
            temperature=0.8
        )
        logging.info(f'Получили ответ от GPT. Ответ: {form_completion.choices[0].message.content}')

        tokens[message.from_user.id]['prompt_1']['input'] += int(form_completion.usage.prompt_tokens)
        tokens[message.from_user.id]['prompt_1']['output'] += int(form_completion.usage.completion_tokens)
        logging.info(f'Считаем токены для пользователя (user_id: {message.from_user.id}): {message.from_user.id}, итого prompt_1_input = {tokens[message.from_user.id]["prompt_1"]["input"]}, prompt_1_output = {tokens[message.from_user.id]["prompt_1"]["output"]}')

        context_messages[message.from_user.id].append({"role": "assistant", "content": form_completion.choices[0].message.content})
        key_word = 'анкета'

        if key_word in str(form_completion.choices[0].message.content).lower():
            logging.info(f'Слово тригре в ответе от GPT, выдаем клаваиатуру, если ответ пользователя положительный, переходим к промпту 2')
            s2 = bot.send_message(message.chat.id, form_completion.choices[0].message.content,
                                  reply_markup=markup_keyboard_accept)
            bot.register_next_step_handler(s2, final_check_form)
        else:
            logging.info('Переходим к уточняющим вопросам, если они нужны')
            check_message = bot.send_message(message.chat.id, form_completion.choices[0].message.content)
            bot.register_next_step_handler(check_message, check_form)

    elif message.content_type == 'text':
        logging.info('Пользователь отправил текстоовое сообщение')

        text_from_user = message.text
        bot.send_message(message.chat.id, "Понял тебя, начинаю составлять твою анкету!")

        logging.info(f'Сообщение пользователя (user_id: {message.from_user.id}): {text_from_user}')
        logging.info(f'Добавляем полученный текст в контекст пользователя (user_id: {message.from_user.id})')

        context_messages[message.from_user.id].append({"role": "user", "content": str(text_from_user)})

        form_completion = openai.ChatCompletion.create(
            model=config.GPT_4_TURBO,
            messages=context_messages[message.from_user.id],
            temperature=0.8
        )

        logging.info(f'Получили ответ GPT. Ответ: {form_completion.choices[0].message.content}')

        tokens[message.from_user.id]['prompt_1']['input'] += int(form_completion.usage.prompt_tokens)
        tokens[message.from_user.id]['prompt_1']['output'] += int(form_completion.usage.completion_tokens)
        logging.info(f'Считаем токены для пользователя (user_id: {message.from_user.id}): {message.from_user.id}, итого prompt_1_input = {tokens[message.from_user.id]["prompt_1"]["input"]}, prompt_1_output = {tokens[message.from_user.id]["prompt_1"]["output"]}')

        context_messages[message.from_user.id].append({"role": "assistant", "content": form_completion.choices[0].message.content})

        key_word = 'анкета'

        if key_word in str(form_completion.choices[0].message.content).lower():
            logging.info(f'Слово тригре в ответе от GPT, выдаем клаваиатуру, если ответ пользователя положительный, переходим к промпту 2')
            s2 = bot.send_message(message.chat.id, form_completion.choices[0].message.content,reply_markup=markup_keyboard_accept)
            bot.register_next_step_handler(s2, final_check_form)
        else:
            logging.info('Переходим к уточняющим вопросам, если они нужны')
            check_message = bot.send_message(message.chat.id, form_completion.choices[0].message.content)
            bot.register_next_step_handler(check_message, check_form)


def check_form(message: types.Message):
    logging.info(f'Ответ пользователя (check_form): {message.text}')
    user_answer = message.text

    logging.info('Добавляем ответ пользователя в контекст')

    context_messages[message.from_user.id].append({"role": "user", "content": str(user_answer)})

    get_form = openai.ChatCompletion.create(
        model=config.GPT_4_TURBO,
        messages=context_messages[message.from_user.id],
        temperature=0.8
    )
    logging.info(f'Ответ от GPT получен. Ответ: {get_form.choices[0].message.content}')

    tokens[message.from_user.id]['prompt_1']['input'] += int(get_form.usage.prompt_tokens)
    tokens[message.from_user.id]['prompt_1']['output'] += int(get_form.usage.completion_tokens)
    logging.info(f'Считаем токены для пользователя (user_id: {message.from_user.id}): {message.from_user.id}, итого prompt_1_input = {tokens[message.from_user.id]["prompt_1"]["input"]}, prompt_1_output = {tokens[message.from_user.id]["prompt_1"]["output"]}')

    logging.info(f'Проверяем, есть ли слово тригер(анкета) в ответе от GPT')

    key_word = 'анкета'

    if key_word in str(get_form.choices[0].message.content).lower():
        logging.info(f'Слово тригре в ответе от GPT, выдаем клаваиатуру, если ответ пользователя положительный, переходим к промпту 2')
        s2 = bot.send_message(message.chat.id, get_form.choices[0].message.content, reply_markup=markup_keyboard_accept)
        bot.register_next_step_handler(s2, final_check_form)
    else:
        logging.info(f'Слово тригер НЕ в ответе от GPT, продолжаем задавать вопросы пользователю')
        mess = bot.send_message(message.chat.id, get_form.choices[0].message.content)
        bot.register_next_step_handler(mess, check_form)


def final_check_form(message: types.Message):
    ok = message.text
    logging.info(f'Переходим к финальной проверке анкеты пользователя. Ответ пользователя на форму: {ok}')
    if ok == 'Да':
        logging.info(f'Пользователь (user_id: {message.from_user.id}) подтвердил корректность анкеты, начианем составлять для него программу')
        bot.send_message(message.chat.id,"Отлично! Составляю для тебя программу, это займет не больше минуты.")
        logging.info(f'Перед составлением программы, получаем заполненую json форму пользователя без лишнего текста, для того, чтобы передать ее в промпт 2')


        context_messages[message.from_user.id].append({"role": "assistant", "content": 'Переделай этот текст в json формат, где "profile" - массив внутри которого есть "name", "sex", "age","level","duration","issues","equipment", "wishes" . Не давай никаких комментариев.'})

        get_ready_form = openai.ChatCompletion.create( #1.5
            model=config.GPT_3_5,
            messages=context_messages[message.from_user.id],
            temperature=0
        )

        json_form = json.loads(get_ready_form.choices[0].message.content.replace("'", '"'))

        logging.info(f'json form {json_form}')

        BotDatabase.insert_user_form(message.from_user.id, json_form)

        logging.info(f'Получили форму пользователя (user_id: {message.from_user.id}), форма: {get_ready_form.choices[0].message.content}, передаем ее во 2 промпт')

        tokens[message.from_user.id]['prompt_1']['input'] += int(get_ready_form.usage.prompt_tokens)
        tokens[message.from_user.id]['prompt_1']['output'] += int(get_ready_form.usage.completion_tokens)
        logging.info(f'Считаем токены для пользователя (user_id: {message.from_user.id}): {message.from_user.id}, итого prompt_1_input = {tokens[message.from_user.id]["prompt_1"]["input"]}, prompt_1_output = {tokens[message.from_user.id]["prompt_1"]["output"]}')

        context_messages_program[message.from_user.id].append({"role": "system", "content": "Ты - тренер по фитнесу, который составляет индивидуальную программу спортивных занятий дома. Не здоровайся с пользователем. Общайся с пользователем на «ты». У тебя есть анкета которую ты получаешь от пользователя. Сделай логичную программу с учётом анкеты пользователя. Рядом с каждым упражнением подпиши: количество подходов, количество повторений/времени в позиции. Подстраивай количество подходов и повторений в зависимости от уровня физической подготовки пользователя (от 1 до 10). Давай точное количество повторений/время. Помни, тренировка начинается с разминки, далее основная часть (силовая), а в конце заминка. Предлагай не более 4-5 на каждый этап тренировки. Ты должен иметь в виду все данные предоставленные в анкете. Начинай своё сообщение только с 'Твоя программа тренировки', когда отдаёшь программу полностью. Сделай предупреждение, если упражнение затрагивает физическое ограничение. После создания программы спроси у пользователя подходит ли ему программа. Если нет, то что можно изменить. При внесении изменений в программу, выводи только измененное упражнение/упражнения. Повтори программу полностью, только после одобрительного ответа пользователя. Не прощайся с пользователем. "})
        context_messages_program[message.from_user.id].append({"role": "user", "content": get_ready_form.choices[0].message.content})
        context_messages[message.from_user.id].clear()

        logging.info('Создаем программу на основе полученной формы (анкеты), ждем ответ от GPT')

        pre_program = openai.ChatCompletion.create(
            model=config.GPT_4_TURBO,
            messages=context_messages_program[message.from_user.id],
            temperature=0.4
        )

        logging.info(f'Ответ от GPT получен, программа готова: {pre_program.choices[0].message.content}')

        tokens[message.from_user.id]['prompt_2']['input'] += int(pre_program.usage.prompt_tokens)
        tokens[message.from_user.id]['prompt_2']['output'] += int(pre_program.usage.completion_tokens)
        logging.info(f'Считаем токены для пользователя (user_id: {message.from_user.id}): {message.from_user.id}, итого prompt_2_input = {tokens[message.from_user.id]["prompt_2"]["input"]}, prompt_2_output = {tokens[message.from_user.id]["prompt_2"]["output"]}')

        check = bot.send_message(message.chat.id, pre_program.choices[0].message.content,reply_markup=markup_keyboard_accept, parse_mode="Markdown")
        context_messages_clear_program[message.from_user.id].append({"role": "assistant", "content": pre_program.choices[0].message.content})

        bot.register_next_step_handler(check, check_program)

    else:

        context_messages[message.from_user.id].append({"role": "user", "content": str(ok)})
        logging.info(f"context: {context_messages[message.from_user.id]}")

        edit_form = openai.ChatCompletion.create(
            model=config.GPT_4_TURBO,
            messages=context_messages[message.from_user.id],
            temperature=0.4
        )

        tokens[message.from_user.id]['prompt_1']['input'] += int(edit_form.usage.prompt_tokens)
        tokens[message.from_user.id]['prompt_1']['output'] += int(edit_form.usage.completion_tokens)
        logging.info(f'Считаем токены для пользователя (user_id: {message.from_user.id}): {message.from_user.id}, итого prompt_1_input = {tokens[message.from_user.id]["prompt_1"]["input"]}, prompt_1_output = {tokens[message.from_user.id]["prompt_1"]["output"]}')

        check = bot.send_message(message.chat.id, edit_form.choices[0].message.content)
        bot.register_next_step_handler(check, check_form)


def check_program(message: types.Message):
    user_answer = message.text
    logging.info(f'from check_program {user_answer}')

    if user_answer == 'Да':
        bot.send_message(message.chat.id, "Хорошо, пожалуйста подожди, сохраняю твою программу!")
        logging.info(f'Сохраняем программу для пользователя {message.from_user.id}')

        context_messages_clear_program[message.from_user.id].append({"role": "system", "content": 'Сделай этот текст в json формат, где "training" - массив внутри которого есть массивы "Разминка" , "Основная часть", "Заминка" внутри которых есть "Упражнение 1", "Упражнение 2", "Упражнение 3" и так далее. Не давай никаких комментариев. Не меняй содержание текста.'})
        raw_program = """
                **Разминка**
                1.Приседания без веса - 3 подхода по 15 повторений
                2.Бег на месте - 3 минуты
                3.Прыжки на месте - 3 подхода по 30 секунд
                4.Размахивание руками - 3 подхода по 20 раз каждой рукой

                **Основная часть**
                1.Отжимания - 5 подходов по 20 повторений
                2.Подтягивания (если есть турник) - 4 подхода по 12 повторений
                3.Планка - 4 подхода по 1 минуте
                4.Берпи - 4 подхода по 15 повторений

                **Заминка**
                1.Растяжка грудных мышц - 30 секунд на каждую сторону
                2.Растяжка бицепсов и предплечий - 30 секунд на каждую руку
                3.Растяжка квадрицепсов - 30 секунд на каждую ногу
                4.Поза ребенка - 1 минута

                """

        context_messages_clear_program[message.from_user.id].append({"role": "user", "content": f"{raw_program}"})

        jsonf_example = """
        {
          "training": {
            "Разминка": [
              "Приседания без веса - 3 подхода по 15 повторений",
              "Бег на месте - 3 минуты",
              "Прыжки на месте - 3 подхода по 30 секунд",
              "Размахивание руками - 3 подхода по 20 раз каждой рукой"
            ],
            "Основная часть": [
              "Отжимания - 5 подходов по 20 повторений",
              "Планка - 4 подхода по 1 минуте",
              "Берпи - 4 подхода по 15 повторений",
              "Отжимания с узкой постановкой рук (для трицепсов) - 4 подхода по 15 повторений"
            ],
            "Заминка": [
              "Растяжка квадрицепсов - по 1 минуте на каждую ногу",
              "Растяжка грудных мышц - 2 подхода по 30 секунд",
              "Растяжка трицепсов - по 30 секунд на каждую руку",
              "Дыхательные упражнения - 3 минуты"
            ]
          }
        }
        """
        context_messages_clear_program[message.from_user.id].append({"role": "assistant", "content": f'{jsonf_example}'})

        get_program = openai.ChatCompletion.create( # prompt 2.5
            model=config.GPT_3_5,
            messages=context_messages_clear_program[message.from_user.id], # берем только программу
            temperature=0
        )

        logging.info(f'json prog: {get_program.choices[0].message.content}')

        json_program_ready = json.loads(get_program.choices[0].message.content)
        BotDatabase.insert_user_program(message.from_user.id, json_program_ready)

        bot.send_message(message.chat.id,"Я сохранил твою программу!")
        timetable = bot.send_message(message.chat.id, "В какие дни недели и время тебе удобно заниматься?")

        context_messages_schedule[message.from_user.id].append({"role": "system", "content": "Твоя задача написать расписание занятий по информации от пользователя в следующем формате: день недели: время (в 24 часовом формате, пример: 15:45 или 07:25). Каждый день недели напиши отдельной строкой. Дай только один временный слот, если пользователь даёт несколько. Пиши кратко, не задавай лишних вопросов. Общайся с пользователем на «ты». Если расписание составлено, начни своё сообщение с 'Твоё расписание'. Спроси всё ли верно."})
        bot.register_next_step_handler(timetable, set_user_schedule)

    else:
        context_messages_program[message.from_user.id].append({"role": "user", "content": user_answer})
        form = openai.ChatCompletion.create(
            model=config.GPT_4_TURBO,
            messages=context_messages_program[message.from_user.id],
            temperature=0.4
        )
        tokens[message.from_user.id]['prompt_2']['input'] += int(form.usage.prompt_tokens)
        tokens[message.from_user.id]['prompt_2']['output'] += int(form.usage.completion_tokens)
        logging.info(f'Считаем токены для пользователя (user_id: {message.from_user.id}): {message.from_user.id}, итого prompt_2_input = {tokens[message.from_user.id]["prompt_2"]["input"]}, prompt_2_output = {tokens[message.from_user.id]["prompt_2"]["output"]}')

        check = bot.send_message(message.chat.id, form.choices[0].message.content, reply_markup=markup_keyboard_accept)
        bot.register_next_step_handler(check, check_program)


def set_user_schedule(message: types.Message):
    user_answer = message.text
    context_messages_schedule[message.from_user.id].append({"role": "user", "content": user_answer})

    user_schedule = openai.ChatCompletion.create( # 3
        model=config.GPT_4_TURBO,
        messages=context_messages_schedule[message.from_user.id],
        temperature=0.3
    )

    context_messages_schedule[message.from_user.id].append({"role":"assistant", "content": user_schedule.choices[0].message.content})

    check = bot.send_message(message.chat.id, user_schedule.choices[0].message.content, reply_markup=markup_keyboard_accept)
    bot.register_next_step_handler(check, check_schedule)


def check_schedule(message: types.Message):
    user_answer = message.text
    if user_answer == 'Да':
        bot.send_message(message.chat.id, "Хорошо, сохраню твое распиасание! Ты можешь начать программу сейчас, нажав /start_sport")
        context_messages_schedule[message.from_user.id].append({"role":"system", "content": "Переделай этот текст в json формат, где 'schedule' - массив внутри которого есть 'dayOfWeek'  и 'time'. Не давай никаких комментариев."})
        json_schedule = openai.ChatCompletion.create( #3.5
            model=config.GPT_3_5,
            messages=context_messages_schedule[message.from_user.id],
            temperature=0
        )
        logging.info(f'{json_schedule.choices[0].message.content}')
        json_schedule_ready = json.loads(json_schedule.choices[0].message.content)
        BotDatabase.insert_schedule(message.from_user.id, json_schedule_ready)

    else:
        context_messages_schedule[message.from_user.id].append({"role": "user", "content": user_answer})
        change_schedule = openai.ChatCompletion.create( # 3
            model=config.GPT_4_TURBO,
            messages=context_messages_schedule[message.from_user.id],
            temperature=0.3
        )
        change = bot.send_message(message.chat.id, change_schedule.choices[0].message.content)
        bot.register_next_step_handler(change, set_user_schedule)


@bot.message_handler(commands=['start_sport'])
def start_sport(message: types.Message):
    if message.from_user.id not in user_feedback.keys():
        user_feedback[message.from_user.id] = []
    count_exercises = None
    exercises = None
    try:
        exercises = BotDatabase.get_user_program(message.from_user.id)
        count_exercises = len(exercises)
    except:
        bot.send_message(message.chat.id, "К сожалению я не смог найти твою спортивную программу\nДля того, чтобы создать ее, жми /start!")
    if exercises:
        if count_exercises == 0:
            bot.send_message(message.chat.id, "К сожалению я не смог найти твою спортивную программу\nДля того, чтобы создать ее, жми /start!")
        else:
            bot.send_message(message.chat.id,"Отлично что ты решил начать тренировку! Загружаю твою программу и вперед тренироваться")
            time.sleep(0.3)
            logging.info(f"Получаем упраженения из бд для пользователя {message.from_user.id}")

            logging.info(f"Получили упражнения пользователя, из количество - {count_exercises}, упражнения - {exercises}")

            first = bot.send_message(message.chat.id, f"Упражнение {exercises[0][0]}", reply_markup=markup_keyboard_exercises)
            bot.register_next_step_handler(first, check_ex, exercises, 0, 0)


def check_ex(message: types.Message, exercises, n, n2):
    user_answer = message.text
    logging.info(user_answer)
    if user_answer == "Я выполнил упражнение":
        rand_n = random.randint(0,len(config.chill_phrases) - 1)
        chill = bot.send_message(message.chat.id, f"{config.chill_phrases[rand_n]}\n(отдых 1 минута)", reply_markup=markup_keyboard_chill)
        n += 1
        if n == len(exercises[n2]):
            n2 += 1
            n = 0
        bot.register_next_step_handler(chill, next_exercise, exercises, n, n2)


def next_exercise(message: types.Message, exercises, n, n2):
    logging.info(f'{message.text}, {n}, {n2}, {exercises}')
    if n2 == len(exercises):
        bot.send_message(message.chat.id, "Поздравляю тебя! Ты завершил тренировку! Теперь, пожалуйста ответь на 3 коротких вопроса.")
        final = bot.send_message(message.chat.id, "Как твое самочувствие?")
        bot.register_next_step_handler(final, first_question)
    else:
        next = bot.send_message(message.chat.id, f"Упражнение {exercises[n2][n]}", reply_markup=markup_keyboard_exercises)
        bot.register_next_step_handler(next, check_ex, exercises, n, n2)


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
def schedule(message: types.Message):
    context_messages_schedule[message.from_user.id] = []
    context_messages_schedule[message.from_user.id].append({"role": "system", "content": "Твоя задача написать расписание занятий по информации от пользователя в следующем формате: день недели: время (в 24 часовом формате, пример: 15:45 или 07:25). Каждый день недели напиши отдельной строкой. Дай только один временный слот, если пользователь даёт несколько. Пиши кратко, не задавай лишних вопросов. Общайся с пользователем на «ты». Если расписание составлено, начни своё сообщение с 'Твоё расписание'. Спроси всё ли верно."})

    get_schedule = BotDatabase.get_user_schedule(message.from_user.id)
    if len(get_schedule) == 0:
        bot.send_message(message.chat.id, "Упс, пока что не нашел твое расписание (")
        change = bot.send_message(message.chat.id, "Если ты хочешь установить расписание, нажимай на кнопку ниже",reply_markup=markup_keyboard_set_schedule)
        bot.register_next_step_handler(change, edit_schedule)
    else:
        bot.send_message(message.chat.id, 'Твое расписание:\n\n' + '\n'.join(get_schedule).replace(',',' '))
        change = bot.send_message(message.chat.id, "Если ты хочешь изменить расписание, нажимай на кнопку ниже", reply_markup=markup_keyboard_set_schedule)
        bot.register_next_step_handler(change, edit_schedule)


def edit_schedule(message: types.Message):
    user_answer = message.text

    if user_answer == 'Настроить новое расписание':
        change = bot.send_message(message.chat.id, "Хорошо, давай я установлю тебе новое расписание, напиши пожалуйста в какие дни недели и время тебе удобно заниматься")
        BotDatabase.drop_user_schedule(message.from_user.id)
        bot.register_next_step_handler(change, set_user_schedule)


@bot.message_handler(commands=['edit_prog'])
def edit_prog(message: types.Message):
    context_messages_remake_program[message.from_user.id] = []
    context_messages_remake_program_json[message.from_user.id] = []

    context_messages_remake_program[message.from_user.id].append({"role": "system", "content": "Ты - тренер по фитнесу, который составляет индивидуальную программу спортивных занятий дома. Не здоровайся с пользователем. Общайся с пользователем на «ты». У тебя есть анкета которую ты получаешь от пользователя. Сделай логичную программу с учётом анкеты пользователя. Рядом с каждым упражнением подпиши: количество подходов, количество повторений/времени в позиции. Подстраивай количество подходов и повторений в зависимости от уровня физической подготовки пользователя (от 1 до 10). Давай точное количество повторений/время. Помни, тренировка начинается с разминки, далее основная часть (силовая), а в конце заминка. Предлагай не более 4-5 на каждый этап тренировки. Ты должен иметь в виду все данные предоставленные в анкете. Начинай своё сообщение только с 'Твоя программа тренировки', когда отдаёшь программу полностью. Сделай предупреждение, если упражнение затрагивает физическое ограничение. Не прощайся с пользователем. "})
    program = None
    try:
        program = BotDatabase.get_user_program(message.from_user.id)
    except:
        check = bot.send_message(message.chat.id,
                                 "Не нашел твоей программы, для того чтобы создать ее жми на кнопку ниже",
                                 reply_markup=markup_keyboard_set_program)
        bot.register_next_step_handler(check, re_call_prompt)
    if program:
        if len(program) == 0:
            check = bot.send_message(message.chat.id, "Не нашел твоей программы, для того чтобы создать ее жми на кнопку ниже", reply_markup=markup_keyboard_set_program)
            bot.register_next_step_handler(check, re_call_prompt)
        else:
            start = '*Разминка*\n ' + '\n'.join(program[0]) + "\n"
            mid = '*Основная часть*\n ' + '\n'.join(program[1]) + "\n"
            end = '*Заминка*\n ' + '\n'.join(program[2])
            ready_prog = [start, mid, end]
            user_form = BotDatabase.get_user_form(message.from_user.id)

            ready_form = {"name": user_form[0], "sex": user_form[1], "age": user_form[2], "level": user_form[3], "duration": user_form[4], "issues": user_form[5], "equipment": user_form[6], "wishes": user_form[7]}

            check = bot.send_message(message.chat.id, 'Твоя программа\n\n' + '\n'.join(ready_prog), parse_mode="Markdown", reply_markup=markup_keyboard_set_program)

            context_messages_remake_program[message.from_user.id].append({"role": "user", "content": str('Твоя программа\n\n' + '\n'.join(ready_prog))})
            context_messages_remake_program[message.from_user.id].append({"role": "user", "content": str(ready_form)})

            bot.register_next_step_handler(check, re_call_prompt)


def re_call_prompt(message: types.Message):
    user_answer = message.text

    if user_answer == 'Настроить новую программу':
        BotDatabase.drop_user_program(message.from_user.id)

        change = bot.send_message(message.chat.id,"Хорошо, давай я создам тебе новую программу, напиши пожалуйста свои пожелания")
        bot.register_next_step_handler(change, remake_prog)


def remake_prog(message:types.Message):
    user_answer = message.text
    context_messages_remake_program[message.from_user.id].append({"role": "user", "content": user_answer})

    remake_program = openai.ChatCompletion.create(
        model=config.GPT_4_TURBO,
        messages=context_messages_remake_program[message.from_user.id],
        temperature=0.4
    )
    bot.send_message(message.chat.id, remake_program.choices[0].message.content)

    context_messages_remake_program_json[message.from_user.id].append({"role": "assistant", "content": remake_program.choices[0].message.content})
    context_messages_remake_program_json[message.from_user.id].append({"role": "system","content": 'Сделай этот текст в json формат, где "training" - массив внутри которого есть массивы "Разминка" , "Основная часть", "Заминка" внутри которых есть "Упражнение 1", "Упражнение 2", "Упражнение 3" и так далее. Не давай никаких комментариев. Не меняй содержание текста.'})
    raw_program = """
                    **Разминка**
                    1.Приседания без веса - 3 подхода по 15 повторений
                    2.Бег на месте - 3 минуты
                    3.Прыжки на месте - 3 подхода по 30 секунд
                    4.Размахивание руками - 3 подхода по 20 раз каждой рукой

                    **Основная часть**
                    1.Отжимания - 5 подходов по 20 повторений
                    2.Подтягивания (если есть турник) - 4 подхода по 12 повторений
                    3.Планка - 4 подхода по 1 минуте
                    4.Берпи - 4 подхода по 15 повторений

                    **Заминка**
                    1.Растяжка грудных мышц - 30 секунд на каждую сторону
                    2.Растяжка бицепсов и предплечий - 30 секунд на каждую руку
                    3.Растяжка квадрицепсов - 30 секунд на каждую ногу
                    4.Поза ребенка - 1 минута

                    """

    context_messages_remake_program_json[message.from_user.id].append({"role": "user", "content": f"{raw_program}"})

    jsonf_example = """
            {
              "training": {
                "Разминка": [
                  "Приседания без веса - 3 подхода по 15 повторений",
                  "Бег на месте - 3 минуты",
                  "Прыжки на месте - 3 подхода по 30 секунд",
                  "Размахивание руками - 3 подхода по 20 раз каждой рукой"
                ],
                "Основная часть": [
                  "Отжимания - 5 подходов по 20 повторений",
                  "Планка - 4 подхода по 1 минуте",
                  "Берпи - 4 подхода по 15 повторений",
                  "Отжимания с узкой постановкой рук (для трицепсов) - 4 подхода по 15 повторений"
                ],
                "Заминка": [
                  "Растяжка квадрицепсов - по 1 минуте на каждую ногу",
                  "Растяжка грудных мышц - 2 подхода по 30 секунд",
                  "Растяжка трицепсов - по 30 секунд на каждую руку",
                  "Дыхательные упражнения - 3 минуты"
                ]
              }
            }
            """
    context_messages_remake_program_json[message.from_user.id].append({"role": "assistant", "content": f'{jsonf_example}'})

    get_program = openai.ChatCompletion.create(  # prompt 2.5
        model=config.GPT_3_5,
        messages=context_messages_remake_program_json[message.from_user.id],  # берем только программу
        temperature=0
    )

    logging.info(f'json prog: {get_program.choices[0].message.content}')

    json_program_ready = json.loads(get_program.choices[0].message.content)
    BotDatabase.insert_user_program(message.from_user.id, json_program_ready)

    bot.send_message(message.chat.id, "Я сохранил твою программу!")


@bot.message_handler(commands=['about'])
def about(message: types.Message):
    bot.send_message(message.chat.id, "Привет, я GymLessBot. Я составлю для тебя персонализированную программу тренировки дома.\nЯ учитываю различные факторы при составлении программы.\nНапример, я смотрю на твой уровень физической подготовки и пожелания по упражнениям. Также я подстрою программу, если у тебя есть какие либо травмы.")


@bot.message_handler()
def all_messages(message: types.Message):
    if message.content_type == 'voice':
        bot.send_message(message.chat.id, "Извини, я пока не могу распознать твои слова, напиши мне текстом")


bot.infinity_polling()
