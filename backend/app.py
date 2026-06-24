"""
app.py
Flask application factory. Serves the SPA shell (templates/index.html),
static assets (CSS/JS/GeoJSON/images), and the /api/* JSON endpoints
defined in routes.py. Also serves road network files from /road_network/.
"""
import os

from flask import Flask, render_template, send_from_directory

from . import prediction, weather, traffic
from .routes import api

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROAD_NETWORK_DIR = os.path.join(BASE_DIR, "road_network")


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
        static_url_path="/static",
    )
    app.config["JSON_SORT_KEYS"] = False

    # Load the dataset, models, and (re)initialize the crash/hazard DB once.
    prediction.init()

    # Initialize weather simulation for all road segments
    segment_ids = list(prediction._SOURCE_DF['segment_id'].astype(int))
    weather.init(segment_ids)

    # Initialize traffic temporal data (loads CSV once, builds segment mapping)
    traffic.init(prediction._SOURCE_DF)

    app.register_blueprint(api)

    @app.route("/")
    @app.route("/dashboard")
    def index():
        return render_template("index.html")

    # Serve Detection 9 road network files (GeoJSON, CSV) for download
    @app.route("/road_network/<path:filename>")
    def road_network_files(filename):
        return send_from_directory(ROAD_NETWORK_DIR, filename)

    return app
