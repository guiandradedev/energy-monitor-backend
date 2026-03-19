from dotenv import load_dotenv
load_dotenv()

from infra.broker.mqtt import MQTTClient
MQTTClient().start()

# import os
# import uvicorn

# if __name__ == '__main__':
#     host = os.getenv('HOST', '0.0.0.0')
#     port = os.getenv('PORT') or os.getenv('APP_PORT') or 5000
#     try:
#         port = int(port)
#     except Exception:
#         port = 5000

#     debug = os.getenv('DEBUG', 'True').lower() in ('1', 'true', 'yes')

#     # Rodar o servidor FastAPI com Uvicorn
#     uvicorn.run('src.api.main:app', host=host, port=port, reload=debug)