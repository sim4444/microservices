from sqlalchemy import create_engine, Integer, Float, String, DateTime, func, Text
from datetime import datetime

from sqlalchemy.orm import sessionmaker, declarative_base, mapped_column
import os
import yaml


with open("./config/app_conf.yml", "r") as f:
    app_config = yaml.safe_load(f.read())

DB_USER = app_config["datastore"]["user"]
DB_PASSWORD = app_config["datastore"]["password"]
DB_HOST = app_config["datastore"]["hostname"]
DB_PORT = app_config["datastore"]["port"]
DB_NAME = app_config["datastore"]["db"]

# Define MySQL database connection string
DATABASE_URI = f"mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URI)
SessionLocal = sessionmaker(bind=engine)

# Define the base class for models
Base = declarative_base()

# order event Model
class OrderEvent(Base):
    __tablename__ = "order_events"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id = mapped_column(String(36), nullable=False) 
    user_id = mapped_column(String(255), nullable=False) 
    user_country = mapped_column(String(255), nullable=False)  
    price = mapped_column(Float, nullable=False)
    order_timestamp = mapped_column(DateTime, nullable=False)
    date_created = mapped_column(DateTime, default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "user_country": self.user_country,
            "order_timestamp": self.order_timestamp.isoformat(timespec='milliseconds') + "Z" if self.order_timestamp else None,
            "price": self.price,
            "date_created": self.date_created.isoformat(timespec='milliseconds') + "Z" if self.date_created else None
        }



# rating event Model
class RatingEvent(Base):
    __tablename__ = "rating_events"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id = mapped_column(String(36), nullable=False)  
    device_id = mapped_column(String(255), nullable=False)  
    product_type = mapped_column(String(255), nullable=False)  
    rating = mapped_column(Float, nullable=False)
    timestamp = mapped_column(DateTime, nullable=False)
    date_created = mapped_column(DateTime, default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "device_id": self.device_id,
            "product_type": self.product_type,
            "timestamp": self.timestamp.isoformat(timespec='milliseconds') + "Z" if self.timestamp else None,
            "rating": self.rating,
            "date_created": self.date_created.isoformat(timespec='milliseconds') + "Z" if self.date_created else None
        }

# Function to create tables
def init_db():
    Base.metadata.create_all(engine)

# Function to drop tables
def drop_db():
    """Drops all tables in the database."""
    Base.metadata.drop_all(engine)
    print("All tables dropped successfully!")
