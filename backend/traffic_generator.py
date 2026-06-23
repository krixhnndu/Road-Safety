import pandas as pd
import numpy as np


# =====================================
# LOAD ROAD DATASET
# =====================================

roads = pd.read_csv(
    "road_network/bengaluru_road_segments.csv"
)


# =====================================
# BASE CONGESTION FOR EACH ROAD
# =====================================

def get_base_congestion(row):

    score = 0.20

    # road class effect

    road_class = str(
        row["road_class"]
    ).lower()


    if "primary" in road_class:
        score += 0.25

    elif "secondary" in road_class:
        score += 0.18

    elif "residential" in road_class:
        score += 0.08


    # highway effect

    highway = str(
        row["highway"]
    ).lower()


    if highway != "nan":
        score += 0.15


    # length effect

    road_length = float(
        row["length_m"]
    )


    if road_length > 2000:
        score += 0.12

    elif road_length > 1000:
        score += 0.07


    # connected roads effect

    connections = str(
        row["connected_segment_ids"]
    )


    num_connections = len(
        connections.split(",")
    )


    if num_connections > 4:
        score += 0.15

    elif num_connections > 2:
        score += 0.08


    return min(score, 1.0)


# =====================================
# TIME OF DAY EFFECT
# =====================================

def time_factor(hour):

    # morning rush

    if 7 <= hour <= 10:
        return 1.6


    # evening rush

    elif 17 <= hour <= 20:
        return 1.8


    # daytime

    elif 11 <= hour <= 15:
        return 1.1


    # night

    elif 22 <= hour or hour <= 5:
        return 0.35


    return 0.8


# =====================================
# WEEKEND EFFECT
# =====================================

def weekend_factor(day):

    # saturday sunday

    if day in [5, 6]:
        return 0.80

    return 1.0


# =====================================
# RANDOM INCIDENT EFFECT
# =====================================

def incident_factor():

    x = np.random.rand()

    if x < 0.02:
        return "Accident", 1.50

    elif x < 0.04:
        return "Construction", 1.30

    return "None", 1.0


# =====================================
# GENERATE TIMESTAMPS
# 60 DAYS
# EVERY 3 HOURS
# =====================================

start_date = pd.Timestamp.today().floor("D")

timestamps = pd.date_range(
    start=start_date,
    periods=60 * 8,
    freq="3h"
)


rows = []


# =====================================
# MAIN LOOP
# =====================================

for _, road in roads.iterrows():

    base = get_base_congestion(road)

    for ts in timestamps:

        tm = time_factor(ts.hour)

        wk = weekend_factor(ts.weekday())

        incident, im = incident_factor()


        congestion = base * tm * wk * im


        # random variation

        congestion += np.random.uniform(-0.05, 0.05)

        congestion = max(0.05, min(1.0, congestion))


        # synthetic speed

        avg_speed = 80 * (1 - congestion)


        # synthetic vehicle density

        vehicle_density = int(
            congestion * np.random.randint(100, 500)
        )


        rows.append([

            road["segment_id"],

            road["road_name"],

            ts,

            incident,

            round(congestion, 3),

            round(avg_speed, 2),

            vehicle_density
        ])


# =====================================
# SAVE DATASET
# =====================================

df = pd.DataFrame(

    rows,

    columns=[

        "segment_id",

        "road_name",

        "timestamp",

        "incident",

        "congestion_score",

        "avg_speed_kmph",

        "vehicle_density"
    ]
)


df.to_csv(

    "datasets/traffic_temporal_data.csv",

    index=False
)


print("SUCCESS")
print("Rows generated:", len(df))
print("Saved to datasets/traffic_temporal_data.csv")