# from fastapi import FastAPI
# from pydantic import BaseModel
# from fastapi.middleware.cors import CORSMiddleware
# import pandas as pd
# import networkx as nx
# import geopandas as gpd
# from sqlalchemy import create_engine
# from shapely import wkt
# from shapely.geometry import LineString
# from fastapi.responses import FileResponse
#
# app = FastAPI()
#
# @app.get("/")
# def serve_home_page():
#     # השרת ישלח את קובץ ה-HTML שלנו כשנכנסים לכתובת הראשית
#     return FileResponse("index.html")
#
# # מאפשר לדפדפן (צד הלקוח) לפנות לשרת ה-API הזה
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# # --- הגדרות ---
# SERVER_NAME = r'DESKTOP-QU3PBU9\SQLEXPRESS01'
# DATABASE_NAME = 'ShadowAppDB'
# DRIVER = 'ODBC Driver 17 for SQL Server'
# connection_string = f"mssql+pyodbc://@{SERVER_NAME}/{DATABASE_NAME}?driver={DRIVER}&trusted_connection=yes"
# engine = create_engine(connection_string)
#
# SUN_PENALTY = 10.0
# TRANSITION_COST = 5.0
#
#
# # המבנה של הבקשה שנקבל מהמשתמש
# class RouteRequest(BaseModel):
#     start_lat: float
#     start_lng: float
#     end_lat: float
#     end_lng: float
#     date_str: str  # התאריך שהמשתמש/המערכת בחרה
#     hour_val: int  # השעה שהמשתמש/המערכת בחרה
#
#
# # --- פונקציות ליבה (שהיו חסרות) ---
#
# def build_polished_graph(date_str, hour_val):
#     print(f"1. Fetching data for {date_str} @ {hour_val}:00...")
#
#     sql = f"""
#     SELECT
#         s.SegmentID,
#         s.LengthMeters,
#         s.Geom.STAsText() as geometry,
#         ISNULL(sc.ShadowRatio, 0) as ShadowRatio
#     FROM StreetSegments s
#     LEFT JOIN SegmentScores sc
#         ON s.SegmentID = sc.SegmentID
#         AND sc.SeasonDate = '{date_str}'
#         AND DATEPART(HOUR, sc.TimeOfDay) = {hour_val}
#     """
#
#     df = pd.read_sql(sql, engine)
#     df['geometry'] = df['geometry'].apply(wkt.loads)
#     gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
#
#     print(f"   Loaded {len(gdf)} segments. Building graph...")
#     G = nx.Graph()
#
#     for _, row in gdf.iterrows():
#         coords = list(row.geometry.coords)
#         u = coords[0]
#         v = coords[-1]
#
#         length = row['LengthMeters']
#         shadow_ratio = row['ShadowRatio']
#
#         sun_factor = 1.0 - shadow_ratio
#         cost_time = length * (1 + (sun_factor * SUN_PENALTY))
#         total_weight = cost_time + TRANSITION_COST
#
#         G.add_edge(u, v, weight=total_weight, length=length, geometry=row.geometry)
#
#     return G
#
#
# def get_smooth_path(G, nodes):
#     if not nodes or len(nodes) < 2:
#         return None
#
#     path_coords = []
#
#     for i in range(len(nodes) - 1):
#         u = nodes[i]
#         v = nodes[i + 1]
#         data = G.get_edge_data(u, v)
#
#         edge_data = data[0] if 0 in data else data
#         geom = edge_data.get('geometry')
#
#         if geom:
#             coords = list(geom.coords)
#             if (coords[0][0] - u[0]) ** 2 + (coords[0][1] - u[1]) ** 2 > 1e-8:
#                 coords = coords[::-1]
#             path_coords.extend(coords)
#
#     if not path_coords:
#         return None
#
#     raw_line = LineString(path_coords)
#     simplified_line = raw_line.simplify(tolerance=0.0001, preserve_topology=True)
#
#     return simplified_line
#
#
# # --- מנגנון מטמון (Cache) ---
# graphs_cache = {}
#
#
# def get_or_build_graph(date_str, hour_val):
#     """
#     בודק אם הגרף לשעה המבוקשת כבר קיים בזיכרון.
#     אם כן, מחזיר אותו מיד. אם לא, בונה אותו ושומר לפעמים הבאות.
#     """
#     cache_key = f"{date_str}_{hour_val}"
#
#     if cache_key not in graphs_cache:
#         print(f"Graph for {cache_key} not in cache. Building from SQL...")
#         graphs_cache[cache_key] = build_polished_graph(date_str, hour_val)
#     else:
#         print(f"Using cached graph for {cache_key}.")
#
#     return graphs_cache[cache_key]
#
#
# # טעינה מראש של שעת ברירת המחדל בעליית השרת
# print("Pre-loading default graph into memory (14:00)...")
# get_or_build_graph('2025-06-21', 14)
# print("Server is ready.")
#
#
# # --- נתיב ה-API ---
# @app.post("/calculate_route")
# def calculate_route(request: RouteRequest):
#     # שליפת הגרף הספציפי לשעה והתאריך שהמשתמש/המערכת בחרה
#     G = get_or_build_graph(request.date_str, request.hour_val)
#
#     # מציאת צמתים קרובים
#     start_node = min(G.nodes, key=lambda n: (n[1] - request.start_lat) ** 2 + (n[0] - request.start_lng) ** 2)
#     end_node = min(G.nodes, key=lambda n: (n[1] - request.end_lat) ** 2 + (n[0] - request.end_lng) ** 2)
#
#     # מציאת המסלול המוצל
#     shadiest_nodes = nx.shortest_path(G, source=start_node, target=end_node, weight='weight')
#     line_shade = get_smooth_path(G, shadiest_nodes)
#
#     route_coords = []
#     if line_shade:
#         route_coords = [{"lat": y, "lng": x} for x, y in line_shade.coords]
#
#     return {"route": route_coords}
#
#
# if __name__ == "__main__":
#     import uvicorn
#
#     uvicorn.run(app, host="0.0.0.0", port=8000)
#

#
# from fastapi import FastAPI
# from pydantic import BaseModel
# from fastapi.middleware.cors import CORSMiddleware
# import pandas as pd
# import networkx as nx
# import geopandas as gpd
# from sqlalchemy import create_engine
# from shapely import wkt
# from shapely.geometry import LineString
# from fastapi.responses import FileResponse
#
# app = FastAPI()
#
#
# @app.get("/")
# def serve_home_page():
#     return FileResponse("index.html")
#
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# # --- הגדרות חיבור ---
# SERVER_NAME = r'DESKTOP-QU3PBU9\SQLEXPRESS01'
# DATABASE_NAME = 'ShadowAppDB'
# DRIVER = 'ODBC Driver 17 for SQL Server'
# connection_string = f"mssql+pyodbc://@{SERVER_NAME}/{DATABASE_NAME}?driver={DRIVER}&trusted_connection=yes"
# engine = create_engine(connection_string)
#
# SUN_PENALTY = 10.0
# TRANSITION_COST = 5.0
#
#
# class RouteRequest(BaseModel):
#     start_lat: float
#     start_lng: float
#     end_lat: float
#     end_lng: float
#     date_str: str
#     hour_val: int
#
#
# # --- פונקציות עזר ---
#
# def build_polished_graph(date_str, hour_val):
#     print(f"Fetching data for {date_str} @ {hour_val}:00...")
#     sql = f"""
#     SELECT
#         s.SegmentID,
#         s.LengthMeters,
#         s.Geom.STAsText() as geometry,
#         ISNULL(sc.ShadowRatio, 0) as ShadowRatio
#     FROM StreetSegments s
#     LEFT JOIN SegmentScores sc
#         ON s.SegmentID = sc.SegmentID
#         AND sc.SeasonDate = '{date_str}'
#         AND DATEPART(HOUR, sc.TimeOfDay) = {hour_val}
#     """
#     df = pd.read_sql(sql, engine)
#     df['geometry'] = df['geometry'].apply(wkt.loads)
#     gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
#
#     G = nx.Graph()
#     for _, row in gdf.iterrows():
#         coords = list(row.geometry.coords)
#         u, v = coords[0], coords[-1]
#         length = row['LengthMeters']
#         shadow_ratio = row['ShadowRatio']
#
#         # חישוב משקל "עלות" עבור המסלול המוצל
#         sun_factor = 1.0 - shadow_ratio
#         cost_weight = length * (1 + (sun_factor * SUN_PENALTY)) + TRANSITION_COST
#
#         G.add_edge(u, v, weight=cost_weight, length=length, shadow_ratio=shadow_ratio, geometry=row.geometry)
#     return G
#
#
# def get_smooth_path(G, nodes):
#     if not nodes or len(nodes) < 2: return None
#     path_coords = []
#     for i in range(len(nodes) - 1):
#         u, v = nodes[i], nodes[i + 1]
#         edge_data = G.get_edge_data(u, v)
#         geom = edge_data.get('geometry')
#         if geom:
#             coords = list(geom.coords)
#             if (coords[0][0] - u[0]) ** 2 + (coords[0][1] - u[1]) ** 2 > 1e-8:
#                 coords = coords[::-1]
#             path_coords.extend(coords)
#     if not path_coords: return None
#     return LineString(path_coords).simplify(0.0001)
#
#
# graphs_cache = {}
#
#
# def get_or_build_graph(date_str, hour_val):
#     cache_key = f"{date_str}_{hour_val}"
#     if cache_key not in graphs_cache:
#         graphs_cache[cache_key] = build_polished_graph(date_str, hour_val)
#     return graphs_cache[cache_key]
#
#
# # --- נתיב ה-API המרכזי ---
#
# @app.post("/calculate_route")
# def calculate_route(request: RouteRequest):
#     G = get_or_build_graph(request.date_str, request.hour_val)
#
#     # מציאת הצמתים הקרובים ביותר ללחיצות המשתמש
#     start_node = min(G.nodes, key=lambda n: (n[1] - request.start_lat) ** 2 + (n[0] - request.start_lng) ** 2)
#     end_node = min(G.nodes, key=lambda n: (n[1] - request.end_lat) ** 2 + (n[0] - request.end_lng) ** 2)
#
#     # 1. חישוב מסלול מוצל (לפי משקל ה-cost)
#     shadiest_nodes = nx.shortest_path(G, source=start_node, target=end_node, weight='weight')
#     line_shade = get_smooth_path(G, shadiest_nodes)
#
#     # 2. חישוב מסלול קצר רגיל (לפי משקל ה-length)
#     standard_nodes = nx.shortest_path(G, source=start_node, target=end_node, weight='length')
#     line_standard = get_smooth_path(G, standard_nodes)
#
#     # הכנת קואורדינטות לתצוגה במפה
#     shade_coords = [{"lat": y, "lng": x} for x, y in line_shade.coords] if line_shade else []
#     standard_coords = [{"lat": y, "lng": x} for x, y in line_standard.coords] if line_standard else []
#
#     # חישוב נתונים עבור המסלול המוצל
#     dist_shade = sum(
#         G.get_edge_data(shadiest_nodes[i], shadiest_nodes[i + 1])['length'] for i in range(len(shadiest_nodes) - 1))
#     shadow_shade = sum(G.get_edge_data(shadiest_nodes[i], shadiest_nodes[i + 1])['shadow_ratio'] for i in
#                        range(len(shadiest_nodes) - 1)) / (len(shadiest_nodes) - 1)
#
#     # חישוב נתונים עבור המסלול הסטנדרטי
#     dist_standard = sum(
#         G.get_edge_data(standard_nodes[i], standard_nodes[i + 1])['length'] for i in range(len(standard_nodes) - 1))
#     shadow_standard = sum(G.get_edge_data(standard_nodes[i], standard_nodes[i + 1])['shadow_ratio'] for i in
#                           range(len(standard_nodes) - 1)) / (len(standard_nodes) - 1)
#
#     return {
#         "shade_route": shade_coords,
#         "standard_route": standard_coords,
#         "stats": {
#             "shade": {"dist": round(dist_shade), "shadow": round(shadow_shade * 100)},
#             "standard": {"dist": round(dist_standard), "shadow": round(shadow_standard * 100)}
#         }
#     }
#
#
# if __name__ == "__main__":
#     import uvicorn
#
#     # טעינה מוקדמת של כל שעות המפתח לזיכרון ברגע שהשרת עולה
#     print("Pre-loading all graphs into memory. Please wait...")
#     hours_to_preload = [8, 10, 14, 16]  # או כל שעות שיש לך ב-SQL
#
#     for h in hours_to_preload:
#         get_or_build_graph('2025-06-21', h)
#
#     print("All graphs loaded! Server is ready.")
#     uvicorn.run(app, host="0.0.0.0", port=8000)

# from fastapi import FastAPI
# from pydantic import BaseModel
# from fastapi.middleware.cors import CORSMiddleware
# import pandas as pd
# import networkx as nx
# import geopandas as gpd
# from sqlalchemy import create_engine
# from shapely import wkt
# from shapely.geometry import LineString
# from fastapi.responses import FileResponse
#
# # הנה השורה שהייתה חסרה וגרמה לשגיאה!
# app = FastAPI()
#
#
# @app.get("/")
# def serve_home_page():
#     return FileResponse("index.html")
#
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# # --- הגדרות חיבור ---
# SERVER_NAME = r'DESKTOP-QU3PBU9\SQLEXPRESS01'
# DATABASE_NAME = 'ShadowAppDB'
# DRIVER = 'ODBC Driver 17 for SQL Server'
# connection_string = f"mssql+pyodbc://@{SERVER_NAME}/{DATABASE_NAME}?driver={DRIVER}&trusted_connection=yes"
# engine = create_engine(connection_string)
#
# SUN_PENALTY = 10.0
# TRANSITION_COST = 5.0
#
#
# class RouteRequest(BaseModel):
#     start_lat: float
#     start_lng: float
#     end_lat: float
#     end_lng: float
#     date_str: str
#     hour_val: int
#
#
# # --- פונקציות עזר ---
# def build_polished_graph(date_str, hour_val):
#     print(f"Fetching data for {date_str} @ {hour_val}:00...")
#     sql = f"""
#     SELECT
#         s.SegmentID,
#         s.LengthMeters,
#         s.Geom.STAsText() as geometry,
#         ISNULL(sc.ShadowRatio, 0) as ShadowRatio
#     FROM StreetSegments s
#     LEFT JOIN SegmentScores sc
#         ON s.SegmentID = sc.SegmentID
#         AND sc.SeasonDate = '{date_str}'
#         AND DATEPART(HOUR, sc.TimeOfDay) = {hour_val}
#     """
#     df = pd.read_sql(sql, engine)
#     df['geometry'] = df['geometry'].apply(wkt.loads)
#     gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
#
#     G = nx.Graph()
#     for _, row in gdf.iterrows():
#         coords = list(row.geometry.coords)
#         u, v = coords[0], coords[-1]
#         length = row['LengthMeters']
#         shadow_ratio = row['ShadowRatio']
#
#         sun_factor = 1.0 - shadow_ratio
#         cost_weight = length * (1 + (sun_factor * SUN_PENALTY)) + TRANSITION_COST
#
#         G.add_edge(u, v, weight=cost_weight, length=length, shadow_ratio=shadow_ratio, geometry=row.geometry)
#     return G
#
#
# def get_smooth_path(G, nodes):
#     if not nodes or len(nodes) < 2: return None
#     path_coords = []
#     for i in range(len(nodes) - 1):
#         u, v = nodes[i], nodes[i + 1]
#         edge_data = G.get_edge_data(u, v)
#         geom = edge_data.get('geometry')
#         if geom:
#             coords = list(geom.coords)
#             if (coords[0][0] - u[0]) ** 2 + (coords[0][1] - u[1]) ** 2 > 1e-8:
#                 coords = coords[::-1]
#             path_coords.extend(coords)
#     if not path_coords: return None
#     return LineString(path_coords).simplify(0.0001)
#
#
# graphs_cache = {}
#
#
# def get_or_build_graph(date_str, hour_val):
#     cache_key = f"{date_str}_{hour_val}"
#     if cache_key not in graphs_cache:
#         graphs_cache[cache_key] = build_polished_graph(date_str, hour_val)
#     return graphs_cache[cache_key]
#
#
# # --- נתיב ה-API המרכזי ---
# @app.post("/calculate_route")
# def calculate_route(request: RouteRequest):
#     G = get_or_build_graph(request.date_str, request.hour_val)
#
#     start_node = min(G.nodes, key=lambda n: (n[1] - request.start_lat) ** 2 + (n[0] - request.start_lng) ** 2)
#     end_node = min(G.nodes, key=lambda n: (n[1] - request.end_lat) ** 2 + (n[0] - request.end_lng) ** 2)
#
#     # 1. חישוב המסלול הרגיל
#     standard_nodes = nx.shortest_path(G, source=start_node, target=end_node, weight='length')
#     dist_standard = sum(G.get_edge_data(standard_nodes[i], standard_nodes[i + 1]).get('length', 0) for i in
#                         range(len(standard_nodes) - 1))
#
#     # הגדרת המגבלה: מקסימום 500 מטרים מעבר למסלול הרגיל
#     MAX_ALLOWED_DISTANCE = dist_standard + 500
#     shadiest_nodes = standard_nodes
#
#     try:
#         path_generator = nx.shortest_simple_paths(G, source=start_node, target=end_node, weight='weight')
#         attempts = 0
#         for path in path_generator:
#             attempts += 1
#             path_dist = sum(G.get_edge_data(path[i], path[i + 1]).get('length', 0) for i in range(len(path) - 1))
#
#             if path_dist <= MAX_ALLOWED_DISTANCE:
#                 shadiest_nodes = path
#                 break
#
#             if attempts >= 50:
#                 break
#     except nx.NetworkXNoPath:
#         pass
#
#     line_shade = get_smooth_path(G, shadiest_nodes)
#     line_standard = get_smooth_path(G, standard_nodes)
#
#     shade_coords = [{"lat": y, "lng": x} for x, y in line_shade.coords] if line_shade else []
#     standard_coords = [{"lat": y, "lng": x} for x, y in line_standard.coords] if line_standard else []
#
#     dist_shade = sum(G.get_edge_data(shadiest_nodes[i], shadiest_nodes[i + 1]).get('length', 0) for i in
#                      range(len(shadiest_nodes) - 1))
#
#     if len(shadiest_nodes) > 1:
#         shadow_shade = sum(G.get_edge_data(shadiest_nodes[i], shadiest_nodes[i + 1]).get('shadow_ratio', 0) for i in
#                            range(len(shadiest_nodes) - 1)) / (len(shadiest_nodes) - 1)
#     else:
#         shadow_shade = 0
#
#     if len(standard_nodes) > 1:
#         shadow_standard = sum(G.get_edge_data(standard_nodes[i], standard_nodes[i + 1]).get('shadow_ratio', 0) for i in
#                               range(len(standard_nodes) - 1)) / (len(standard_nodes) - 1)
#     else:
#         shadow_standard = 0
#
#     return {
#         "shade_route": shade_coords,
#         "standard_route": standard_coords,
#         "stats": {
#             "shade": {"dist": round(dist_shade), "shadow": round(shadow_shade * 100)},
#             "standard": {"dist": round(dist_standard), "shadow": round(shadow_standard * 100)}
#         }
#     }
#
#
# if __name__ == "__main__":
#     import uvicorn
#
#     print("Pre-loading all graphs into memory. Please wait...")
#     hours_to_preload = [8, 10, 14, 16]
#     for h in hours_to_preload:
#         get_or_build_graph('2025-06-21', h)
#
#     print("All graphs loaded! Server is ready.")
#     uvicorn.run(app, host="0.0.0.0", port=8000)

# from fastapi import FastAPI
# from pydantic import BaseModel
# from fastapi.middleware.cors import CORSMiddleware
# import pandas as pd
# import networkx as nx
# import geopandas as gpd
# from sqlalchemy import create_engine
# from shapely import wkt
# from shapely.geometry import LineString
# from fastapi.responses import FileResponse
# import pickle
# import os
#
# app = FastAPI()
#
#
# @app.get("/")
# def serve_home_page():
#     return FileResponse("index.html")
#
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# # --- הגדרות חיבור לגיבוי ---
# SERVER_NAME = r'DESKTOP-QU3PBU9\SQLEXPRESS01'
# DATABASE_NAME = 'ShadowAppDB'
# DRIVER = 'ODBC Driver 17 for SQL Server'
# connection_string = f"mssql+pyodbc://@{SERVER_NAME}/{DATABASE_NAME}?driver={DRIVER}&trusted_connection=yes"
# engine = create_engine(connection_string)
#
# SUN_PENALTY = 10.0
# TRANSITION_COST = 5.0
#
#
# class RouteRequest(BaseModel):
#     start_lat: float
#     start_lng: float
#     end_lat: float
#     end_lng: float
#     date_str: str
#     hour_val: int
#
#
# def build_polished_graph(date_str, hour_val):
#     print(f"Fetching data for {date_str} @ {hour_val}:00 from SQL...")
#     sql = f"""
#     SELECT
#         s.SegmentID,
#         s.LengthMeters,
#         s.Geom.STAsText() as geometry,
#         ISNULL(sc.ShadowRatio, 0) as ShadowRatio
#     FROM StreetSegments s
#     LEFT JOIN SegmentScores sc
#         ON s.SegmentID = sc.SegmentID
#         AND sc.SeasonDate = '{date_str}'
#         AND DATEPART(HOUR, sc.TimeOfDay) = {hour_val}
#     """
#     df = pd.read_sql(sql, engine)
#     df['geometry'] = df['geometry'].apply(wkt.loads)
#     gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
#
#     G = nx.Graph()
#     for _, row in gdf.iterrows():
#         coords = list(row.geometry.coords)
#         u, v = coords[0], coords[-1]
#         length = row['LengthMeters']
#         shadow_ratio = row['ShadowRatio']
#
#         sun_factor = 1.0 - shadow_ratio
#         cost_weight = length * (1 + (sun_factor * SUN_PENALTY)) + TRANSITION_COST
#
#         G.add_edge(u, v, weight=cost_weight, length=length, shadow_ratio=shadow_ratio, geometry=row.geometry)
#     return G
#
#
# def get_smooth_path(G, nodes):
#     if not nodes or len(nodes) < 2: return None
#     path_coords = []
#     for i in range(len(nodes) - 1):
#         u, v = nodes[i], nodes[i + 1]
#         edge_data = G.get_edge_data(u, v)
#         geom = edge_data.get('geometry')
#         if geom:
#             coords = list(geom.coords)
#             if (coords[0][0] - u[0]) ** 2 + (coords[0][1] - u[1]) ** 2 > 1e-8:
#                 coords = coords[::-1]
#             path_coords.extend(coords)
#     if not path_coords: return None
#     return LineString(path_coords).simplify(0.0001)
#
#
# graphs_cache = {}
#
#
# def get_or_build_graph(date_str, hour_val):
#     cache_key = f"{date_str}_{hour_val}"
#
#     if cache_key in graphs_cache:
#         return graphs_cache[cache_key]
#
#     file_path = f'graphs/graph_{hour_val}.pkl'
#     if os.path.exists(file_path):
#         print(f"Loading graph for {hour_val}:00 from file ({file_path})...")
#         with open(file_path, 'rb') as f:
#             G = pickle.load(f)
#         graphs_cache[cache_key] = G
#         return G
#     else:
#         print(f"File {file_path} not found. Falling back to SQL...")
#         G = build_polished_graph(date_str, hour_val)
#         graphs_cache[cache_key] = G
#         return G
#
#
# @app.post("/calculate_route")
# def calculate_route(request: RouteRequest):
#     G = get_or_build_graph(request.date_str, request.hour_val)
#
#     start_node = min(G.nodes, key=lambda n: (n[1] - request.start_lat) ** 2 + (n[0] - request.start_lng) ** 2)
#     end_node = min(G.nodes, key=lambda n: (n[1] - request.end_lat) ** 2 + (n[0] - request.end_lng) ** 2)
#
#     standard_nodes = nx.shortest_path(G, source=start_node, target=end_node, weight='length')
#     dist_standard = sum(G.get_edge_data(standard_nodes[i], standard_nodes[i + 1]).get('length', 0) for i in
#                         range(len(standard_nodes) - 1))
#
#     MAX_ALLOWED_DISTANCE = dist_standard + 500
#     shadiest_nodes = standard_nodes
#
#     try:
#         path_generator = nx.shortest_simple_paths(G, source=start_node, target=end_node, weight='weight')
#         attempts = 0
#         for path in path_generator:
#             attempts += 1
#             path_dist = sum(G.get_edge_data(path[i], path[i + 1]).get('length', 0) for i in range(len(path) - 1))
#
#             if path_dist <= MAX_ALLOWED_DISTANCE:
#                 shadiest_nodes = path
#                 break
#
#             if attempts >= 50:
#                 break
#     except nx.NetworkXNoPath:
#         pass
#
#     line_shade = get_smooth_path(G, shadiest_nodes)
#     line_standard = get_smooth_path(G, standard_nodes)
#
#     shade_coords = [{"lat": y, "lng": x} for x, y in line_shade.coords] if line_shade else []
#     standard_coords = [{"lat": y, "lng": x} for x, y in line_standard.coords] if line_standard else []
#
#     dist_shade = sum(G.get_edge_data(shadiest_nodes[i], shadiest_nodes[i + 1]).get('length', 0) for i in
#                      range(len(shadiest_nodes) - 1))
#
#     if len(shadiest_nodes) > 1:
#         shadow_shade = sum(G.get_edge_data(shadiest_nodes[i], shadiest_nodes[i + 1]).get('shadow_ratio', 0) for i in
#                            range(len(shadiest_nodes) - 1)) / (len(shadiest_nodes) - 1)
#     else:
#         shadow_shade = 0
#
#     if len(standard_nodes) > 1:
#         shadow_standard = sum(G.get_edge_data(standard_nodes[i], standard_nodes[i + 1]).get('shadow_ratio', 0) for i in
#                               range(len(standard_nodes) - 1)) / (len(standard_nodes) - 1)
#     else:
#         shadow_standard = 0
#
#     return {
#         "shade_route": shade_coords,
#         "standard_route": standard_coords,
#         "stats": {
#             "shade": {"dist": round(dist_shade), "shadow": round(shadow_shade * 100)},
#             "standard": {"dist": round(dist_standard), "shadow": round(shadow_standard * 100)}
#         }
#     }
#
#
# if __name__ == "__main__":
#     import uvicorn
#
#     print("Pre-loading all graphs into memory. Please wait...")
#     hours_to_preload = [8, 10, 14, 16]
#     for h in hours_to_preload:
#         get_or_build_graph('2025-06-21', h)
#
#     print("All graphs loaded! Server is ready.")
#     uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import networkx as nx
import geopandas as gpd
from sqlalchemy import create_engine
from shapely import wkt
from shapely.geometry import LineString
from fastapi.responses import FileResponse
import pickle
import os
import zipfile

# 1. יצירת התיקייה אם היא לא קיימת
if not os.path.exists('graphs'):
    os.makedirs('graphs')

# 2. חילוץ אוטומטי של קבצי ה-ZIP הקטנים כשמעלים לענן
zip_files = ['graph_8.zip', 'graph_10.zip', 'graph_14.zip', 'graph_16.zip']
for zip_name in zip_files:
    if os.path.exists(zip_name):
        print(f"Extracting {zip_name}...")
        with zipfile.ZipFile(zip_name, 'r') as zip_ref:
            # מחלץ את התוכן לתוך תיקיית graphs
            zip_ref.extractall('graphs')

app = FastAPI()


@app.get("/")
def serve_home_page():
    return FileResponse("index.html")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- הגדרות חיבור לגיבוי ---
SERVER_NAME = r'DESKTOP-QU3PBU9\SQLEXPRESS01'
DATABASE_NAME = 'ShadowAppDB'
DRIVER = 'ODBC Driver 17 for SQL Server'
connection_string = f"mssql+pyodbc://@{SERVER_NAME}/{DATABASE_NAME}?driver={DRIVER}&trusted_connection=yes"
engine = create_engine(connection_string)

SUN_PENALTY = 10.0
TRANSITION_COST = 5.0


class RouteRequest(BaseModel):
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    date_str: str
    hour_val: int


def build_polished_graph(date_str, hour_val):
    print(f"Fetching data for {date_str} @ {hour_val}:00 from SQL...")
    sql = f"""
    SELECT 
        s.SegmentID, 
        s.LengthMeters,
        s.Geom.STAsText() as geometry,
        ISNULL(sc.ShadowRatio, 0) as ShadowRatio
    FROM StreetSegments s
    LEFT JOIN SegmentScores sc 
        ON s.SegmentID = sc.SegmentID 
        AND sc.SeasonDate = '{date_str}' 
        AND DATEPART(HOUR, sc.TimeOfDay) = {hour_val}
    """
    df = pd.read_sql(sql, engine)
    df['geometry'] = df['geometry'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")

    G = nx.Graph()
    for _, row in gdf.iterrows():
        coords = list(row.geometry.coords)
        u, v = coords[0], coords[-1]
        length = row['LengthMeters']
        shadow_ratio = row['ShadowRatio']

        sun_factor = 1.0 - shadow_ratio
        cost_weight = length * (1 + (sun_factor * SUN_PENALTY)) + TRANSITION_COST

        G.add_edge(u, v, weight=cost_weight, length=length, shadow_ratio=shadow_ratio, geometry=row.geometry)
    return G


def get_smooth_path(G, nodes):
    if not nodes or len(nodes) < 2: return None
    path_coords = []
    for i in range(len(nodes) - 1):
        u, v = nodes[i], nodes[i + 1]
        edge_data = G.get_edge_data(u, v)
        geom = edge_data.get('geometry')
        if geom:
            coords = list(geom.coords)
            if (coords[0][0] - u[0]) ** 2 + (coords[0][1] - u[1]) ** 2 > 1e-8:
                coords = coords[::-1]
            path_coords.extend(coords)
    if not path_coords: return None
    return LineString(path_coords).simplify(0.0001)


graphs_cache = {}


def get_or_build_graph(date_str, hour_val):
    cache_key = f"{date_str}_{hour_val}"

    if cache_key in graphs_cache:
        return graphs_cache[cache_key]

    file_path = f'graphs/graph_{hour_val}.pkl'
    if os.path.exists(file_path):
        print(f"Loading graph for {hour_val}:00 from file ({file_path})...")
        with open(file_path, 'rb') as f:
            G = pickle.load(f)
        graphs_cache[cache_key] = G
        return G
    else:
        print(f"File {file_path} not found. Falling back to SQL...")
        G = build_polished_graph(date_str, hour_val)
        graphs_cache[cache_key] = G
        return G


@app.post("/calculate_route")
def calculate_route(request: RouteRequest):
    G = get_or_build_graph(request.date_str, request.hour_val)

    start_node = min(G.nodes, key=lambda n: (n[1] - request.start_lat) ** 2 + (n[0] - request.start_lng) ** 2)
    end_node = min(G.nodes, key=lambda n: (n[1] - request.end_lat) ** 2 + (n[0] - request.end_lng) ** 2)

    standard_nodes = nx.shortest_path(G, source=start_node, target=end_node, weight='length')
    dist_standard = sum(G.get_edge_data(standard_nodes[i], standard_nodes[i + 1]).get('length', 0) for i in
                        range(len(standard_nodes) - 1))

    MAX_ALLOWED_DISTANCE = dist_standard + 500
    shadiest_nodes = standard_nodes

    try:
        path_generator = nx.shortest_simple_paths(G, source=start_node, target=end_node, weight='weight')
        attempts = 0
        for path in path_generator:
            attempts += 1
            path_dist = sum(G.get_edge_data(path[i], path[i + 1]).get('length', 0) for i in range(len(path) - 1))

            if path_dist <= MAX_ALLOWED_DISTANCE:
                shadiest_nodes = path
                break

            if attempts >= 50:
                break
    except nx.NetworkXNoPath:
        pass

    line_shade = get_smooth_path(G, shadiest_nodes)
    line_standard = get_smooth_path(G, standard_nodes)

    shade_coords = [{"lat": y, "lng": x} for x, y in line_shade.coords] if line_shade else []
    standard_coords = [{"lat": y, "lng": x} for x, y in line_standard.coords] if line_standard else []

    dist_shade = sum(G.get_edge_data(shadiest_nodes[i], shadiest_nodes[i + 1]).get('length', 0) for i in
                     range(len(shadiest_nodes) - 1))

    if len(shadiest_nodes) > 1:
        shadow_shade = sum(G.get_edge_data(shadiest_nodes[i], shadiest_nodes[i + 1]).get('shadow_ratio', 0) for i in
                           range(len(shadiest_nodes) - 1)) / (len(shadiest_nodes) - 1)
    else:
        shadow_shade = 0

    if len(standard_nodes) > 1:
        shadow_standard = sum(G.get_edge_data(standard_nodes[i], standard_nodes[i + 1]).get('shadow_ratio', 0) for i in
                              range(len(standard_nodes) - 1)) / (len(standard_nodes) - 1)
    else:
        shadow_standard = 0

    return {
        "shade_route": shade_coords,
        "standard_route": standard_coords,
        "stats": {
            "shade": {"dist": round(dist_shade), "shadow": round(shadow_shade * 100)},
            "standard": {"dist": round(dist_standard), "shadow": round(shadow_standard * 100)}
        }
    }


if __name__ == "__main__":
    import uvicorn

    print("Pre-loading all graphs into memory. Please wait...")
    hours_to_preload = [8, 10, 14, 16]
    for h in hours_to_preload:
        get_or_build_graph('2025-06-21', h)

    print("All graphs loaded! Server is ready.")
    uvicorn.run(app, host="0.0.0.0", port=8000)