from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import networkx as nx
from shapely.geometry import LineString
from fastapi.responses import FileResponse
import pickle
import os
import zipfile

# 1. יצירת התיקייה אם היא לא קיימת
if not os.path.exists('graphs'):
    os.makedirs('graphs')

# 2. חילוץ אוטומטי של קבצי ה-ZIP הקטנים
zip_files = ['graph_8.zip', 'graph_10.zip', 'graph_14.zip', 'graph_16.zip']
for zip_name in zip_files:
    if os.path.exists(zip_name):
        print(f"Extracting {zip_name}...")
        with zipfile.ZipFile(zip_name, 'r') as zip_ref:
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

class RouteRequest(BaseModel):
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    date_str: str  
    hour_val: int  

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
        print(f"Error: Graph file for {hour_val}:00 not found!")
        return nx.Graph()

@app.post("/calculate_route")
def calculate_route(request: RouteRequest):
    G = get_or_build_graph(request.date_str, request.hour_val)
    
    if not G.nodes:
        return {"shade_route": [], "standard_route": [], "stats": {"shade": {"dist": 0, "shadow": 0}, "standard": {"dist": 0, "shadow": 0}}}

    # מציאת הצמתים הקרובים ביותר להתחלה ולסיום
    start_node = min(G.nodes, key=lambda n: (n[1] - request.start_lat)**2 + (n[0] - request.start_lng)**2)
    end_node = min(G.nodes, key=lambda n: (n[1] - request.end_lat)**2 + (n[0] - request.end_lng)**2)

    # 1. חישוב המסלול הרגיל (לפי מרחק בלבד)
    standard_nodes = nx.shortest_path(G, source=start_node, target=end_node, weight='length')
    dist_standard = sum(G.get_edge_data(standard_nodes[i], standard_nodes[i+1]).get('length', 0) for i in range(len(standard_nodes)-1))

    # 2. חישוב המסלול המוצל המהיר (לפי משקל הצל שהגדרנו מראש)
    try:
        shadiest_nodes = nx.shortest_path(G, source=start_node, target=end_node, weight='weight')
        dist_shade = sum(G.get_edge_data(shadiest_nodes[i], shadiest_nodes[i+1]).get('length', 0) for i in range(len(shadiest_nodes)-1))
        
        # אם המסלול המוצל ארוך מדי (מעל 500 מטר תוספת), נשתמש ברגיל
        if dist_shade > dist_standard + 500:
            shadiest_nodes = standard_nodes
            dist_shade = dist_standard
    except nx.NetworkXNoPath:
        shadiest_nodes = standard_nodes
        dist_shade = dist_standard

    # בניית הקווים הגיאומטריים למפה
    line_shade = get_smooth_path(G, shadiest_nodes)
    line_standard = get_smooth_path(G, standard_nodes)

    shade_coords = [{"lat": y, "lng": x} for x, y in line_shade.coords] if line_shade else []
    standard_coords = [{"lat": y, "lng": x} for x, y in line_standard.coords] if line_standard else []

    # חישוב אחוזי הצל להצגה בסטטיסטיקות
    if len(shadiest_nodes) > 1:
        shadow_shade = sum(G.get_edge_data(shadiest_nodes[i], shadiest_nodes[i+1]).get('shadow_ratio', 0) for i in range(len(shadiest_nodes)-1)) / (len(shadiest_nodes)-1)
    else:
        shadow_shade = 0

    if len(standard_nodes) > 1:
        shadow_standard = sum(G.get_edge_data(standard_nodes[i], standard_nodes[i+1]).get('shadow_ratio', 0) for i in range(len(standard_nodes)-1)) / (len(standard_nodes)-1)
    else:
        shadow_standard = 0

    return {
        "shade_route": shade_coords,
        "standard_route": standard_coords,
        "stats": {
            "shade": {"dist": round(dist_shade), "shadow": round(shadow_shade * 100)},
            "standard": {"dist": round(dist_standard
