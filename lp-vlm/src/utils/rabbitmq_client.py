import pika
import time
def get_rabbitmq_connection(user_name: str, password: str):
    retry = 0
    MAX_RETRIES = 5
    while retry < MAX_RETRIES:
        try:
            credentials = pika.PlainCredentials(user_name, password)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host="localhost",  port=5672,credentials=credentials,heartbeat=300,
            blocked_connection_timeout=300)
            )
            return connection
        except pika.exceptions.AMQPConnectionError:
            retry += 1
            print("Waiting for RabbitMQ...")
            time.sleep(1)
    raise pika.exceptions.AMQPConnectionError("Could not connect after 5 retries")