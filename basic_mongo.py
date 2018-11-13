from datetime import datetime, timedelta

from pymongo.mongo_client import MongoClient

from secrets import MONGO


class BasicMongo:
    @staticmethod
    def get_last(db):
        return db.logs.aggregate(
            [
                {'$sort': {'mac': 1, 'timestamp': 1}},
                {
                    '$group':
                        {
                            '_id': '$mac',
                            'last': {'$last': '$$ROOT'}
                        }
                }
            ]
        )

    @staticmethod
    def get_names(db):
        result = db.sensors.find({})
        return {r['_id']: r['name'] for r in result}

    @staticmethod
    def get_db():
        client = MongoClient(MONGO['HOST'], MONGO['PORT'])
        return client.heiz_system

    @staticmethod
    def update_name(db, old, new):
        print(db.sensors.update_one({"name": old}, {"$set": {"name": new}}))
        return True

    @staticmethod
    def insert(db, data):
        db.sensors.insert_one(data)
        return True

    @staticmethod
    def get_day_value(db, sensor, day, state=None):
        if not state:
            state = {"$exists": True}
        today = (datetime.now() + timedelta(days=day)).replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        return db.sensors.find(
            {"name": sensor, "state": state, "timestamp": {"$gte": today, "$lt": tomorrow}})

    @staticmethod
    def get_one(db, sensor):
        return db.sensors.find_one({"name": sensor})
