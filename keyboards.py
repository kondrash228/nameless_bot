from telebot import types

markup_keyboard_accept = types.ReplyKeyboardMarkup(resize_keyboard=True)
yes_btn = types.KeyboardButton('Да')
markup_keyboard_accept.add(yes_btn)

markup_keyboard_exercises = types.ReplyKeyboardMarkup(resize_keyboard=True)
ready_btn = types.KeyboardButton("Я выполнил упражнение")
markup_keyboard_exercises.add(ready_btn)

markup_keyboard_chill = types.ReplyKeyboardMarkup(resize_keyboard=True)
skip = types.KeyboardButton("Пропустить отдых")
markup_keyboard_chill.add(skip)