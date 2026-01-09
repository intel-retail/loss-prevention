import pika
import json
import os
from datetime import datetime
from config import LP_IP
import sys

rabbit_user = os.environ.get("RABBITMQ_USER")
rabbit_pass = os.environ.get("RABBITMQ_PASSWORD")
rabbit_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
rabbit_port = int(os.environ.get("RABBITMQ_PORT", "5672"))
rabbit_queue = os.environ.get("RABBITMQ_QUEUE", "object_detection")

try:
    credentials = pika.PlainCredentials(rabbit_user, rabbit_pass)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=rabbit_host, port=rabbit_port, credentials=credentials)
    )
    channel = connection.channel()

    end_message = {
        "msg_type": "STREAM_END",
        "status": "COMPLETED",
        "timestamp": datetime.now().isoformat(),
        "data": {}
    }
    channel.basic_publish(
        exchange="",
        routing_key=rabbit_queue,
        body=json.dumps(end_message)
    )

    print("📢 End message sent successfully!")
    connection.close()

except Exception as e:
    print(f"❌ Failed to send end message: {e}")
    sys.exit(1)