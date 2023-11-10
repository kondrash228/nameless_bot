from telebot import types

markup_keyboard_accept = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
yes_btn = types.KeyboardButton('Да')
markup_keyboard_accept.add(yes_btn)

markup_keyboard_exercises = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
ready_btn = types.KeyboardButton("Я выполнил упражнение")
markup_keyboard_exercises.add(ready_btn)

markup_keyboard_chill = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
skip = types.KeyboardButton("Пропустить отдых")
markup_keyboard_chill.add(skip)

markup_keyboard_change_schedule = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
change = types.KeyboardButton("Изменить расписание")
markup_keyboard_change_schedule.add(change)

markup_keyboard_set_schedule = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
set = types.KeyboardButton("Настроить новое расписание")
markup_keyboard_set_schedule.add(set)

markup_keyboard_set_program = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
prog = types.KeyboardButton("Настроить новую программу")
markup_keyboard_set_program.add(prog)