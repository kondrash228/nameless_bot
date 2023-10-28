from telebot import types

markup_keyboard_accept = types.ReplyKeyboardMarkup(resize_keyboard=True)
yes_btn = types.KeyboardButton('Да')
markup_keyboard_accept.add(yes_btn)

markup_keyboard_accept_call = types.InlineKeyboardMarkup()
item_yes = types.InlineKeyboardButton('да', callback_data='yes')
item_no = types.InlineKeyboardButton('нет', callback_data='no')
markup_keyboard_accept_call.add(item_yes, item_no)