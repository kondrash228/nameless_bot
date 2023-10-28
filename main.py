import openai
import telebot
import gtts
import sqlite3
import logging
import json
import requests

from gtts import gTTS
from telebot import types
from tenacity import retry, wait_random_exponential, stop_after_attempt
from termcolor import colored

import config
from database import BotDatabase
from keyboards import markup_keyboard_accept, markup_keyboard_accept_call

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

context_messages = []
context_messages_program = []

context_messages.append({"role": "system", "content": "Твоя задача сделать анкету по данным предоставлеными пользователем. Формат анкеты следующий:имя,пол,возраст,уровень физической подготовки (от 1 до 10),длительность занятия,физические ограничения,наличие спортивного инвентаря,пожелания по упражнениям. Не задавай вопрос про пол (гендер) пользователя,определи пол по имени. Общайся с пользователем на «ты». Задавай уточняющие вопросы до тех пор пока анкету не заполнишь полностью. Задавай вопросы строго по анкете. Задавай по одному вопросу за раз. Пиши более кратко. По завершению анкеты, спроси, все ли верно с ней и спроси нужно ли что-то исправить."})

@bot.message_handler(commands=['start'])
def main(message: types.Message):

    if not BotDatabase.check_user(user_id=message.from_user.id):
        logging.info(f'добваляем пользователя с user_id: {message.from_user.id} в базу данных')
        BotDatabase.add_user(message.from_user.id, message.from_user.username)

        start_msg = bot.send_message(message.chat.id,
                                     f"Привет {message.from_user.username}, я твой личный бот фитнесс-тренер\nДавай составим для тебя план индивидуальных тренировок. "
                                     "Для этого ты можешь рассказать о себе и своем спортивном опыте в голосовом сообщении "
                                     "или написать текстом :)")

        bot.register_next_step_handler(start_msg, get_info)
    else:
        logging.info(f'пользователь с user_id: {message.from_user.id} уже существует')
        bot.send_message(message.from_user.id, "привет друг, ты зареган уже! го качаться, выбери один из пунктов меню")


def get_info(message: types.Message):
    if message.content_type == 'voice':

        logging.info('пользователь отправил голосовое сообщение, вызываем whisper и конвертируем в текст')
        bot.send_message(message.chat.id, "Супер, начинаем заполнять для тебя анкету!")

        file_info = bot.get_file(message.voice.file_id)
        df = bot.download_file(file_info.file_path)

        logging.info('получили голосовое сообщение, скармливаем его whisper')
        with open('test_filename.mp3', 'wb') as file:
            file.write(df)

        audio_file = open('test_filename.mp3', 'rb')
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        transcripted_text = str(transcript['text'])

        logging.info(f'Получили текст из гс {transcripted_text}, отправляем запрос в гпт')

        context_messages.append({"role": "user", "content": transcripted_text})

        form_completion = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages
        )

        logging.info(f'получили ответ гпт {form_completion}')
        context_messages.append({"role": "assistant", "content": form_completion.choices[0].message.content})

        check_message = bot.send_message(message.chat.id, form_completion.choices[0].message.content)
        bot.register_next_step_handler(check_message, check_form)

    elif message.content_type == 'text':

        logging.info('пользователь отправил текстовое сообщение')
        text_from_user = message.text
        bot.send_message(message.chat.id, "Супер, начинаем заполнять для тебя анкету!")

        context_messages.append({"role": "user", "content": str(text_from_user)})

        form_completion = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages
        )

        logging.info(f'получили ответ гпт {form_completion}')

        context_messages.append({"role": "assistant", "content": form_completion.choices[0].message.content})

        check_message = bot.send_message(message.chat.id, form_completion.choices[0].message.content)

        bot.register_next_step_handler(check_message, check_form)


def check_form(message: types.Message):
    logging.info(f'from check_form: {message.text}')
    user_answer = message.text

    context_messages.append({"role": "user", "content": str(user_answer)})
    logging.info(f"context: {context_messages}")

    get_form = openai.ChatCompletion.create(

        model=config.FT_MODEL_NAME,
        messages=context_messages
    )

    key_word = 'анкета'
    logging.info(get_form)

    if key_word in str(get_form.choices[0].message.content).lower(): # посмотреть ответ
        bot.send_message(message.chat.id, get_form.choices[0].message.content)
        bot.send_message(message.chat.id, "Все ли верно?", reply_markup=markup_keyboard_accept)
        logging.info(f'{message.text}')
    else:
        mess = bot.send_message(message.chat.id, get_form.choices[0].message.content)
        bot.register_next_step_handler(mess, check_form)


def create_program(message: types.Message):
    logging.info('создаем программу на основе анкеты пользователя!')
    pre_program = openai.ChatCompletion.create(
        model=config.FT_MODEL_NAME,
        messages=context_messages_program
    )

    check_msg = bot.send_message(message.chat.id, pre_program.choices[0].message.content)
    bot.register_next_step_handler(check_msg, check_program)


def check_program(message: types.Message):
    user_answer = message.text.lower()

    if user_answer == 'да':
        # достать голую программу и сохранить в бд
        pass
    else:
        context_messages_program.append({"role": "user", "content": user_answer})

        re_creating_program = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages_program
        )
        m2 = bot.send_message(message.chat.id, re_creating_program.choices[0].message.content)
        bot.register_next_step_handler(m2, check_program)


@bot.message_handler(commands=['start_sport'])
def start_sport(message: types.Message):
    pass


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
    bot.send_message(message.chat.id, "Привет, я бот, который составляет индивидуальные тренировки")


bot.infinity_polling()
