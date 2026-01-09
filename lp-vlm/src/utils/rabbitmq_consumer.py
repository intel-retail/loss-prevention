import pika
import json
import queue
import time
from datetime import datetime
from .vlm import call_vlm
from .rabbitmq_client import get_rabbitmq_connection
import threading
from concurrent.futures import ThreadPoolExecutor
from .config import logger
            
class ODConsumer:
    def __init__(self,message_queue,user_name, password):
        self.message_queue = message_queue 
        self.user_name = user_name
        self.password = password

    # RabbitMQ consumer running in background
    def rabbitmq_consumer(self):
        connection = get_rabbitmq_connection(self.user_name, self.password)
        channel = connection.channel()
        channel.queue_declare(queue="object_detection", durable=True)

        def callback(ch, method, properties, body):
            payload = json.loads(body)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"OD Consumer - Received object_detection message at {timestamp}: {payload}")
            self.message_queue.put(json.dumps(payload),block=False)


        channel.basic_consume(queue="object_detection", on_message_callback=callback, auto_ack=True)
        channel.start_consuming()
        
    def start_consumer(self):
        threading.Thread(target=self.rabbitmq_consumer, daemon=True).start()
        
        
