import os
import logging
from dotenv import load_dotenv
import openai
import tiktoken

load_dotenv()

EMBEDDING_DIMENSION = 1536

# Secret Keys
COGNITIVE_SEARCH_CONFIG = {
    'api_key': os.environ['COGNITIVE_SEARCH_API_KEY'],
    'endpoint': os.environ['COGNITIVE_SEARCH_ENDPOINT'],
    'index_name': os.environ['COGNITIVE_SEARCH_INDEX_NAME']
}


AZURE_OPENAI_CONFIG = {
    'api_key': os.getenv('AZURE_OPENAI_API_KEY'),
    'api_base': os.getenv('AZURE_OPENAI_API_BASE'),
    'deployment_name': os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME'),
    'api_version': "2023-05-15"
}

ADA_CONFIG = {
    'api_key': os.environ['AZURE_OPENAI_API_KEY'],
    'api_base': os.environ['AZURE_OPENAI_API_BASE'],
    'api_version': os.environ['ADA_API_VERSION'],
    'model': os.environ['ADA_MODEL'],
    'deployment_name': os.environ['ADA_DEPLOYMENT_NAME']
}

BLOB_STORAGE_CONFIG = {
    'connection_string': os.getenv('AZURE_STORAGE_CONNECTION_STRING'),
    'container_name': os.getenv('CONTAINER_NAME')
}

openai.api_type = "azure"
openai.api_key = AZURE_OPENAI_CONFIG['api_key']
openai.api_base = AZURE_OPENAI_CONFIG['api_base']
openai.api_version = AZURE_OPENAI_CONFIG['api_version']

encoding = tiktoken.encoding_for_model("gpt-4o")

EMAIL_CONFIG = {
    'smtp_server': os.getenv('SMTP_SERVER'),
    'smtp_port': os.getenv('SMTP_PORT'),
    'smtp_username': os.getenv('SMTP_USERNAME'),
    'smtp_password': os.getenv('SMTP_PASSWORD'),
    'from_email': os.getenv('FROM_EMAIL'),
    'to_email': os.getenv('TO_EMAIL')
}


PORT = "8000"
HOST = "0.0.0.0"
CONCURRENCY_LIMIT = 50

# Logging Configuration
logger = logging.getLogger('PoC')
formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s', "%Y-%m-%d %H:%M:%S")

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)
app_logger = logger
