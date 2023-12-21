import os
from telegrambot import TelegramApp

if __name__ == '__main__':
    app = TelegramApp(os.getenv('BOT_TOKEN'))
    app.start_app()
