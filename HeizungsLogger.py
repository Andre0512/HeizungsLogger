#!/usr/bin/env python

import logging
import os
import sys
from datetime import datetime

import requests as r
from telegram.bot import Bot
from telegram.ext.callbackqueryhandler import CallbackQueryHandler
from telegram.ext.updater import Updater
from telegram.inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram.inline.inlinekeyboardmarkup import InlineKeyboardMarkup
from telegram.parsemode import ParseMode

from secrets import TELEGRAM, DEBUG, VBUS_SERVER

if DEBUG:
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(levelname)s - %(message)s')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                        filename="{}/{}".format(os.path.dirname(os.path.realpath(__file__)), 'log/state_channel.log'))
logger = logging.getLogger(__name__)

URL = "http://{}:{}/api/v1/live-data"


def get_sensors():
    response = r.get(URL.format(VBUS_SERVER["IP"], VBUS_SERVER["PORT"]))
    return response.json()


def get_value(v):
    if v['name'][:11] == "Temperature":
        value = format(v['rawValue'], "0.1f") + "°C"
        return "{}: `{}`".format(v['name'], value)
    return "{}: `{}`".format(v['name'], v['rawValue'])


def parse_message():
    text = [get_value(v) for v in get_sensors()]
    text.append("\n_Aktualisiert: {}_".format(datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")))
    return "\n".join(text)


def get_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Aktualisieren", callback_data="refresh")]])


def send(bot=None):
    if not bot:
        bot = Bot(TELEGRAM["token"])
    bot.edit_message_text(chat_id=TELEGRAM["chat_id"], message_id=TELEGRAM["msg_id"], text=parse_message(),
                          parse_mode=ParseMode.MARKDOWN, timeout=60)  # , reply_markup=get_keyboard())


def answer_callback(bot, update):
    if update.callback_query.data == "refresh":
        send(bot)
        logger.info(
            "Update - {} - {}".format(update.callback_query.from_user.first_name, update.callback_query.from_user.id))
    update.callback_query.answer()


def main():
    updater = Updater(TELEGRAM["token"])
    dp = updater.dispatcher

    dp.add_handler(CallbackQueryHandler(answer_callback))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    try:
        send()
        # if len(sys.argv) > 1 and sys.argv[1] == "1":
        #    send()
        # else:
        #    main()
    except Exception as e:
        logger.error(e)
