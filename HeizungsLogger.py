#!/usr/bin/env python
import json
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

from basic_mongo import BasicMongo as mongo
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
Zirkulation: `{S8}`°C
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


def save_data(data):
    if len(sys.argv) > 1 and sys.argv[1] == "log":
        db = mongo.get_db()
        with open('data.json') as data_file:
            old_data = json.load(data_file)
        for k, v in old_data.items():
            if not data[k] == old_data[k]:
                mongo.insert(db, {"state": v, "timestamp": datetime.now(), "name": k})
        with open('data.json', 'w') as outfile:
            json.dump(data, outfile, indent=4)


def useful(sensors):
    result = {}
    s = 0
    p = 0
    for x in sensors:
        if x['name'][:11] == "Temperature" and s < 16:
            s += 1
            if float(x['rawValue']) < 800:
                result['S' + str(s)] = format(x['rawValue'], "0.1f")
        elif x['name'][:10] == "Pump speed" and p < 14:
            p += 1
            result['R' + str(p)] = format(x['rawValue'], "0.1f")
    return result


def pretty(sensors):
    sensors['R1'] = sensors['R1'] + "%" if float(sensors['R1']) > 0 and float(sensors["R3"]) == 0 else "❌"
    sensors['R4'] = sensors['R1'] + "%" if not sensors['R1'] == "❌" and float(sensors['R4']) > 0 else "❌"
    sensors['R13'] = "✔️" if float(sensors['R13']) > 0 else "❌"
    sensors['R8'] = "✔️" if float(sensors['R8']) > 0 else "❌"
    sensors['R3'] = "✔️" if float(sensors['R3']) > 0 else "❌"
    sensors['R5'] = "✔️" if float(sensors['R5']) > 0 else "❌"
    sensors['R9'] = "✔️" if float(sensors['R9']) > 0 else "❌"
    if float(sensors['R6']) > 0:
        sensors['R6'] = "✔️"
    elif float(sensors['R7']) > 0:
        sensors['R6'] = "️❌"
    else:
        sensors['R6'] = "🤷‍♂️"
    return sensors


def ugly(sensors):
    result = ""
    for sensor in sensors:
        if sensor['name'][:11] == "Temperature":
            value = format(sensor['rawValue'], "0.1f") + "°C"
            result += "{}: `{}`\n".format(sensor['name'], value)
            continue
        result += "{}: `{}`\n".format(sensor['name'], sensor['rawValue'])
    return result


def get_sensors():
    response = r.get(URL.format(VBUS_SERVER["IP"], VBUS_SERVER["PORT"]))
    return response.json()


def parse_message():
    sensors = pretty(useful(get_sensors()))
    save_data(sensors)
    t = TEXT.format(**sensors).replace(".", ",")
    text = [t, "_Aktualisiert: {}_".format(datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S"))]
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
    except Exception as e:
        logger.error(e)
