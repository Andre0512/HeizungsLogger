#!/usr/bin/env python

import logging
import os
import sys
from datetime import datetime
from pprint import pprint

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
TEXT = """
*Solar*
Außentemperatur: `{S9}`°C
Kollektorfühler: `{S1}`°C
Primärer Speicher: `{S2}`°C
Pumpe Speicher 1: `{R1}`
Sekundärer Speicher: `{S3}`°C
Pumpe Speicher 2: `{R4}`

*Ölheizung*
Temperatur: `{S14}`°C
Aktiv: `{R13}`
Pumpe: `{R8}`

*Warmwasser*
Boiler: `{S16}`°C
Nachheizung: `{S6}`°C
Pumpe: `{R3}`

*Heizung*
Temperatur: `{S10}`°C
Nachheizung: `{S5}`°C
Pumpe: `{R5}`
Mischventil: `{R6}`

*Holzofen*
Temperatur: `{S7}`°C
Pumpe: `{R9}`
"""


def get_sensors():
    response = r.get(URL.format(VBUS_SERVER["IP"], VBUS_SERVER["PORT"]))
    result = {}
    s = 0
    p = 0
    for x in response.json():
        if x['name'][:11] == "Temperature":
            s += 1
            result['S' + str(s)] = format(x['rawValue'], "0.1f")
        if x['name'][:10] == "Pump speed":
            p += 1
            result['R' + str(p)] = format(x['rawValue'], "0.1f")
    result['R1'] = result['R1'] + "%" if float(result['R1']) > 0 and float(result["R3"]) == 0 else "❌"
    result['R4'] = result['R1'] + "%" if not result['R1'] == "❌" and float(result['R4']) > 0 else "❌"
    result['R13'] = "✔️" if float(result['R13']) > 0 else "❌"
    result['R8'] = "✔️" if float(result['R8']) > 0 else "❌"
    result['R3'] = "✔️" if float(result['R3']) > 0 else "❌"
    result['R5'] = "✔️" if float(result['R5']) > 0 else "❌"
    result['R9'] = "✔️" if float(result['R9']) > 0 else "❌"
    if float(result['R6']) > 0:
        result['R6'] = "✔️"
    elif float(result['R7']) > 0:
        result['R6'] = "️❌"
    else:
        result['R6'] = "❔"
    pprint(result)
    return result


def parse_message():
    text = [TEXT.format(**get_sensors())]
    text.append("_Aktualisiert: {}_".format(datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")))
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
    send()
    try:
        pass
        # if len(sys.argv) > 1 and sys.argv[1] == "1":
        #    send()
        # else:
        #    main()
    except Exception as e:
        logger.error(e)
