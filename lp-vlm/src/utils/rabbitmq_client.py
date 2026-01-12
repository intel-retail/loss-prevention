import pika
import time
import os
import socket
from utils.config import logger


def get_rabbitmq_connection(user_name: str, password: str):
    logger.info("Creating RabbitMQ connection...")
    retry = 0
    MAX_RETRIES = 20
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))
    logger.info(f"RabbitMQ target → host={host} port={port}")
    while retry < MAX_RETRIES:
        logger.info(f"Attempt {retry + 1}/{MAX_RETRIES} connecting to RabbitMQ...")
        try:
            credentials = pika.PlainCredentials(user_name, password)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=host,
                    port=port,
                    credentials=credentials,
                    heartbeat=300,
                    blocked_connection_timeout=300
                )
            )
            logger.info("RabbitMQ connection established.")
            return connection
        except (pika.exceptions.AMQPConnectionError, socket.gaierror) as e:
            retry += 1
            logger.info(f"Waiting for RabbitMQ... ({e})")
            time.sleep(1)
    raise pika.exceptions.AMQPConnectionError(f"Could not connect after {MAX_RETRIES} retries (host={host} port={port})")