import telebot
import gtts
import sqlite3
import logging

from gtts import gTTS
from telebot import types

import config
from database import BotDatabase

bot = telebot.TeleBot(token=config.TG_BOT_TOKEN)
bot_database = BotDatabase(config.DATABASE_NAME)
logging.basicConfig(filename='logs.log', encoding='utf-8', level=logging.DEBUG)


@bot.message_handler(commands=['start'])
def main(message: types.Message):
    """
    greeting and asking first questions

    :param message:
    :return:
    """

    if bot_database.check_user(message.from_user.id):
        logging.info(f'добваляем пользователя с user_id: {message.from_user.id} в базу данных')
        bot_database.add_user(message.from_user.id, message.from_user.username)

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
        bot.send_message(message.from_user.id, "привет друг, ты зареган уже! го качаться")


def get_info(message: types.Message):
    """
    check if user send to us a voice message -> speech to text | convert to text
    chek if user send to us a text message -> starting completing the form
    :param message:
    :return:
    """
    logging.info('переходим к заполнению формы')
    voice = False

    if voice:
        logging.info('пользователь отправил голосовое сообщение, вызываем whisper и конвертируем в текст')
        """
        => convert to text and call the function which will fill the form
        => save program to database
        => register next step
        """
        text = ''
        fill_form(text)
        bot_database.insert(text)
        pass
    else:
        logging.info('пользователь отправил текстовое сообщение')
        """
        => call the function which will fill the form 
        => check if the form filled 
        => save program to database
        => register next step
        """
        text = ''
        form = fill_form(text)
        bot.send_message(message.from_user.id, f'Проверь форму {form}, выбери один из ответов на клаве')
        ok = ''

        if ok == 'да':
            # add to database and save, then register next step
            bot_database.insert(text)
            pass
        else:
            # call openai again (attempts are limited) => edit and ask again
            text = ''
            fill_form(text)


def fill_form(raw_data: str) -> str:
    """
    here we use gpt

    :param raw_data:
    :return:
    """
    logging.info('вызываем гпт')

    pass


if __name__ == '__main__':
    bot.infinity_polling()
