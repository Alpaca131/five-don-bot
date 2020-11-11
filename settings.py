import os
from dotenv import load_dotenv

load_dotenv(verbose=True)

dotenv_path = 'home/alpaca-data/env/.env'
load_dotenv(dotenv_path)

TOKEN = os.environ['TOKEN']
