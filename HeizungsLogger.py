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
Kesseltemperatur: `{S14}`°C
Bereitschaft: `{R13}`
Pumpe: `{R8}`

*Warmwasser*
Pufferspeicher: `{S16}`°C
Wassertemperatur: `{S8}`°C
Nachlaufendes Wasser: `{S6}`°C
Pumpe: `{R3}`

*Heizung*
Temperatur: `{S10}`°C
Nachlaufendes Wasser: `{S5}`°C
Pumpe: `{R5}`
Mischventil: {R6}

*Holzofen - Wert vmtl Falsch*
Temperatur: `{S7}`°C
Pumpe: `{R9}`
"""


def save_data(data):
    if len(sys.argv) > 1 and sys.argv[-1] == "log":
        save = False
        db = mongo.get_db()
        with open("{}/{}".format(os.path.dirname(os.path.realpath(__file__)), 'data.json')) as data_file:
            old_data = json.load(data_file)
        for k, v in old_data.items():
            if not data[k] == old_data[k]:
                logger.debug("changed = {} - {}".format(k, data[k]))
                mongo.insert(db, {"state": v, "timestamp": datetime.now(), "name": k})
                save = True
        if save:
            logger.debug("saved - " + str(data))
            with open("{}/{}".format(os.path.dirname(os.path.realpath(__file__)), 'data.json'), 'w') as outfile:
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
    sensors['R1'] = sensors['R1'] + "%" if float(sensors['R1']) > 0 and float(sensors["R4"]) == 0 else "❌"
    sensors['R4'] = sensors['R1'] + "%" if not sensors['R1'] == "❌" and float(sensors['R4']) > 0 else "❌"
    sensors['R13'] = "✔️" if float(sensors['R13']) > 0 else "❌"
    sensors['R8'] = "✔️" if float(sensors['R8']) > 0 else "❌"
    sensors['R3'] = "✔️" if float(sensors['R3']) > 0 else "❌"
    sensors['R5'] = "✔️" if float(sensors['R5']) > 0 else "❌"
    sensors['R9'] = "✔️" if float(sensors['R9']) > 0 else "❌"
    if float(sensors['R6']) > 0:
        sensors['R6'] = "_Warmwasserzufluss an_"
    elif float(sensors['R7']) > 0:
        sensors['R6'] = "_️Warmwasserzufluss aus_"
    else:
        sensors['R6'] = "_Teilweise Warmwasserzufluss_"
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
    try:
        response = r.get(URL.format(VBUS_SERVER["IP"], VBUS_SERVER["PORT"]))
        return [response.json(), False]
    except r.exceptions.ConnectionError:
        cmd = "ssh pi@{} \"cd /home/pi/resol-vbus/ && /home/pi/n/bin/node examples/json-live-data-server/index.js\" &"
        if os.system("ping -c 2 " + VBUS_SERVER["IP"]) == 0:
            if not os.system("ssh pi@{} pgrep -f json-live-data-server".format(VBUS_SERVER["IP"])) == 0:
                os.system(cmd.format(VBUS_SERVER["IP"]))
                logger.warn("started - json-live-data-server")
                return ["‼️Server gleich wieder erreichbar‼\n‼Daten evtl. nicht aktuell‼️", True]
            logger.warn("json-live-data-server runs but not callable")
            return ["‼️‼️Server läuft, aber antwortet nicht‼️‼\n‼Daten evtl. nicht aktuell‼️️", True]
        logger.warn(VBUS_SERVER["IP"] + " - not reachable")
        return ["‼️‼️‼️Raspberry Pi nicht erreichbar‼️‼️‼️\n‼Daten nicht evtl. aktuell‼️", True]


def parse_message():
    text = []
    sensors, error = get_sensors()
    if error:
        timestamp = datetime.fromtimestamp(os.path.getmtime("{}/{}".format(os.path.dirname(os.path.realpath(__file__)), 'data.json')))
        text.append(sensors)
        with open("{}/{}".format(os.path.dirname(os.path.realpath(__file__)), 'data.json')) as data_file:
            sensors = json.load(data_file)
    else:
        timestamp = datetime.now()
        sensors = useful(sensors)
    save_data(sensors)
    text.append(TEXT.format(**pretty(sensors)).replace(".", ","))
    text.append("_Aktualisiert: {}_".format(datetime.strftime(timestamp, "%Y-%m-%d %H:%M:%S")))
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
