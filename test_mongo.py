import certifi
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb+srv://sudharsan1429_db_user:12xc2MRGRvqZFCuA@arivorahdb.biyxz3a.mongodb.net/?appName=ArivoraHDB"

print("Connecting to MongoDB Atlas...")
client = MongoClient(
    uri,
    server_api=ServerApi('1'),
    serverSelectionTimeoutMS=15000,
    tlsCAFile=certifi.where(),
    tlsAllowInvalidCertificates=True,
)

try:
    client.admin.command('ping')
    print("[OK] Connected to MongoDB Atlas successfully!")
    db = client["arivora"]
    cols = db.list_collection_names()
    print(f"[OK] DB 'arivora' collections: {cols if cols else '(none yet)'}")
except Exception as e:
    print(f"[FAIL] {e}")
finally:
    client.close()
    print("Done.")
