from datetime import datetime

from telegram.bot import Bot
from telegram.parsemode import ParseMode

from basic_mongo import BasicMongo as mongo
from secrets import TELEGRAM


def get_text():
    DAYS = ['Heute', 'Gestern']
    result = []
    db = mongo.get_db()
    for j in range(len(DAYS)):
        data = mongo.get_day_value(db, 'R8', j * -1, state={'$eq': '100.0'})
        data2 = mongo.get_day_value(db, 'R13', j * -1)
        r = []
        x = "Keine Bereitschaft." if not float(mongo.get_one(db, "R13")['state']) else "Bereitschaft seit *0:00* Uhr."
        if data2.count():
            for i, d in enumerate(data2):
                if not i and d['state'] == '100.0':
                    r.append("von *00:00* Uhr")
                time = d['timestamp'].strftime("%H:%M")
                r.append("bis *{}* Uhr".format(time) if d['state'] == '100.0' else "von *{}* Uhr".format(time))
                if i == data2.count() - 1 and d['state'] == '0.0':
                    r.append("bis *23:59* Uhr" if j else "bis *jetzt*")
            for i, d in enumerate(r):
                if i == len(r) - 3:
                    r[i] = r[i] + " und"
                    break
                if i % 2:
                    r[i] += ","
            x = "Bereitschaft {}.".format(" ".join(r))
        v = data.count()
        t = ""
        h = []
        if data.count():
            h.append("(")
            for d in data:
                h.append("_{}_ Uhr, ".format(d['timestamp'].strftime("%H:%M")))
            h[len(h) - 1] = h[len(h) - 1][:-2] + ")"
            if data.count() > 1:
                h[len(h) - 2] = h[len(h) - 2][:-2] + " und "
            t = "".join(h)
        result.append("*{}*\n{}\nHeizvorgänge: *{}*\n{}".format(DAYS[j], x, v, t))
    result = result[::-1]
    result.append("_Aktualisiert: {}_".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    return "*STATISTIK*\n\n" + "\n\n".join(result)


def send():
    Bot(TELEGRAM["token"]).edit_message_text(chat_id=TELEGRAM["chat_id"], message_id=TELEGRAM["msg_id2"],
                                             text=get_text(), parse_mode=ParseMode.MARKDOWN, timeout=60)


if __name__ == '__main__':
    send()
