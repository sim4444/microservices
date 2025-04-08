import os
import time
import json
import logging.config
from datetime import datetime

import yaml
import connexion
from flask import jsonify
from pykafka import KafkaClient
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

# Configure logging to use UTC timestamps
logging.Formatter.converter = time.gmtime

# Kafka constants
KAFKA_TIMEOUT_MS = 1000  # Kafka consumer timeout

# Load logging configuration
with open("./config/log_conf.yml", "r", encoding="utf-8") as log_file:
    log_config = yaml.safe_load(log_file.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger("basicLogger")

# Load app configuration
with open("./config/app_conf.yml", "r", encoding="utf-8") as conf_file:
    app_config = yaml.safe_load(conf_file.read())

KAFKA_HOST = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
TOPIC_NAME = app_config['events']['topic']

# Connect to Kafka
client = KafkaClient(hosts=KAFKA_HOST)
topic = client.topics[str.encode(TOPIC_NAME)]

logger.info("Analyzer service has started. Logging test message!")


def get_event(index, event_type):
    """Retrieve a specific event from Kafka by index."""
    logger.info("Fetching %s at index %d", event_type, index)
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True,
        consumer_timeout_ms=KAFKA_TIMEOUT_MS
    )

    counter = 0
    for msg in consumer:
        if msg is None:
            break
        message = msg.value.decode("utf-8")
        data = json.loads(message)
        if data.get("type") == event_type:
            if counter == index:
                logger.info("Found event %s at index %d", event_type, index)
                return data, 200
            counter += 1

    logger.warning("No %s found at index %d", event_type, index)
    return {"message": f"No {event_type} at index {index}"}, 404


def get_order_events(index):
    """Fetch order event by index."""
    return get_event(index, "order_event")


def get_rating_events(index):
    """Fetch rating event by index."""
    return get_event(index, "rating_event")


def get_event_stats():
    """Compute statistics on Kafka messages."""
    logger.info("Computing event statistics from Kafka")
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True,
        consumer_timeout_ms=KAFKA_TIMEOUT_MS
    )

    stats = {
        "num_order_events": 0,
        "num_rating_events": 0
    }

    for msg in consumer:
        if msg is None:
            break
        message = msg.value.decode("utf-8")
        data = json.loads(message)
        if data["type"] == "order_event":
            stats["num_order_events"] += 1
        elif data["type"] == "rating_event":
            stats["num_rating_events"] += 1

    logger.info("Stats: %s", stats)
    return jsonify(stats), 200


def get_all_order_ids():
    """Get all order id and trace_id from Kafka."""
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True,
        consumer_timeout_ms=KAFKA_TIMEOUT_MS
    )

    results = []
    for msg in consumer:
        if msg is None:
            break
        try:
            data = json.loads(msg.value.decode("utf-8"))
            if data.get("type") == "order_event":
                payload = data["payload"]
                results.append({
                    "event_id": payload.get("user_id"),
                    "trace_id": payload.get("trace_id")
                })
        except Exception as error:
            logger.warning("Skipping message: %s", str(error))
            continue

    return results, 200


def get_all_rating_ids():
    """Get all rating id and trace_id from Kafka."""
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True,
        consumer_timeout_ms=KAFKA_TIMEOUT_MS
    )

    results = []
    for msg in consumer:
        if msg is None:
            break
        try:
            data = json.loads(msg.value.decode("utf-8"))
            if data.get("type") == "rating_event":
                payload = data["payload"]
                results.append({
                    "event_id": payload.get("device_id"),
                    "trace_id": payload.get("trace_id")
                })
        except Exception as error:
            logger.warning("Skipping message: %s", str(error))
            continue

    return results, 200


# Create Flask app with Connexion
app = connexion.FlaskApp(__name__, specification_dir="")
app.add_api("analyzer.yml", base_path="/analyzer", strict_validation=True, validate_responses=True)

# Enable CORS if flagged
if os.environ.get("CORS_ALLOW_ALL") == "yes":
    app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if __name__ == "__main__":
    app.run(port=8200, host="0.0.0.0")
