from urllib.parse import unquote
import re
from datetime import timedelta, datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, ContextTypes
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler
from telegram.ext import filters
from prediction import PredictionModel
from steamapi import SteamParser


class TimeDeltaFormats:
    DAY = 'day'
    MONTH = 'month'
    YEAR = 'year'
    ALL_TIME = 'all_time'


CHOOSING_TIMEDELTA, ENTERING_DATE = range(2)
CHOOSING_TIMEDELTA_VALES = {
    TimeDeltaFormats.DAY: 'День',
    TimeDeltaFormats.MONTH: 'Месяц',
    TimeDeltaFormats.YEAR: 'Год',
    TimeDeltaFormats.ALL_TIME: 'Всё время',
    'exit': 'Выход'
}

CHOOSING_TIMEDELTA_RANGES = {
    TimeDeltaFormats.DAY: timedelta(days=1),
    TimeDeltaFormats.MONTH: timedelta(days=30),
    TimeDeltaFormats.YEAR: timedelta(days=365),
    TimeDeltaFormats.ALL_TIME: timedelta(days=365 * 99)
}


class TelegramApp:
    token: str
    steam_community_link = r"https:\/\/steamcommunity\.com\/market\/listings\/730\/.*"

    def __init__(self, token):
        self.token = token
        self.delete_markup_messages = {}
        self.delete_messages = {}
        self.links = {}
        self.models = {}

    class MessagesTemplates:
        START = "Здравствуйте, {}!\n" \
                "Отправьте ссылку на товар торговой площадки, а мы покажем тенденции роста или падения."
        WRONG_LINK = "Неправильная ссылка. Проверьте её правильность.\nПример ссылки: " \
                     "https://steamcommunity.com/market/listings/730/Operation%20Breakout%20Weapon%20Case"
        TIMEOUT = "Запрашивать анализ предмета можно не чаще, чем раз в минуту"
        CHOOSE_TIMEDELTA = "Выберите интересуемый временной отрезок"
        WRONG_TIMEDELTA = "Выбран неправильный временной отрезок"

    CHOOSING_TIMEDELTA_KEYBOARD = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=v, callback_data=k)] for k, v in CHOOSING_TIMEDELTA_VALES.items()
        ]
    )
    CHOOSING_TIMEDELTA_KEYBOARD_PREDICT = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=v, callback_data=k)] for k, v in CHOOSING_TIMEDELTA_VALES.items()
        ] + [[InlineKeyboardButton(text="Предсказать", callback_data="predict")]]
    )

    async def start(self, upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await ctx.bot.send_message(
            upd.effective_chat.id,
            self.MessagesTemplates.START.format(upd.effective_user.name)
        )

    async def link(self, upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
        link = upd.effective_message.text
        match = re.match(self.steam_community_link, link)
        if match is None:
            await ctx.bot.send_message(upd.effective_chat.id, self.MessagesTemplates.WRONG_LINK)
            return
        msg = await ctx.bot.send_message(upd.effective_chat.id, self.MessagesTemplates.CHOOSE_TIMEDELTA,
                                         reply_markup=self.CHOOSING_TIMEDELTA_KEYBOARD)
        self.delete_markup_messages[upd.effective_user.id] = msg.id
        self.links[upd.effective_user.id] = link.split('/')[-1]
        return CHOOSING_TIMEDELTA

    async def starting_model(self, upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if upd.callback_query.data == 'predict':
            await ctx.bot.edit_message_reply_markup(upd.effective_chat.id,
                                                    self.delete_markup_messages[upd.effective_user.id],
                                                    reply_markup=InlineKeyboardMarkup([[]]))
            msg = await ctx.bot.send_message(chat_id=upd.effective_chat.id, text="Введите дату в формате ISO-8601")
            self.delete_messages[upd.effective_user.id] = msg.id
            return ENTERING_DATE
        elif upd.callback_query.data == 'exit':
            await ctx.bot.edit_message_reply_markup(
                upd.effective_chat.id,
                self.delete_markup_messages[upd.effective_user.id],
                reply_markup=InlineKeyboardMarkup([[]])
            )
            return ConversationHandler.END
        elif upd.callback_query.data not in CHOOSING_TIMEDELTA_VALES.keys():
            await ctx.bot.send_message(upd.effective_chat.id, self.MessagesTemplates.WRONG_TIMEDELTA)
            return CHOOSING_TIMEDELTA
        if self.models.get(upd.effective_user.id) is not None:
            await ctx.bot.delete_message(message_id=self.delete_markup_messages[upd.effective_user.id],
                                         chat_id=upd.effective_chat.id)
            msg = await ctx.bot.send_message(
                text=f"Выбранный отрезок: {CHOOSING_TIMEDELTA_VALES[upd.callback_query.data]}\n"
                     f"Начинаем анализ, ожидайте",
                chat_id=upd.effective_chat.id)
        else:
            msg = await ctx.bot.edit_message_text(
                text=f"Выбранный отрезок: {CHOOSING_TIMEDELTA_VALES[upd.callback_query.data]}\n"
                     f"Начинаем анализ, ожидайте",
                chat_id=upd.effective_chat.id,
                message_id=self.delete_markup_messages[upd.effective_user.id]
            )
        self.delete_markup_messages[upd.effective_user.id] = msg.id
        dt_from = datetime.now(tz=timezone.utc) - CHOOSING_TIMEDELTA_RANGES[upd.callback_query.data]
        history, labels = SteamParser.get_item(self.links[upd.effective_user.id], dt_from=dt_from)
        pm = PredictionModel(history, labels, labels[0], unquote(self.links[upd.effective_user.id]))
        pm.transform_data()
        pm.train()
        file_path = pm.draw_graph(labels)
        self.models[upd.effective_user.id] = pm
        await ctx.bot.delete_message(upd.effective_user.id, self.delete_markup_messages[upd.effective_user.id])
        msg = await ctx.bot.send_photo(
            photo=open(file_path, 'rb'),
            caption=f"Выбранный отрезок: {CHOOSING_TIMEDELTA_VALES[upd.callback_query.data]}",
            chat_id=upd.effective_chat.id,
            reply_markup=self.CHOOSING_TIMEDELTA_KEYBOARD_PREDICT,
        )
        self.delete_markup_messages[upd.effective_user.id] = msg.id
        return CHOOSING_TIMEDELTA

    async def predict(self, upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            dt = datetime.fromisoformat(upd.effective_message.text)
            dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            await ctx.bot.send_message(chat_id=upd.effective_chat.id,
                                       text="Отправьте правильную дату в формате ISO-8601")
            return ENTERING_DATE
        else:
            pm: PredictionModel = self.models[upd.effective_user.id]
            price = pm.predict(dt)
            await ctx.bot.send_message(chat_id=upd.effective_chat.id,
                                       text="Предполагаемая цена товара, основываясь на выбранном временном промежутке"
                                            f", на {dt.strftime('%d.%m.%Y %H:%M')} - {price[0][0]}$")
            await ctx.bot.delete_message(chat_id=upd.effective_chat.id,
                                         message_id=self.delete_messages[upd.effective_user.id])
            await ctx.bot.delete_message(chat_id=upd.effective_chat.id,
                                         message_id=upd.effective_message.message_id)
            await ctx.bot.edit_message_reply_markup(
                chat_id=upd.effective_chat.id,
                message_id=self.delete_markup_messages[upd.effective_user.id],
                reply_markup=self.CHOOSING_TIMEDELTA_KEYBOARD_PREDICT
            )
            return CHOOSING_TIMEDELTA

    def start_app(self) -> None:
        """Factory method needed to initialize application"""
        app = ApplicationBuilder().token(self.token).build()
        start_handler = CommandHandler('start', self.start)
        app.add_handler(start_handler)
        app.add_handler(
            ConversationHandler(
                entry_points=[MessageHandler(filters=filters.TEXT, callback=self.link)],
                states={
                    CHOOSING_TIMEDELTA: [CallbackQueryHandler(callback=self.starting_model)],
                    ENTERING_DATE: [MessageHandler(filters=filters.TEXT, callback=self.predict)]
                },
                fallbacks=[start_handler]
            )
        )
        app.run_polling()
