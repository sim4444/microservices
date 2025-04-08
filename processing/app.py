"""Processing microservice that aggregates and updates statistics periodically."""

import os
import time
import json
import yaml
import requests
import logging.config
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import connexion
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

# Set logging to use UTC time
logging.Formatter.converter = time.gmtime

# Load logging configuration
with open('./config/log_conf.yml', 'r', encoding='utf-8') as f:
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger("basicLogger")

# Load app configuration
with open('./config/app_conf.yml', 'r', encoding='utf-8') as f:
    app_config = yaml.safe_load(f.read())

STORAGE_SERVICE_URL = app_config['storage']['url']
STATS_FILE = app_config['stats']['filename']

# Default stats structure
DEFAULT_STATS = {
    "num_order_events": 0,
    "max_price": 0,
    "num_rating_events": 0,
    "max_rating": 0,
    "last_updated": "1996-07-07T00:00:00Z"
}


def populate_stats():
    """Periodically fetches data from the storage service and updates statistics."""
    logger.info("Starting periodic statistics processing.")

    if not os.path.exists(STATS_FILE):
        logger.warning(f"{STATS_FILE} does not exist. Creating with default stats.")
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_STATS, f, indent=4)
        logger.info(f"Created {STATS_FILE} with default statistics.")

    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        stats = json.load(f)

    last_updated = stats.get("last_updated", "1970-01-01T00:00:00Z")
    current_time = datetime.utcnow().isoformat() + "Z"

    try:
        order_response = requests.get(
            f"{STORAGE_SERVICE_URL}/events/order",
            params={"start_timestamp": last_updated, "end_timestamp": current_time}
        )
        rating_response = requests.get(
            f"{STORAGE_SERVICE_URL}/events/rating",
            params={"start_timestamp": last_updated, "end_timestamp": current_time}
        )

        if order_response.status_code == 200 and rating_response.status_code == 200:
            order_events = order_response.json()
            rating_events = rating_response.json()

            logger.info(f"Received {len(order_events)} order events.")
            logger.info(f"Received {len(rating_events)} rating events.")

            stats["num_order_events"] += len(order_events)
            stats["num_rating_events"] += len(rating_events)

            if order_events:
                stats["max_price"] = max(
                    stats["max_price"],
                    max(event["price"] for event in order_events)
                )

            if rating_events:
                stats["max_rating"] = max(
                    stats["max_rating"],
                    max(event["rating"] for event in rating_events)
                )

            stats["last_updated"] = current_time

            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=4)

            logger.debug(f"Updated statistics: {json.dumps(stats, indent=4)}")
        else:
            logger.error("Failed to fetch data from storage service.")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")

    logger.info("Periodic statistics processing completed.")


def init_scheduler():
    """Initializes the background scheduler."""
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(populate_stats, 'interval', seconds=app_config['scheduler']['interval'])
    sched.start()


def get_stats():
    """Handles GET requests for statistics."""
    logger.info("GET /stats request received.")

    if not os.path.exists(STATS_FILE):
        logger.error("Statistics file does not exist.")
        return {"message": "Statistics do not exist"}, 404

    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        stats = json.load(f)

    logger.debug(f"Returning statistics: {json.dumps(stats, indent=4)}")
    logger.info("GET /stats request processed successfully.")
    return stats, 200


# Connexion app and middleware setup
app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api("processing.yaml", base_path="/processing", strict_validation=True, validate_responses=True)

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
    init_scheduler()
    app.run(port=8100, host="0.0.0.0")
