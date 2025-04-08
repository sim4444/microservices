import time
import json
import os
from datetime import datetime
import httpx
import connexion
import yaml
import logging.config

# Load logging config
with open("config/log_conf.yml", "r") as f:
    log_config = yaml.safe_load(f)
    logging.config.dictConfig(log_config)

logger = logging.getLogger("basicLogger")

app = connexion.FlaskApp(__name__, specification_dir="./")
app.add_api("openapi.yml", base_path="/consistency_check")

# Load app config
with open("config/app_conf.yml", "r") as f:
    APP_CONF = yaml.safe_load(f)

DATA_FILE = APP_CONF["datastore"]["filepath"]

def run_consistency_checks():
    start_time = time.time()
    logger.info("Starting consistency check...")

    # Fetch stats and IDs
    processing_stats = httpx.get(f'{APP_CONF["processing"]["url"]}/stats').json()
    analyzer_stats = httpx.get(f'{APP_CONF["analyzer"]["url"]}/stats').json()
    storage_counts = httpx.get(f'{APP_CONF["storage"]["url"]}/counts').json()

    analyzer_order_ids = httpx.get(f'{APP_CONF["analyzer"]["url"]}/ids/events/order').json()
    analyzer_rating_ids = httpx.get(f'{APP_CONF["analyzer"]["url"]}/ids/events/rating').json()

    storage_order_ids = httpx.get(f'{APP_CONF["storage"]["url"]}/ids/events/order').json()
    storage_rating_ids = httpx.get(f'{APP_CONF["storage"]["url"]}/ids/events/rating').json()

    if not isinstance(analyzer_order_ids, list): analyzer_order_ids = []
    if not isinstance(analyzer_rating_ids, list): analyzer_rating_ids = []
    if not isinstance(storage_order_ids, list): storage_order_ids = []
    if not isinstance(storage_rating_ids, list): storage_rating_ids = []

    analyzer_ids = [(e["trace_id"], e["event_id"], "order") for e in analyzer_order_ids] + \
                   [(e["trace_id"], e["event_id"], "rating") for e in analyzer_rating_ids]
    storage_ids = [(e["trace_id"], e["event_id"], "order") for e in storage_order_ids] + \
                  [(e["trace_id"], e["event_id"], "rating") for e in storage_rating_ids]

    analyzer_set = {(e[0], e[1]): e[2] for e in analyzer_ids}
    storage_set = {(e[0], e[1]): e[2] for e in storage_ids}

    missing_in_db = [{"trace_id": t[0], "event_id": t[1], "type": analyzer_set[t]} for t in analyzer_set if t not in storage_set]
    missing_in_queue = [{"trace_id": t[0], "event_id": t[1], "type": storage_set[t]} for t in storage_set if t not in analyzer_set]

    logger.info("Consistency checks completed | processing_time_ms=%d | missing_in_db=%d | missing_in_queue=%d",
                int((time.time() - start_time) * 1000), len(missing_in_db), len(missing_in_queue))

    output = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "counts": {
            "processing": processing_stats,
            "queue": analyzer_stats,
            "db": storage_counts
        },
        "missing_in_db": missing_in_db,
        "missing_in_queue": missing_in_queue
    }

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(output, f, indent=4)

    duration_ms = int((time.time() - start_time) * 1000)
    return {"processing_time_ms": duration_ms}, 200

def get_checks():
    if not os.path.exists(DATA_FILE):
        logger.warning("Attempt to access /checks before any run.")
        return {"message": "No consistency check has been run."}, 404

    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    return data, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8300)
