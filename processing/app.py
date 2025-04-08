import os
import time
import json
import logging.config
from datetime import datetime
import yaml
import requests
from apscheduler.schedulers.background import BackgroundScheduler
import connexion

# Optional CORS setup
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware


# Ensure timestamps use UTC
logging.Formatter.converter = time.gmtime

# Load logging configuration
with open('./config/log_conf.yml', 'r', encoding='utf-8') as log_file:
    LOG_CONFIG = yaml.safe_load(log_file.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger("basicLogger")

# Load app configuration
with open('./config/app_conf.yml', 'r', encoding='utf-8') as conf_file:
    app_config = yaml.safe_load(conf_file.read())

STORAGE_SERVICE_URL = app_config['storage']['url']
STATS_FILE = app_config['stats']['filename']

# Default stats
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

    # Ensure file exists
    if not os.path.exists(STATS_FILE):
        logger.warning("%s does not exist. Creating new file with default stats.", STATS_FILE)
        with open(STATS_FILE, 'w', encoding='utf-8') as stats_file:
            json.dump(DEFAULT_STATS, stats_file, indent=4)
        logger.info("Created %s with default statistics.", STATS_FILE)

    with open(STATS_FILE, 'r', encoding='utf-8') as stats_file:
        stats = json.load(stats_file)

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

            logger.info("Received %d order events.", len(order_events))
            logger.info("Received %d rating events.", len(rating_events))

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

            with open(STATS_FILE, 'w', encoding='utf-8') as stats_file:
                json.dump(stats, stats_file, indent=4)

            logger.debug("Updated statistics: %s", json.dumps(stats, indent=4))
        else:
            logger.error("Error fetching data from the storage service.")

    except Exception as error:
        logger.error("An error occurred: %s", str(error))

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

    with open(STATS_FILE, 'r', encoding='utf-8') as stats_file:
        stats = json.load(stats_file)

    logger.debug("Returning statistics: %s", json.dumps(stats, indent=4))
    logger.info("GET /stats request processed successfully.")
    return stats, 200


# Set up the app
app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api("processing.yaml", base_path="/processing", strict_validation=True, validate_responses=True)

# CORS support
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
