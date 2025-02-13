from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


# Начальная клавиатура бота
start_keyboard = ReplyKeyboardMarkup(keyboard=[[
                KeyboardButton(text='🚀 Запуск'),]],
                resize_keyboard=True)


# Главная клавиатура бота
main_keyboard = ReplyKeyboardMarkup(keyboard=[[
                 KeyboardButton(text='🚀 Запуск'),
                 KeyboardButton(text='🤓 Помощь'),
                 KeyboardButton(text='💐 Заказать букет'),
                 KeyboardButton(text='📦 Мои заказы'), ]],
                 resize_keyboard=True)