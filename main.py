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

context_messages = {}
context_messages_program = {}

tokens = {}


@bot.message_handler(commands=['start'])
def main(message: types.Message):
    if not BotDatabase.check_user(user_id=message.from_user.id):
        logging.info(f'добваляем пользователя с user_id: {message.from_user.id} в базу данных')
        BotDatabase.add_user(message.from_user.id, message.from_user.username)

        start_msg = bot.send_message(message.chat.id,
                                     f"Привет {message.from_user.username}, я твой личный бот фитнесс-тренер\nДавай составим для тебя план индивидуальных тренировок. "
                                     "Для этого ты можешь рассказать о себе и своем спортивном опыте в голосовом сообщении "
                                     "или написать текстом :)")

        if not message.from_user.id in context_messages.keys():
            context_messages[message.from_user.id] = []
            context_messages_program[message.from_user.id] = []
            tokens[message.from_user.id] = {"prompt_1": 0, "prompt_2": 0}

        context_messages[message.from_user.id].append({"role": "system",
                                                       "content": "Твоя задача сделать анкету по данным предоставлеными пользователем. Формат анкеты следующий:имя,пол,возраст,уровень физической подготовки (от 1 до 10),длительность занятия, дни недели для занятий, точное время начала тренировки (24 часовой формат), физические ограничения,наличие спортивного инвентаря,пожелания по упражнениям. Не задавай вопрос про пол (гендер) пользователя,определи пол по имени. Общайся с пользователем на «ты». Задавай уточняющие вопросы до тех пор пока анкету не заполнишь полностью. Задавай вопросы строго по анкете. Обязательно спроси у пользователя возраст. Задавай по два вопроса за раз. Пиши кратко, не повторяй слова пользователя, не давай лишних комментариев. Начни сообщение с анкетой со слов 'Твоя анкета' .По завершению анкеты, спроси, все ли верно с ней и спроси нужно ли что-то исправить. Не выдавай анкету до тех пор пока она полностью не будет заполнена."})
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
        with open(f'{message.from_user.id}.mp3', 'wb') as file:
            file.write(df)

        audio_file = open(f'{message.from_user.id}.mp3', 'rb')
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        transcripted_text = str(transcript['text'])

        logging.info(f'Получили текст из гс {transcripted_text}, отправляем запрос в гпт')

        # context_messages.append({"role": "user", "content": transcripted_text})
        context_messages[message.from_user.id].append({"role": "user", "content": transcripted_text})

        form_completion = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages[message.from_user.id],
            temperature=0.1
        )

        logging.info(f'получили ответ гпт {form_completion.choices[0].message.content}')

        tokens[message.from_user.id]['prompt_1'] += int(form_completion.usage.total_tokens)
        logging.info(f'считаем токены для пользователя: {message.from_user.id}, итого prompt_1 = {tokens[message.from_user.id]["prompt_1"]}')

        # context_messages.append({"role": "assistant", "content": form_completion.choices[0].message.content})
        context_messages[message.from_user.id].append({"role": "assistant", "content": form_completion.choices[0].message.content})

        check_message = bot.send_message(message.chat.id, form_completion.choices[0].message.content)
        bot.register_next_step_handler(check_message, check_form)

    elif message.content_type == 'text':

        logging.info('пользователь отправил текстовое сообщение')
        text_from_user = message.text
        bot.send_message(message.chat.id, "Супер, начинаем заполнять для тебя анкету!")

        # context_messages.append({"role": "user", "content": str(text_from_user)})
        context_messages[message.from_user.id].append({"role": "user", "content": str(text_from_user)})

        form_completion = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages[message.from_user.id],
            temperature=0.1
        )

        logging.info(f'Получили ответ gpt {form_completion.choices[0].message.content}')
        tokens[message.from_user.id]['prompt_1'] += int(form_completion.usage.total_tokens)

        logging.info( f'считаем токены для пользователя: {message.from_user.id}, итого prompt_1 = {tokens[message.from_user.id]["prompt_1"]}')

        # context_messages.append({"role": "assistant", "content": form_completion.choices[0].message.content})
        context_messages[message.from_user.id].append({"role": "assistant", "content": form_completion.choices[0].message.content})

        check_message = bot.send_message(message.chat.id, form_completion.choices[0].message.content)

        bot.register_next_step_handler(check_message, check_form)


def check_form(message: types.Message):
    logging.info(f'from check_form: {message.text}')
    user_answer = message.text

    # context_messages.append({"role": "user", "content": str(user_answer)})
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

    if key_word in str(get_form.choices[0].message.content).lower():  # посмотреть ответ
        s2 = bot.send_message(message.chat.id, get_form.choices[0].message.content, reply_markup=markup_keyboard_accept)
        bot.register_next_step_handler(s2, final_check_form)
    else:
        mess = bot.send_message(message.chat.id, get_form.choices[0].message.content)
        bot.register_next_step_handler(mess, check_form)


def final_check_form(message: types.Message):
    ok = message.text

    if ok == 'Да':
        bot.send_message(message.chat.id,
                                 "Отлично! Начинаю подготовку твоей индивидуаьлной программы тренировок!",
                                 reply_markup=markup_keyboard_accept)
        context_messages[message.from_user.id].append(
            {"role": "assistant", "content": "Выдай полученную форму, без лишнего текста, ничего не пиши кроме анкеты"})

        get_ready_form = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages[message.from_user.id],
            temperature=0.1
        )

        tokens[message.from_user.id]["prompt_1"] += int(get_ready_form.usage.total_tokens)
        logging.info(f'текущие токены пользователя: {message.from_user.id} prompt_1={tokens[message.from_user.id]["prompt_1"]}')

        logging.info(f'Получили готовую анкету: {get_ready_form.choices[0].message.content}')

        context_messages_program[message.from_user.id].append({"role": "system","content": "Ты - тренер по фитнесу, который составляет индивидуальную программу спортивных занятий дома. Не здоровайся с пользователем. У тебя есть список упражнений и анкета которую ты получаешь от пользователя. Сделай логичную программу с учётом анкеты пользователя, используй только упражнения которые даны в списке упражнений. Рядом с каждым упражнением подпиши: количество подходов, количество повторений/времени в позиции. Подстраивай количество подходов и повторений в зависимости от уровня физической подготовки пользователя, возраста и пола. Общайся с пользователем на «ты». Помни, тренировка начинается с разминки, далее основная часть (силовая), а в конце заминка. Предлагай не более 4-5 упражнений на каждый этап тренировки. Ты должен иметь в виду все данные предоставленные в анкете. Сделай предупреждение «с осторожностью из-за {физическое ограничение}, если упражнение затрагивает физическое ограничение. После создания программы спроси у пользователя подходит ли ему программа и что можно изменить. Если пользователя что-то не устраивает,сразу выдавай измененную программу. Не задавай лишних вопросов."})
        context_messages_program[message.from_user.id].append({"role": "user", "content": get_ready_form.choices[0].message.content})
        context_messages_program[message.from_user.id].append({"role": "user","content": 'Список упражнений: "Велосипед" (#1), "Кошачья" растяжка (#2), "Ножницы" (#3), "Боковые скручивания" (#4), "Берпи" (#5), "Касания стоп" (#6), "Комплексная растяжка дельт" (#7), "Косые скручивания" (#8), "Круговые движения коленями" (#9), "Круговые движения локтями" (#10), "Круговые движения плечами" (#11), "Круговые движения руками" (#12), "Махи назад" (#13), "Махи ногой" (#14), "Отведение ноги в сторону" (#15), "Отжимания" (#16), "Отжимания на одной руке" (#17), "Отжимания от скамьи из-за спины" (#18), "Отжимания с узким упором" (#19), "Отжимания с широким упором" (#20), "Планка" (#21), "Подтягивание коленей" (#22), "Подъем ног" (#23), "Подъем плеч" (#24), "Подъем согнутых в коленях ног" (#25), "Подъем туловища из положения лежа" (#26), "Подъем ягодиц" (#27), "Приседания" (#28), "Прыжки ноги вместе, ноги врозь" (#29), "Прыжки с выпадами" (#30), "Прыжки с приседаниями" (#31), "Растягивание икроножных мышц" (#32), "Растягивание мышц брюшного пресса" (#33), "Растягивание мышц шеи в стороны" (#34), "Растягивание широчайших мышц спины" (#35), "Растяжение мышц задней поверхности бедра" (#36), "Растяжка в положении сидя" (#37), "Растяжка грудных мышц отведением плеч" (#38), "Растяжка икроножных мышц в положении стоя" (#39), "Растяжка лежа на полу" (#40), "Растяжка мышц в положении сидя" (#41), "Растяжка мышц задней поверхности бедра сидя на полу" (#42), "Растяжка мышц спины" (#43), "Растяжка с выпадом" (#44), "Растяжка с приседанием" (#45), "Растяжка "супермен"" (#46), "Растяжка широчайших мышц спины сидя" (#47), "Растяжка ягодичных мышц" (#48), "Скручивания" (#49), "Статическое упражнение для мышц груди" (#50), "Тройная растяжка" (#51), "Тяга головы к груди" (#52), "Вертикальная тяга гантелей" (#53), "Выпады с гантелями" (#54), "Жим гантелей лежа на полу" (#55), "Жим гантелей стоя" (#56), "Заход на скамью с гантелями" (#57), "Комплексный жим гантелей" (#58), "Концентрированные сгибания на бицепс сидя" (#59), "Разведение гантелей в стороны лежа лицом вниз" (#60), "Сведение гантелей лежа" (#61), "Тяга гантели к груди" (#62), "Шраги с гантелями" (#63), "Подтягивания" (#64), "Подтягивания в стороны" (#65), "Подтягивания на одной руке" (#66), "Подтягивания обратным хватом" (#67), "Подтягивания смешанным хватом" (#68), "Подтягивания широким хватом" (#69), "Подтягивания широким хватом за голову" (#70), "Подъем ног к перекладине" (#71), "Подъем ног в висе на перекладине" (#72).'})
        context_messages[message.from_user.id].clear()

        logging.info('создаем программу на основе анкеты пользователя!')

        pre_program = openai.ChatCompletion.create(
            model=config.FT_MODEL_NAME,
            messages=context_messages_program[message.from_user.id],
            temperature=0.1
        )

        tokens[message.from_user.id]["prompt_2"] += int(pre_program.usage.total_tokens)
        logging.info(f'текущие токены пользователя: {message.from_user.id} prompt_2={tokens[message.from_user.id]["prompt_2"]}')

        check = bot.send_message(message.chat.id, pre_program.choices[0].message.content, reply_markup=markup_keyboard_accept)
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
        bot.send_message(message.chat.id, "Хорошо, сохраняем твою программу!")
        logging.info(f'Сохраняем программу для пользователя {message.from_user.id}')

        context_messages_program[message.from_user.id].append({"role": "assistant", "content": "Выдай созданную программу без лишнего текста"})

        get_program = openai.ChatCompletion.create(
            model=config.MODEL_NAME,
            messages=context_messages_program[message.from_user.id],
            temperature=0.1
        )
        logging.info(f'Полученная программа с помощью gpt 3.5 {get_program.choices[0].message.content}')
        BotDatabase.insert(message.from_user.id, get_program.choices[0].message.content)
        bot.send_message(message.from_user.id, "Твоя программа успешно сохранена! Далее ты можешь выбрать одну из команд")
        logging.info('Успешно сохранили программу в бд')

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
