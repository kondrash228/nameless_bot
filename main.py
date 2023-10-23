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

messages_f = []


@bot.message_handler(commands=['start'])
def main(message: types.Message):
    """
    greeting and asking first questions

    :param message:
    :return:
    """

    if not BotDatabase.check_user(user_id=message.from_user.id):
        logging.info(f'добваляем пользователя с user_id: {message.from_user.id} в базу данных')
        BotDatabase.add_user(message.from_user.id, message.from_user.username)

        start_msg = bot.send_message(message.chat.id,
                                     f"Привет {message.from_user.username}, я твой личный бот фитнесс-тренер\nДавай составим для тебя план индивидуальных тренировок. "
                                     "Для этого ты можешь рассказать о себе и своем спортивном опыте в голосовом сообщении "
                                     "или написать текстом :)")
        """
        просим пользователя надиктовать или написать о себе и далее делаем запрос к openai 
        """
        bot.register_next_step_handler(start_msg, get_info)
    else:
        logging.info(f'пользователь с user_id: {message.from_user.id} уже существует')
        bot.send_message(message.from_user.id, "привет друг, ты зареган уже! го качаться, выбери один из пунктов меню")


def get_info(message: types.Message):
    """
    check if user send to us a voice message -> speech to text | convert to text done
    chek if user send to us a text message -> starting completing the form done
    :param message:
    :return:
    """

    if message.content_type == 'voice':
        """
        => convert to text and call the function which will fill the form
        => save program to database
        => register next step
        """

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

        messages_f.append({"role": "system",
                           "content": "составь анекту по введеным данным и запроси подробную информацию если тебе ее не хватает для составления анекты.анекта имеет вид: имя, пол, возраст, длительность заняти, дни занятий, физические ограничения, пожелания по упражнениям"})
        messages_f.append({"role": "user", "content": transcripted_text})

        form_completion = openai.ChatCompletion.create(  # req to fill the form
            model=config.MODEL_NAME,
            messages=messages_f
        )

        logging.info(f'получили ответ гпт {form_completion}')
        bot.send_message(message.chat.id, form_completion.choices[0].message.content)

        markup_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=False)
        yes_btn = types.KeyboardButton('да')
        no_btn = types.KeyboardButton('нет')
        markup_keyboard.add(yes_btn, no_btn)

        check_message = bot.send_message(message.chat.id, "проверь форму и напиши, если хочешь что то поменять",
                                         reply_markup=markup_keyboard)
        bot.register_next_step_handler(check_message, check_form)

    elif message.content_type == 'text':
        """
        => call the function which will fill the form
        => check if the form filled
        => save program to database
        => register next step
        """

        logging.info('пользователь отправил текстовое сообщение')
        text_from_user = message.text
        bot.send_message(message.chat.id, "Супер, начинаем заполнять для тебя анкету!")

        messages_f.append({"role": "system",
                           "content": "составь анекту по введеным данным и запроси подробную информацию если тебе ее не хватает для составления анекты.анекта имеет вид: имя, пол, возраст, длительность заняти, дни занятий, физические ограничения, пожелания по упражнениям"})
        messages_f.append({"role": "user", "content": text_from_user})

        form_completion = openai.ChatCompletion.create(  # req to fill the form
            model=config.MODEL_NAME,
            messages=messages_f
        )

        logging.info(f'получили ответ гпт {form_completion}')
        bot.send_message(message.chat.id, form_completion.choices[0].message.content)

        markup_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=False)
        yes_btn = types.KeyboardButton('да')
        no_btn = types.KeyboardButton('нет')
        markup_keyboard.add(yes_btn, no_btn)

        check_message = bot.send_message(message.chat.id, "проверь форму и напиши, если хочешь что то поменять",
                                         reply_markup=markup_keyboard)
        bot.register_next_step_handler(check_message, check_form)


def check_form(message: types.Message):
    logging.info(f'from check_form: {message.text}')
    if message.text == 'да':
        # todo prompt 2
        pass
    else:
        edit = bot.send_message(message.chat.id, "Напиши что тебе не понравилось")
        bot.register_next_step_handler(edit, edit_form)


def edit_form(message: types.Message):
    logging.info('редактируем анкету пользователя')
    ok = False

    if ok:
        logging.info('ура')
    else:
        to_change = message.text
        messages_f.append({"role": "system", "content": "измени предыдущую форму в соответсвии с текстом"})
        messages_f.append({"role": "user", "content": to_change})

        edited_form = openai.ChatCompletion.create(  # req to fill the form
            model=config.MODEL_NAME,
            messages=messages_f
        )

        bot.send_message(message.chat.id, edited_form.choices[0].message.content)


def fill_form(raw_data: str) -> str:
    """
    here we use gpt

    :param raw_data:
    :return:
    """
    logging.info('вызываем гпт')
    pass


@bot.message_handler(commands=['start_sport'])
def start_sport():
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
def about():
    pass


bot.infinity_polling()
