import connexion
from datetime import datetime
from connexion import NoContent
import logging.config
import yaml
import os
from models import SessionLocal, OrderEvent, RatingEvent, init_db  # Import models
from sqlalchemy import select
import time
from pykafka import KafkaClient
from pykafka.common import OffsetType

from threading import Thread
import json


logging.Formatter.converter = time.gmtime


# Load logging configuration
with open('./config/log_conf.yml', "r") as f:
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger("basicLogger")  # Get the configured logger

with open('./config/app_conf.yml', "r") as f:
    app_config = yaml.safe_load(f.read())

# Extract Kafka connection details
KAFKA_HOST = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
  
KAFKA_TOPIC = app_config['events']['topic']

# Initialize database tables
init_db()

def report_product_order_event(body):
    """Stores order event in the database."""
    session = SessionLocal()
    try:
        # Convert `recorded_at` to a datetime object
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
        logger.debug(f"Stored order event with trace_id {body['trace_id']}")
    finally:
        session.close()
    return NoContent, 201

def report_product_rating_event(body):
    """Stores rating event in the database."""
    session = SessionLocal()
    try:
        # Convert `recorded_at` to a datetime object
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
        logger.debug(f"Stored rating event with trace_id {body['trace_id']}")
    finally:
        session.close()
    return NoContent, 201

def process_messages():
    """ Process event messages """
    hostname = KAFKA_HOST # localhost:9092
    client = KafkaClient(hosts=hostname)
    topic = client.topics[str.encode(KAFKA_TOPIC)]
    # Create a consume on a consumer group, that only reads new messages
    # (uncommitted messages) when the service re-starts (i.e., it doesn't
    # read all the old messages from the history in the message queue).
    consumer = topic.get_simple_consumer(consumer_group=b'event_group',
    reset_offset_on_start=False,
    auto_offset_reset=OffsetType.LATEST)
    # This is blocking - it will wait for a new message
    for msg in consumer:
        msg_str = msg.value.decode('utf-8')
        msg = json.loads(msg_str)
        logger.info("Message: %s" % msg)
        payload = msg["payload"]
        if msg["type"] == "order_event": # Change this to your event type
            # Store the event1 (i.e., the payload) to the DB
            report_product_order_event(payload)
        elif msg["type"] == "rating_event": # Change this to your event type
            # Store the event2 (i.e., the payload) to the DB
            report_product_rating_event(payload)
        # Commit the new message as being read
        consumer.commit_offsets()



def get_order_events(start_timestamp, end_timestamp):
    """Retrieves order events between the given timestamps."""
    session = SessionLocal()
    try:
        # Convert ISO timestamps to datetime objects
        start = datetime.fromisoformat(start_timestamp.replace("Z", ""))
        end = datetime.fromisoformat(end_timestamp.replace("Z", ""))

        # Dynamic SQLAlchemy ORM Query
        statement = (
            select(OrderEvent)
            .where(OrderEvent.date_created >= start)
            .where(OrderEvent.date_created < end)
        )

        # Execute the ORM query
        results = session.execute(statement).scalars().all()

        # Convert ORM objects to dictionaries for JSON response
        events = [result.to_dict() for result in results]
        
        logger.info(f"Found {len(events)} order events (start: {start}, end: {end})")
        return events, 200
    finally:
        session.close()

def get_rating_events(start_timestamp, end_timestamp):
    """Retrieves rating events between the given timestamps."""
    session = SessionLocal()
    try:
        # Convert ISO timestamps to datetime objects
        start = datetime.fromisoformat(start_timestamp.replace("Z", ""))
        end = datetime.fromisoformat(end_timestamp.replace("Z", ""))

        # Dynamic SQLAlchemy ORM Query
        statement = (
            select(RatingEvent)
            .where(RatingEvent.date_created >= start)
            .where(RatingEvent.date_created < end)
        )

        # Execute the ORM query
        results = session.execute(statement).scalars().all()

        # Convert ORM objects to dictionaries for JSON response
        events = [result.to_dict() for result in results]
        
        logger.info(f"Found {len(events)} rating events (start: {start}, end: {end})")
        return events, 200
    finally:
        session.close()

def get_event_counts():
    """Return count of order and rating events in the database."""
    session = SessionLocal()
    try:
        order_count = session.query(OrderEvent).count()
        rating_count = session.query(RatingEvent).count()
        return {"order": order_count, "rating": rating_count}, 200
    except Exception as e:
        logger.error("Error getting event counts: %s", str(e))
        return {"message": "Internal server error"}, 500
    finally:
        session.close()


def get_order_ids():
    """Return all order event IDs and trace IDs."""
    session = SessionLocal()
    try:
        results = session.query(OrderEvent.user_id, OrderEvent.trace_id).all()
        events = [{"event_id": r[0], "trace_id": r[1]} for r in results]
        return events, 200
    except Exception as e:
        logger.error("Error getting order IDs: %s", str(e))
        return {"message": "Internal server error"}, 500
    finally:
        session.close()


def get_rating_ids():
    """Return all rating event IDs and trace IDs."""
    session = SessionLocal()
    try:
        results = session.query(RatingEvent.device_id, RatingEvent.trace_id).all()
        events = [{"event_id": r[0], "trace_id": r[1]} for r in results]
        return events, 200
    except Exception as e:
        logger.error("Error getting rating IDs: %s", str(e))
        return {"message": "Internal server error"}, 500
    finally:
        session.close()


def setup_kafka_thread():
    """Set up a thread to consume Kafka messages continuously."""
    t1 = Thread(target=process_messages)
    t1.setDaemon(True)
    t1.start()

# Create the application instance
app = connexion.FlaskApp(__name__, specification_dir='')

app.add_api("sephora.yaml", base_path="/storage", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    setup_kafka_thread()
    app.run(port=8090, host="0.0.0.0")
