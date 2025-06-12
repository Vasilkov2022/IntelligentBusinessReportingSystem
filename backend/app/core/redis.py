import os
import redis as redis_lib

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# decode_responses=True → получаем str вместо bytes
redis = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)