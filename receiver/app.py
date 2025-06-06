"""Receiver microservice that accepts events and pushes them to Kafka."""

import uuid
import datetime
import logging.config
import time
import json

import connexion
import yaml
from pykafka import KafkaClient
from connexion import NoContent

logging.Formatter.converter = time.gmtime

#test in progress

# Load logging configuration
with open("./config/log_conf.yml", "r", encoding="utf-8") as f:
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger("basicLogger")

# Load configuration from YAML file
with open("./config/app_conf.yml", "r", encoding="utf-8") as f:
    app_config = yaml.safe_load(f.read())

KAFKA_HOST = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
TOPIC_NAME = app_config['events']['topic']

# Connect to Kafka
client = KafkaClient(hosts=KAFKA_HOST)
topic = client.topics[str.encode(TOPIC_NAME)]
producer = topic.get_sync_producer()

ORDERS_URL = app_config["events"]["orders"]["url"]
RATING_URL = app_config["events"]["rating"]["url"]


def add_trace_id(body):
    """Ensures event payload has a trace_id."""
    if body is None:
        body = {}
    if "trace_id" not in body or body["trace_id"] is None:
        body["trace_id"] = str(uuid.uuid4())
    return body


def send_to_kafka(event_type, body):
    """Sends event to Kafka topic instead of HTTP."""
    body = add_trace_id(body)
    message = {
        "type": event_type,
        "datetime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "payload": body
    }

    msg_str = json.dumps(message)
    producer.produce(msg_str.encode('utf-8'))

    logger.info("Produced %s to Kafka with trace_id: %s", event_type, body["trace_id"])
    return NoContent, 201


def report_product_order_event(body):
    """Sends order event to Kafka topic."""
    return send_to_kafka("order_event", body)


def report_product_rating_event(body):
    """Sends rating event to Kafka topic."""
    return send_to_kafka("rating_event", body)


app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api("sephora.yaml", base_path="/receiver", strict_validation=True)

if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
