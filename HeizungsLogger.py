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
*LIVEDATEN*

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
                mongo.insert(db, {"state": data[k], "timestamp": datetime.now(), "name": k})
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
    bcmd = "ssh pi@{} \"{{}}\" {{}}".format(VBUS_SERVER["IP"])
    try:
        response = r.get(URL.format(VBUS_SERVER["IP"], VBUS_SERVER["PORT"]))
        if response.json():
            return [response.json(), False]
        else:
            if not int(datetime.now().strftime("%M")) % 10:
                os.system(bcmd.format("pkill node", ""))
                logger.warning("killed node")
            return ["Daten können nicht gelesen werden. USB Gerät kurz trennen und erneut versuchen", True]
    except r.exceptions.ConnectionError:
        cmd = bcmd.format("cd /home/pi/resol-vbus/ && /home/pi/n/bin/node examples/json-live-data-server/index.js", "&")
        if not os.system("ping -c 2 " + VBUS_SERVER["IP"]):
            if os.system(bcmd.format("ls /dev/tty* | grep -q USB", "")):
                if not os.system(bcmd.format("ls /dev/tty* | grep -q ACM0", "")):
                    os.system("sudo rmmod -f cdc_acm ; sudo rmmod -f ftdi_sio ; sudo rmmod -f usbserial ; sudo modprobe"
                              + "usbserial vendor=0x1fef product=0x2018 ; sudo modprobe ftdi_sio ; pkill node")
                    logger.warning("executed USB reconfiguration")
                    return ["USB Gerät rekonfiguriert... es geht gleich weiter...", True]
                return ["USB Gerät wird nicht erkannt. Bitte (neu) anschließen"]
            if os.system(bcmd.format("pgrep -f json-live-data-server", "")):
                os.system(cmd.format(VBUS_SERVER["IP"]))
                logger.warning("started - json-live-data-server")
                return ["Auslesen wurde gestartet. Es geht gleich weiter (vielleicht)", True]
            logger.warning("json-live-data-server runs but not callable")
            return ["Auslesen gestartet, aber noch nicht verfügbar. Noch etwas Geduld...️️", True]
        logger.warning(VBUS_SERVER["IP"] + " - not reachable")
        return ["Raspberry Pi nicht erreichbar. Verbindung prüfen.", True]


def parse_message():
    text = []
    sensors, error = get_sensors()
    if error:
        last = datetime.strftime(datetime.fromtimestamp(
            os.path.getmtime("{}/{}".format(os.path.dirname(os.path.realpath(__file__)), 'data.json'))),
                                 "%Y-%m-%d %H:%M:%S")
        text.append("‼️‼️{}‼️‼\n‼️Daten sind auf dem Stand von *{}*‼️️".format(sensors, last))
        with open("{}/{}".format(os.path.dirname(os.path.realpath(__file__)), 'data.json')) as data_file:
            sensors = json.load(data_file)
    else:
        sensors = useful(sensors)
    save_data(sensors)
    timestamp = datetime.now()
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
