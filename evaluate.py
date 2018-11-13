import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from basic_mongo import BasicMongo as mongo


def get_sensor(db, sensor):
    data = mongo.get_sensor(db, sensor)
    x = []
    y = []
    for d in data:
        x.append(d['timestamp'])
        y.append(float(d['state']))
    return [x, y]


db = mongo.get_db()
x1, y1 = get_sensor(db, 'R13')
x2, y2 = get_sensor(db, 'S16')
x3, y3 = get_sensor(db, 'S5')
x4, y4 = get_sensor(db, 'S6')
x5, y5 = get_sensor(db, 'S2')

plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
plt.gca().xaxis.set_major_locator(mdates.HourLocator())
t = np.arange(min(y1), max(y1) + 1, (max(y1) - min(y1)) / 10)
plt.yticks(t)
plt.plot(x1, y1)
#plt.plot(x2, y2)
#plt.plot(x3, y3)
#plt.plot(x4, y4)
#plt.plot(x5, y5)
plt.gcf().autofmt_xdate()
plt.savefig('testplot.png', dpi=500)
