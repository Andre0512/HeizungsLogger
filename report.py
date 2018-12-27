from datetime import datetime, timedelta

from telegram.bot import Bot
from telegram.parsemode import ParseMode

from basic_mongo import BasicMongo as mongo
from secrets import TELEGRAM


def check_holes(data, full=None):
    if not full:
        full = {}
    for d in data:
        hour = d['timestamp'].hour
        if hour in full:
            full[hour] += 1
        else:
            full[hour] = 1
    return full


def get_heat_list(data):
    sharp = False
    heat_list = []
    for x in data:
        if float(x['state']) < 60 and not sharp:
            sharp = True
        elif float(x['state']) > 70 and sharp:
            heat_list.append(x['timestamp'])
            sharp = False
    return heat_list


def get_zones(data):
    result = {"22-06": 0, "06-12": 0, "12-17": 0, "17-22": 0}
    for d in data:
        if d.hour >= 22 or d.hour < 6:
            result["22-06"] += 1
        elif 6 <= d.hour < 12:
            result["06-12"] += 1
        elif 12 <= d.hour < 17:
            result["12-17"] += 1
        elif 17 <= d.hour < 22:
            result["17-22"] += 1
    text = "\n*{} Heizvorgänge*\n".format(len(data))
    for k, v in sorted(result.items()):
        text += "{} Uhr: {}\n".format(k, v)
    return text + "\n"


def get_solar(db, z, sensor, name):
    data = mongo.get_day_value(db, sensor, z * -1, twenty_two=True)
    start = False
    result = 0
    for d in sorted(data, key=lambda x: x['timestamp']):
        if float(d['state']) and not start:
            start = d['timestamp']
        if not float(d['state']) and start:
            result = (d['timestamp'] - start)
            start = False
    if result:
        return "{}: `{:02.0f}:{:02.0f}` Stunden\n".format(name, *list(divmod(result.seconds / 60, 60)))
    return "{} ist nicht gelaufen\n".format(name)


def get_min_max(db, z, sensor, name):
    data = mongo.get_day_value(db, sensor, z * -1, twenty_two=True)
    result = sorted(data, key=lambda x: float(x['state']))
    if not result:
        return ""
    text = "*{}*\n".format(name)
    text += "Min `{}°C` {} Uhr\n".format(result[0]['state'], result[0]['timestamp'].strftime('%H:%M'))
    text += "Max `{}°C` {} Uhr\n\n".format(result[-1]['state'], result[-1]['timestamp'].strftime('%H:%M'))
    return text


def get_text(z=1):
    result = "*Tagesbericht {}*\n\n".format((datetime.now() - timedelta(days=z)).strftime("%d.%m."))
    db = mongo.get_db()
    sensors = {"Kollektorfühler": "S1", "Außentemperatur": "S9", "Pufferspeicher": "S16"}
    for name, sensor in sensors.items():
        result += get_min_max(db, z, sensor, name)
    full = check_holes(mongo.get_day_value(db, "S1", z * -1, twenty_two=True))
    check_holes(mongo.get_day_value(db, "S9", z * -1, twenty_two=True), full)
    check_holes(mongo.get_day_value(db, "S14", z * -1, twenty_two=True), full)
    hole = 24 - len(full)
    s14 = mongo.get_day_value(db, "S14", z * -1, twenty_two=True)
    heat_list = get_heat_list(s14)
    solar = {"Pumpe 1": "R1", "Pumpe 2": "R4"}
    result += "*Solar*:\n"
    for k, v in solar.items():
        result += get_solar(db, z, v, k)
    result += get_zones(heat_list)
    if hole:
        result += "‼️ ACHTUNG ‼️\n{} {}".format(hole, "Stunden fehlen" if hole - 1 else "Stunde fehlt") if hole else ""
    return result


def send():
    Bot(TELEGRAM["token"]).send_message(chat_id=TELEGRAM["report_id"], message_id=TELEGRAM["msg_id2"],
                                        text=get_text(), parse_mode=ParseMode.MARKDOWN, timeout=60)


if __name__ == '__main__':
    send()