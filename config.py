from dotenv import load_dotenv
import os

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN           = os.getenv("BOT_TOKEN")
DATABASE_URL        = os.getenv("DATABASE_URL")
ADMIN_ID        = int(os.getenv("ADMIN_ID"))
FUZY_THRESHOLD      = int(os.getenv("FUZY_THRESHOLD", 80))