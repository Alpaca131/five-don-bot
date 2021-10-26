import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ['TOKEN']
SENTRY_DSN = os.environ['SENTRY_DSN']
HEARTBEAT_TOKEN = os.environ["HEARTBEAT_TOKEN"]
