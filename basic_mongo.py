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
        return client.alarm_system

    @staticmethod
    def update_name(db, old, new):
        print(db.sensors.update_one({"name": old}, {"$set": {"name": new}}))
        return True
