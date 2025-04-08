"""Storage microservice that persists events from Kafka into a MySQL database."""

import os
import json
import time
import logging.config
from datetime import datetime
from threading import Thread

import yaml
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from pykafka import KafkaClient
from pykafka.common import OffsetType
from connexion import NoContent
import connexion

from models import SessionLocal, OrderEvent, RatingEvent, init_db

# Use UTC timestamps in logs
logging.Formatter.converter = time.gmtime

# Load logging config
with open('./config/log_conf.yml', "r", encoding="utf-8") as config_file:
    LOG_CONFIG = yaml.safe_load(config_file.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger("basicLogger")

# Load app configuration
with open('./config/app_conf.yml', "r", encoding="utf-8") as config_file:
    app_config = yaml.safe_load(config_file.read())

KAFKA_HOST = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
KAFKA_TOPIC = app_config['events']['topic']

# Initialize DB schema
init_db()


def report_product_order_event(body):
    """Store order event in database."""
    session = SessionLocal()
    try:
        recorded_at_dt = datetime.fromisoformat(body["order_timestamp"].replace("Z", ""))
        event = OrderEvent(
            trace_id=body["trace_id"],
            user_id=body["user_id"],
            user_country=body["user_country"],
            order_timestamp=recorded_at_dt,
            price=body["price"]
        )
        session.add(event)
        session.commit()
        logger.debug("Stored order event with trace_id %s", body["trace_id"])
    finally:
        session.close()
    return NoContent, 201


def report_product_rating_event(body):
    """Store rating event in database."""
    session = SessionLocal()
    try:
        recorded_at_dt = datetime.fromisoformat(body["timestamp"].replace("Z", ""))
        event = RatingEvent(
            trace_id=body["trace_id"],
            device_id=body["device_id"],
            product_type=body["product_type"],
            timestamp=recorded_at_dt,
            rating=body["rating"]
        )
        session.add(event)
        session.commit()
        logger.debug("Stored rating event with trace_id %s", body["trace_id"])
    finally:
        session.close()
    return NoContent, 201


def process_messages():
    """Consume Kafka messages and persist them."""
    client = KafkaClient(hosts=KAFKA_HOST)
    topic = client.topics[str.encode(KAFKA_TOPIC)]

    consumer = topic.get_simple_consumer(
        consumer_group=b'event_group',
        reset_offset_on_start=False,
        auto_offset_reset=OffsetType.LATEST
    )

    for msg in consumer:
        msg_str = msg.value.decode('utf-8')
        msg = json.loads(msg_str)
        logger.info("Received message: %s", msg)
        payload = msg["payload"]

        if msg["type"] == "order_event":
            report_product_order_event(payload)
        elif msg["type"] == "rating_event":
            report_product_rating_event(payload)

        consumer.commit_offsets()


def get_order_events(start_timestamp, end_timestamp):
    """Return all order events within a time range."""
    session = SessionLocal()
    try:
        start = datetime.fromisoformat(start_timestamp.replace("Z", ""))
        end = datetime.fromisoformat(end_timestamp.replace("Z", ""))
        statement = (
            select(OrderEvent)
            .where(OrderEvent.date_created >= start)
            .where(OrderEvent.date_created < end)
        )
        results = session.execute(statement).scalars().all()
        events = [result.to_dict() for result in results]
        logger.info("Found %d order events", len(events))
        return events, 200
    finally:
        session.close()


def get_rating_events(start_timestamp, end_timestamp):
    """Return all rating events within a time range."""
    session = SessionLocal()
    try:
        start = datetime.fromisoformat(start_timestamp.replace("Z", ""))
        end = datetime.fromisoformat(end_timestamp.replace("Z", ""))
        statement = (
            select(RatingEvent)
            .where(RatingEvent.date_created >= start)
            .where(RatingEvent.date_created < end)
        )
        results = session.execute(statement).scalars().all()
        events = [result.to_dict() for result in results]
        logger.info("Found %d rating events", len(events))
        return events, 200
    finally:
        session.close()


def get_event_counts():
    """Return total count of order and rating events."""
    session = SessionLocal()
    try:
        order_count = session.query(OrderEvent).count()
        rating_count = session.query(RatingEvent).count()
        return {"order": order_count, "rating": rating_count}, 200
    except SQLAlchemyError as db_err:
        logger.error("Error getting event counts: %s", str(db_err))
        return {"message": "Internal server error"}, 500
    finally:
        session.close()


def get_order_ids():
    """Return all order event IDs with trace_ids."""
    session = SessionLocal()
    try:
        results = session.query(OrderEvent.user_id, OrderEvent.trace_id).all()
        events = [{"event_id": r[0], "trace_id": r[1]} for r in results]
        return events, 200
    except SQLAlchemyError as db_err:
        logger.error("Error getting order IDs: %s", str(db_err))
        return {"message": "Internal server error"}, 500
    finally:
        session.close()


def get_rating_ids():
    """Return all rating event IDs with trace_ids."""
    session = SessionLocal()
    try:
        results = session.query(RatingEvent.device_id, RatingEvent.trace_id).all()
        events = [{"event_id": r[0], "trace_id": r[1]} for r in results]
        return events, 200
    except SQLAlchemyError as db_err:
        logger.error("Error getting rating IDs: %s", str(db_err))
        return {"message": "Internal server error"}, 500
    finally:
        session.close()


def setup_kafka_thread():
    """Starts Kafka consumer in a daemon thread."""
    t1 = Thread(target=process_messages)
    t1.setDaemon(True)
    t1.start()


# Create and run Connexion app
app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api("sephora.yaml", base_path="/storage", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    setup_kafka_thread()
    app.run(port=8090, host="0.0.0.0")
