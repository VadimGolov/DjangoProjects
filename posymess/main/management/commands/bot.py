import os
import asyncio

from loguru import logger
from decimal import Decimal


from asgiref.sync import sync_to_async
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder

from django.core.management import BaseCommand
from django.core.wsgi import get_wsgi_application

from main.models import User, Flower, Order  # noqa PyUnresolvedReferences
from posymess.settings import BOT_TOKEN  # noqa PyUnresolvedReferences

from .support import clear_commands, orders_list, posy_list
from .keyboards import start_keyboard, main_keyboard

# Настройки Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "posymess.settings")
application = get_wsgi_application()

# Инициализация логирования
logger.add('debug.log', format='{time} {level} {message}', level='DEBUG', rotation='100 MB', compression='zip')


# Определим состояния для FSM
class States(StatesGroup):
    enter_email = State()


# Словарь для хранения активных пользователей
active_users = {}

# Экземпляр бота
mem_storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(bot=bot, storage=mem_storage)


# Приветствие и вызов главного меню
@dp.message(or_f(CommandStart(), F.text.func(lambda text: text == '🚀 Запуск')))
async def start_command(message: types.Message, state: FSMContext):
    await clear_commands(bot)
    await message.answer(text='Добро пожаловать в Posy message! Я бот для заказа букетов')
    await message.reply(text='Для продолжения работы с ботом введите адрес вашей электронной почты', reply_markup=start_keyboard)
    await state.set_state(States.enter_email)


@dp.message(States.enter_email)
async def enter_email(message: types.Message, state: FSMContext):
    email = message.text

    # Проверка наличия адреса эл. почты в базе данных
    try:
        user = await sync_to_async(User.objects.get)(email=email)
        active_users[message.from_user.id] = user
        await state.update_data(email=email)
        await state.clear()
        await message.answer(text='Вы успешно авторизованы!', reply_markup=main_keyboard)

    except User.DoesNotExist:
        await message.answer('Такая почта еще не зарегистрирована\n'
                             'Пожалуйста, зарегистрируйтесь на сайте, чтобы начать работу с ботом')
        await message.reply(text='Для продолжения работы с ботом введите адрес вашей электронной почты', reply_markup=start_keyboard)


# Кнопка помощи
@dp.message(F.text == '🤓 Помощь')
async def help_handler(message: types.Message):
    await message.answer(text='Я помогу вам с моими функциями\n'
                              '\nВы можете:\n'
                              '1. Аутентификация в боте (кнопка «🚀 Запуск»)\n'
                              '1. Создать новый заказ (кнопка «💐 Заказать букет»)\n'
                              '2. Посмотреть текущие заказы (кнопка «📦 Мои заказы»)\n'
                              '3. Отменить текущие заказы (кнопка «📦 Мои заказы»)')


# Кнопка мои заказы
@dp.message(F.text == '📦 Мои заказы')
async def show_orders(message: types.Message):
    current_user = active_users[message.from_user.id]

    if not current_user:
        return

    # Получаем заказы пользователя
    orders = await sync_to_async(Order.objects.filter)(user=current_user)

    if await sync_to_async(orders.exists)():

        simple_orders = await sync_to_async(orders_list)(orders)

        for order in simple_orders:
            # Кнопка для отмены заказа
            delete_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=f'❌ Отменить заказ', callback_data=f'delete:{order['id']}')]],
                    resize_keyboard=True)

            # Информация о заказе
            await message.answer(text=f'Заказ №{order['id']} '
                                      f'букет «{order['posy_name']}» '
                                      f'дата заказа: {order['order_date']} '
                                      f'цена {order['order_price']}, ',
                                 reply_markup=delete_keyboard)
    else:
        await message.answer('Заказов нет')


# Отмена заказа
@dp.callback_query(F.data.startswith('delete:'))
async def remove_order(callback: types.CallbackQuery):
    dead_id = callback.data.split(':')[1]
    order = await sync_to_async(Order.objects.get)(id=dead_id)
    await sync_to_async(order.delete)()
    await callback.message.edit_text(text=f'Заказ №{dead_id} отменён')
    await callback.answer(text='')


# Кнопка заказать букет
@dp.message(F.text == '💐 Заказать букет')
async def new_order(message: types.Message):
    current_user = active_users[message.from_user.id]

    if not current_user:
        return

    # Получаем список букетов
    posies = await sync_to_async(Flower.objects.all)()

    if await sync_to_async(posies.exists)():

        simple_flowers = await sync_to_async(posy_list)(posies)

        order_keyboard = InlineKeyboardBuilder()

        # Кнопка для выбора букета
        for posy in simple_flowers:
            callback_string: str = f'pick_one:{posy["price"]}:{posy["id"]}:{message.from_user.id}'
            order_keyboard.add(InlineKeyboardButton(text=f'«{posy["posy_name"]}» - {posy["price"]} ₽', callback_data=callback_string))

        order_keyboard = order_keyboard.adjust(1).as_markup()

        await message.answer(text='Выберите букет из списка:', reply_markup=order_keyboard)


# Создание заказа
@dp.callback_query(F.data.startswith('pick_one:'))
async def order_posy(callback: types.CallbackQuery):
    data = callback.data.split(':')

    # --------------------------------
    # data[0] = 'pick_one:'
    # Decimal(data[1]) = posy['price']
    # int(data[2]) = posy['id']
    # int(data[3]) = user_id
    # --------------------------------

    current_user = active_users[int(data[3])]
    posy = await sync_to_async(Flower.objects.get)(id=int(data[2]))
    price = Decimal(data[1])

    order = await sync_to_async(Order.objects.create)(user=current_user, flower=posy, order_price=price)  # noqa PyUnresolvedReferences

    await callback.message.edit_text(f'Заказ на {posy.posy_name} создан')
    await callback.answer()


class Command(BaseCommand):
    """
    Класс создает команду для запуска бота

    """

    @classmethod
    async def run_bot(cls) -> None:
        await clear_commands(bot)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    @classmethod
    async def escape_bot(cls) -> None:
        await bot.session.close()

    def handle(self, *args, **kwargs) -> None:
        try:
            logger.info('Бот запущен')
            asyncio.run(self.run_bot())

        except KeyboardInterrupt:
            logger.info('Бот остановлен')

        finally:
            asyncio.run(self.escape_bot())