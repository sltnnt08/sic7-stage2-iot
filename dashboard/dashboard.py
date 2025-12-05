import json
import threading
import time
from datetime import datetime
from collections import deque
import pandas as pd
import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from paho.mqtt import client as mqtt
import plotly.graph_objs as go

# ===============================
# Konfigurasi MQTT (sesuai ESP32)
# ===============================
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC_SUB = "sic7/sensor"
TOPIC_PUB = "sic7/control"
CLIENT_ID = "mqttx_22adfc93"
MQTT_USER = "foursome"
MQTT_PASS = "berempat"

# ===============================
# Global data state
# ===============================
sensor_data = {"temp": 0, "hum": 0, "pot": 0, "status": "Menunggu...", "prediction": "N/A", "model": "N/A"}
MAX_DATA_POINTS = 100  # Tingkatkan untuk visualisasi lebih baik

# Gunakan deque untuk efisiensi memory
data_log = {
    "time": deque(maxlen=MAX_DATA_POINTS),
    "temp": deque(maxlen=MAX_DATA_POINTS),
    "hum": deque(maxlen=MAX_DATA_POINTS),
    "pot": deque(maxlen=MAX_DATA_POINTS)
}

# Tracking ML predictions
ml_stats = {
    "total_predictions": 0,
    "panas_count": 0,
    "normal_count": 0,
    "dingin_count": 0,
    "last_prediction_time": None
}

# Data collection for CSV export
collected_data = []
collection_active = False

# State tracking untuk toggle buttons
button_states = {
    "red": False,
    "yellow": False,
    "green": False,
    "buzzer": False
}

# Connection status
connection_status = {"mqtt": False}

# ===============================
# MQTT setup
# ===============================
def on_connect(client, userdata, flags, rc):
    global connection_status
    if rc == 0:
        print("✅ MQTT connected successfully")
        connection_status["mqtt"] = True
        client.subscribe(TOPIC_SUB)
    else:
        print(f"❌ MQTT connection failed (rc={rc})")
        connection_status["mqtt"] = False

def on_disconnect(client, userdata, rc):
    global connection_status
    connection_status["mqtt"] = False
    if rc != 0:
        print(f"⚠️ MQTT unexpected disconnect (rc={rc})")

def on_message(client, userdata, msg):
    global sensor_data, ml_stats
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        
        # Update sensor data
        sensor_data.update(data)
        
        # Track ML predictions if available
        if "prediction" in data or "status" in data:
            prediction = data.get("prediction", data.get("status", "N/A"))
            if prediction in ["Panas", "Normal", "Dingin"]:
                ml_stats["total_predictions"] += 1
                ml_stats["last_prediction_time"] = datetime.now().strftime("%H:%M:%S")
                
                if prediction == "Panas":
                    ml_stats["panas_count"] += 1
                elif prediction == "Normal":
                    ml_stats["normal_count"] += 1
                elif prediction == "Dingin":
                    ml_stats["dingin_count"] += 1
                
                sensor_data["prediction"] = prediction
        
        print(f"📡 MQTT Data: Temp={data.get('temp')}°C, Hum={data.get('hum')}%, Prediction={sensor_data.get('prediction', 'N/A')}")
    except Exception as e:
        print(f"❌ Error MQTT: {e}")

# Buat MQTT client dengan keepalive lebih lama untuk stabilitas
mqtt_client = mqtt.Client(client_id=CLIENT_ID, clean_session=True, protocol=mqtt.MQTTv311)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message

# Set keepalive dan reconnect settings
mqtt_client.reconnect_delay_set(min_delay=1, max_delay=120)

try:
    mqtt_client.connect(BROKER, PORT, keepalive=60)
    threading.Thread(target=mqtt_client.loop_forever, daemon=True).start()
    print("🚀 MQTT thread started")
except Exception as e:
    print(f"❌ MQTT connection error: {e}")
    connection_status["mqtt"] = False

# ===============================
# DASH APP
# ===============================
app = dash.Dash(
    __name__, 
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css"
    ],
    meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}]
)

app.title = "SIC7 IoT Control Center"

# Modern Layout with Sidebar
app.layout = html.Div([
    # Sidebar
    html.Div([
        html.Div([
            html.H3([
                html.I(className="bi bi-cpu-fill me-2"),
                "SIC7"
            ], className="text-white mb-0"),
            html.Small("IoT Control Center", className="text-white-50 d-block")
        ], className="p-3 border-bottom border-secondary"),
        
        # Data Collection Section
        html.Div([
            html.H6("DATA COLLECTION", className="text-white-50 px-3 mb-2 mt-3 small fw-bold"),
            html.Div([
                dbc.Button([
                    html.I(className="bi bi-play-circle me-2", id="collect-icon"),
                    html.Span("Start Collecting", id="collect-text")
                ], id="btn-collect", color="success", className="w-100 mb-2"),
                dbc.Button([
                    html.I(className="bi bi-download me-2"),
                    "Export CSV"
                ], id="btn-export", color="info", className="w-100 mb-2", disabled=True),
                html.Small([
                    html.I(className="bi bi-database me-2"),
                    html.Span(id="collect-count", children="0 samples")
                ], className="d-block text-white-50 px-2 mb-2"),
            ], className="px-3"),
            
            html.H6("SYSTEM STATUS", className="text-white-50 px-3 mb-2 mt-4 small fw-bold"),
            html.Div([
                html.Small([
                    html.I(className="bi bi-circle-fill text-success me-2", id="mqtt-indicator", style={"fontSize": "8px"}),
                    html.Span(id="sidebar-mqtt-status", children="MQTT Connected")
                ], className="d-block text-white-50 px-3 mb-2"),
                html.Small([
                    html.I(className="bi bi-clock me-2"),
                    html.Span(id="sidebar-time", children=datetime.now().strftime("%H:%M:%S"))
                ], className="d-block text-white-50 px-3"),
            ]),
        ], className="flex-grow-1"),
        
        # Footer
        html.Div([
            html.Small("Team Foursome © 2025", className="text-white-50 d-block text-center")
        ], className="p-3 border-top border-secondary mt-auto")
        
    ], style={
        "position": "fixed",
        "top": 0,
        "left": 0,
        "bottom": 0,
        "width": "260px",
        "backgroundColor": "#1a1d20",
        "zIndex": 1000,
        "display": "flex",
        "flexDirection": "column"
    }),
    
    # Main Content
    html.Div([
        # Top Bar
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.H4([
                        html.I(className="bi bi-house-door me-2"),
                        "Dashboard Overview"
                    ], className="mb-0 text-light")
                ], width=12)
            ])
        ], className="bg-dark p-3 mb-3 rounded shadow-sm border border-secondary"),
        
        # Stats Cards Row
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.I(className="bi bi-thermometer-half text-danger", 
                                      style={"fontSize": "3rem", "opacity": "0.7"})
                            ], width=4, className="text-center"),
                            dbc.Col([
                                html.Small("Temperature", className="text-light d-block mb-1"),
                                html.H3(id="temp-value-big", className="mb-0 fw-bold text-light"),
                                html.Small(id="temp-indicator-small", className="text-muted")
                            ], width=8)
                        ])
                    ])
                ], className="bg-dark border border-secondary shadow-sm h-100")
            ], lg=3, md=6, className="mb-3"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.I(className="bi bi-droplet-fill text-primary", 
                                      style={"fontSize": "3rem", "opacity": "0.7"})
                            ], width=4, className="text-center"),
                            dbc.Col([
                                html.Small("Humidity", className="text-light d-block mb-1"),
                                html.H3(id="hum-value-big", className="mb-0 fw-bold text-light"),
                                html.Small(id="hum-indicator-small", className="text-muted")
                            ], width=8)
                        ])
                    ])
                ], className="bg-dark border border-secondary shadow-sm h-100")
            ], lg=3, md=6, className="mb-3"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.I(className="bi bi-robot text-success", 
                                      style={"fontSize": "3rem", "opacity": "0.7"})
                            ], width=4, className="text-center"),
                            dbc.Col([
                                html.Small("ML Prediction", className="text-light d-block mb-1"),
                                html.H3(id="ml-pred-small", className="mb-0 fw-bold text-light"),
                                html.Small(id="ml-count", className="text-muted")
                            ], width=8)
                        ])
                    ])
                ], className="bg-dark border border-secondary shadow-sm h-100")
            ], lg=3, md=6, className="mb-3"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.I(className="bi bi-sliders text-warning", 
                                      style={"fontSize": "3rem", "opacity": "0.7"})
                            ], width=4, className="text-center"),
                            dbc.Col([
                                html.Small("Potentiometer", className="text-light d-block mb-1"),
                                html.H3(id="pot-value-big", className="mb-0 fw-bold text-light"),
                                dbc.Progress(id="pot-progress-small", value=0, max=4095, 
                                           className="mt-2", style={"height": "6px"}, color="warning")
                            ], width=8)
                        ])
                    ])
                ], className="bg-dark border border-secondary shadow-sm h-100")
            ], lg=3, md=6, className="mb-3"),
        ]),
        
        # ML Prediction Hero Card
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.Small("CURRENT CONDITION", className="text-muted d-block mb-2 fw-bold"),
                                    html.H1(id="ml-prediction", className="display-3 fw-bold mb-0",
                                           style={"letterSpacing": "2px"}),
                                    html.Div(id="ml-prediction-icon", className="mt-3")
                                ], className="text-center p-3")
                            ], lg=5, className="border-end"),
                            dbc.Col([
                                html.Div([
                                    html.Small("PREDICTION STATISTICS", className="text-muted d-block mb-3 fw-bold"),
                                    dcc.Graph(id="prediction-pie", config={'displayModeBar': False},
                                             style={"height": "250px"})
                                ])
                            ], lg=3),
                            dbc.Col([
                                html.Div([
                                    html.Small("MODEL PERFORMANCE", className="text-muted d-block mb-3 fw-bold"),
                                    html.Div(id="ml-confidence", className="mt-3"),
                                    html.Hr(className="my-3"),
                                    html.Div([
                                        html.Small([
                                            html.I(className="bi bi-clock me-2"),
                                            html.Span(id="last-update-time", children="Last update: N/A")
                                        ], className="text-muted d-block mb-2"),
                                        html.Small([
                                            html.I(className="bi bi-cpu me-2"),
                                            html.Span(id="model-info", children="Model: Best")
                                        ], className="text-muted d-block")
                                    ])
                                ])
                            ], lg=4)
                        ])
                    ], className="p-4")
                ], className="bg-dark border border-info shadow mb-3", style={"color": "white"})
            ])
        ]),
        
        # Charts Row
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-graph-up me-2"),
                        "Real-time Sensor Data"
                    ], className="bg-dark text-light border-secondary fw-bold"),
                    dbc.CardBody([
                        dcc.Graph(id="temp-hum-graph", config={'displayModeBar': False})
                    ], className="p-2")
                ], className="bg-dark border border-secondary shadow-sm mb-3")
            ], lg=8),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-activity me-2"),
                        "Potentiometer"
                    ], className="bg-dark text-light border-secondary fw-bold"),
                    dbc.CardBody([
                        dcc.Graph(id="pot-graph", config={'displayModeBar': False})
                    ], className="p-2")
                ], className="bg-dark border border-secondary shadow-sm mb-3")
            ], lg=4),
        ]),
        
        # Control Panel
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-toggles me-2"),
                        "Actuator Control"
                    ], className="bg-dark text-light border-secondary fw-bold", id="actuators"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.Small("LED INDICATORS", className="text-muted d-block mb-3 fw-bold"),
                                    dbc.ButtonGroup([
                                        dbc.Button([
                                            html.I(className="bi bi-lightbulb-fill me-2"),
                                            "RED"
                                        ], id="btn-red", color="danger", className="px-4 py-3"),
                                        dbc.Button([
                                            html.I(className="bi bi-lightbulb-fill me-2"),
                                            "YELLOW"
                                        ], id="btn-yellow", color="warning", className="px-4 py-3"),
                                        dbc.Button([
                                            html.I(className="bi bi-lightbulb-fill me-2"),
                                            "GREEN"
                                        ], id="btn-green", color="success", className="px-4 py-3"),
                                    ], size="lg", className="w-100 mb-3"),
                                ]),
                                html.Div([
                                    html.Small("AUDIO ALERT", className="text-muted d-block mb-3 fw-bold"),
                                    dbc.Button([
                                        html.I(className="bi bi-volume-up-fill me-2"),
                                        "BUZZER CONTROL"
                                    ], id="btn-buzzer", color="info", size="lg", className="w-100 px-4 py-3"),
                                ])
                            ], lg=6),
                            dbc.Col([
                                html.Small("COMMAND LOG", className="text-muted d-block mb-3 fw-bold"),
                                html.Div([
                                    dbc.Alert([
                                        html.I(className="bi bi-info-circle me-2"),
                                        html.Span(id="command-status", children="Ready to send commands...")
                                    ], color="light", className="mb-2"),
                                    html.Div([
                                        html.Small("ACTUATOR STATUS", className="text-muted d-block mb-2"),
                                        html.Div([
                                            dbc.Badge([
                                                html.I(className="bi bi-circle-fill me-1", style={"fontSize": "8px"}),
                                                "RED"
                                            ], id="status-red", color="secondary", className="me-2 mb-2"),
                                            dbc.Badge([
                                                html.I(className="bi bi-circle-fill me-1", style={"fontSize": "8px"}),
                                                "YELLOW"
                                            ], id="status-yellow", color="secondary", className="me-2 mb-2"),
                                            dbc.Badge([
                                                html.I(className="bi bi-circle-fill me-1", style={"fontSize": "8px"}),
                                                "GREEN"
                                            ], id="status-green", color="secondary", className="me-2 mb-2"),
                                            dbc.Badge([
                                                html.I(className="bi bi-circle-fill me-1", style={"fontSize": "8px"}),
                                                "BUZZER"
                                            ], id="status-buzzer", color="secondary", className="mb-2"),
                                        ])
                                    ])
                                ], className="p-3 bg-light rounded")
                            ], lg=6)
                        ])
                    ], className="p-4")
                ], className="bg-dark border border-secondary shadow-sm mb-3")
            ])
        ]),
        
        # Debug Panel (Collapsible)
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        dbc.Button([
                            html.I(className="bi bi-bug me-2"),
                            "Debug Panel"
                        ], id="debug-toggle", color="link", className="text-decoration-none text-light fw-bold p-0")
                    ], className="bg-dark border-secondary"),
                    dbc.Collapse([
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.Small("MQTT STATUS", className="text-muted d-block mb-2 fw-bold"),
                                    html.Pre(id="debug-mqtt", className="bg-secondary text-light p-3 rounded small border border-dark",
                                            style={"maxHeight": "150px", "overflowY": "auto"})
                                ], lg=4),
                                dbc.Col([
                                    html.Small("SENSOR DATA", className="text-muted d-block mb-2 fw-bold"),
                                    html.Pre(id="debug-sensor", className="bg-secondary text-light p-3 rounded small border border-dark",
                                            style={"maxHeight": "150px", "overflowY": "auto"})
                                ], lg=4),
                                dbc.Col([
                                    html.Small("ML STATS", className="text-muted d-block mb-2 fw-bold"),
                                    html.Pre(id="debug-ml", className="bg-secondary text-light p-3 rounded small border border-dark",
                                            style={"maxHeight": "150px", "overflowY": "auto"})
                                ], lg=4)
                            ])
                        ])
                    ], id="debug-collapse", is_open=False)
                ], className="bg-dark border border-secondary shadow-sm mb-3")
            ])
        ]),
        
        # Update interval
        dcc.Interval(id="interval", interval=1000, n_intervals=0),
        
    ], style={"marginLeft": "260px", "padding": "20px", "backgroundColor": "#1a1d20", "minHeight": "100vh"})
    
], style={"fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"})

# ===============================
# Callbacks
# ===============================

# Toggle debug panel
@app.callback(
    Output("debug-collapse", "is_open"),
    [Input("debug-toggle", "n_clicks")],
    [State("debug-collapse", "is_open")],
    prevent_initial_call=True
)
def toggle_debug(n, is_open):
    return not is_open

# Update sidebar time and status
@app.callback(
    [Output("sidebar-time", "children"),
     Output("sidebar-mqtt-status", "children"),
     Output("sidebar-mqtt-status", "className")],
    [Input("interval", "n_intervals")]
)
def update_sidebar(n):
    current_time = datetime.now().strftime("%H:%M:%S")
    if connection_status["mqtt"]:
        return current_time, "MQTT Connected", "d-block text-success px-3 mb-2"
    else:
        return current_time, "MQTT Disconnected", "d-block text-danger px-3 mb-2"

# Update debug panels
@app.callback(
    [Output("debug-mqtt", "children"),
     Output("debug-sensor", "children"),
     Output("debug-ml", "children")],
    [Input("interval", "n_intervals")]
)
def update_debug(n):
    mqtt_debug = f"""BROKER: {BROKER}:{PORT}
CLIENT_ID: {CLIENT_ID}
CONNECTED: {connection_status['mqtt']}
SUB_TOPIC: {TOPIC_SUB}
PUB_TOPIC: {TOPIC_PUB}"""
    
    sensor_debug = json.dumps(sensor_data, indent=2)
    
    ml_debug = json.dumps(ml_stats, indent=2)
    
    return mqtt_debug, sensor_debug, ml_debug

# Update sensor values, ML prediction, and charts
@app.callback(
    [Output("temp-value-big", "children"),
     Output("hum-value-big", "children"),
     Output("pot-value-big", "children"),
     Output("pot-progress-small", "value"),
     Output("temp-indicator-small", "children"),
     Output("hum-indicator-small", "children"),
     Output("ml-pred-small", "children"),
     Output("ml-count", "children"),
     Output("ml-prediction", "children"),
     Output("ml-prediction-icon", "children"),
     Output("ml-confidence", "children"),
     Output("prediction-pie", "figure"),
     Output("last-update-time", "children"),
     Output("model-info", "children"),
     Output("temp-hum-graph", "figure"),
     Output("pot-graph", "figure"),
     Output("status-red", "color"),
     Output("status-yellow", "color"),
     Output("status-green", "color"),
     Output("status-buzzer", "color")],
    [Input("interval", "n_intervals")]
)
def update_all_data(n):
    global data_log, sensor_data, ml_stats, button_states
    
    # Get sensor values
    t = sensor_data.get("temp", 0)
    h = sensor_data.get("hum", 0)
    p = sensor_data.get("pot", 0)
    prediction = sensor_data.get("prediction", "Menunggu...")
    model_name = sensor_data.get("model", "Best Model")
    
    # Update data log
    current_time = datetime.now().strftime("%H:%M:%S")
    data_log["time"].append(current_time)
    data_log["temp"].append(t)
    data_log["hum"].append(h)
    data_log["pot"].append(p)
    
    # Temperature & Humidity indicators (small)
    temp_small = f"{t:.1f}°C" if t > 0 else "No data"
    hum_small = f"{h:.1f}%" if h > 0 else "No data"
    
    # ML prediction small
    ml_pred_text = prediction
    ml_count_text = f"{ml_stats['total_predictions']} predictions"
    
    # ML Prediction colors
    prediction_colors = {
        "Panas": "text-danger",
        "Normal": "text-success",
        "Dingin": "text-info",
        "Menunggu...": "text-secondary"
    }
    
    # ML Prediction Icon (white for gradient background)
    ml_icons = {
        "Panas": html.Div([
            html.I(className="bi bi-thermometer-sun display-1 text-white mb-2"),
            html.P("Kondisi Panas Terdeteksi", className="text-white-50")
        ]),
        "Normal": html.Div([
            html.I(className="bi bi-check-circle-fill display-1 text-white mb-2"),
            html.P("Kondisi Normal", className="text-white-50")
        ]),
        "Dingin": html.Div([
            html.I(className="bi bi-thermometer-snow display-1 text-white mb-2"),
            html.P("Kondisi Dingin Terdeteksi", className="text-white-50")
        ]),
        "Menunggu...": html.Div([
            html.I(className="bi bi-hourglass-split display-1 text-white mb-2"),
            html.P("Menunggu Data Sensor...", className="text-white-50")
        ])
    }
    ml_icon = ml_icons.get(prediction, ml_icons["Menunggu..."])
    
    # ML Confidence / Stats (white text for gradient)
    total = ml_stats["total_predictions"]
    if total > 0:
        ml_confidence_display = html.Div([
            html.Div([
                html.H3(f"{total}", className="text-white mb-0 fw-bold"),
                html.Small("Total Predictions", className="text-white-50 d-block")
            ], className="mb-3"),
            html.Div([
                html.Div([
                    html.Span("🔥", className="me-2"),
                    html.Span(f"Panas: {ml_stats['panas_count']}", className="text-white")
                ], className="mb-1"),
                html.Div([
                    html.Span("✅", className="me-2"),
                    html.Span(f"Normal: {ml_stats['normal_count']}", className="text-white")
                ], className="mb-1"),
                html.Div([
                    html.Span("❄️", className="me-2"),
                    html.Span(f"Dingin: {ml_stats['dingin_count']}", className="text-white")
                ])
            ])
        ])
    else:
        ml_confidence_display = html.P("Belum ada prediksi", className="text-white-50 fst-italic")
    
    # Pie chart for ML predictions distribution (white text)
    if total > 0:
        pie_fig = go.Figure(data=[go.Pie(
            labels=['Panas', 'Normal', 'Dingin'],
            values=[ml_stats['panas_count'], ml_stats['normal_count'], ml_stats['dingin_count']],
            hole=.5,
            marker=dict(colors=['#ff6b6b', '#51cf66', '#4dabf7']),
            textfont=dict(size=16, color='white', family='Arial Black')
        )])
        pie_fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=True,
            legend=dict(
                font=dict(color='white', size=12),
                orientation='v',
                x=1, y=0.5
            ),
            height=250
        )
    else:
        pie_fig = go.Figure()
        pie_fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            annotations=[{
                'text': 'No Data',
                'showarrow': False,
                'font': {'size': 20, 'color': 'white'}
            }],
            height=250
        )
    
    # Temperature & Humidity Graph (Enhanced with modern style)
    temp_hum_fig = go.Figure()
    temp_hum_fig.add_trace(go.Scatter(
        x=list(data_log["time"]),
        y=list(data_log["temp"]),
        mode='lines+markers',
        name='Temperature (°C)',
        line=dict(color='#ff6b6b', width=3, shape='spline'),
        marker=dict(size=6, symbol='circle'),
        fill='tonexty',
        fillcolor='rgba(255, 107, 107, 0.1)'
    ))
    temp_hum_fig.add_trace(go.Scatter(
        x=list(data_log["time"]),
        y=list(data_log["hum"]),
        mode='lines+markers',
        name='Humidity (%)',
        line=dict(color='#4dabf7', width=3, shape='spline'),
        marker=dict(size=6, symbol='diamond'),
        fill='tonexty',
        fillcolor='rgba(77, 171, 247, 0.1)'
    ))
    temp_hum_fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#1a1d20',
        plot_bgcolor='#1a1d20',
        margin=dict(l=40, r=20, t=20, b=40),
        height=350,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified',
        xaxis=dict(showgrid=True, gridcolor='#303030'),
        yaxis=dict(showgrid=True, gridcolor='#303030'),
        font=dict(family="Arial", size=12, color="#f8f9fa")
    )
    
    # Potentiometer Graph (Modern gauge style)
    pot_fig = go.Figure()
    pot_fig.add_trace(go.Scatter(
        x=list(data_log["time"]),
        y=list(data_log["pot"]),
        mode='lines',
        fill='tozeroy',
        name='Potentiometer',
        line=dict(color='#ffd43b', width=3, shape='spline'),
        fillcolor='rgba(255, 212, 59, 0.3)'
    ))
    pot_fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#1a1d20',
        plot_bgcolor='#1a1d20',
        margin=dict(l=40, r=20, t=20, b=40),
        height=350,
        showlegend=False,
        hovermode='x',
        xaxis=dict(showgrid=True, gridcolor='#303030'),
        yaxis=dict(showgrid=True, gridcolor='#303030', range=[0, 4095]),
        font=dict(family="Arial", size=12, color="#f8f9fa")
    )
    
    last_update = f"Last update: {ml_stats['last_prediction_time']}" if ml_stats['last_prediction_time'] else "Last update: N/A"
    model_info_text = f"Model: {model_name}"
    
    # Button states for status badges
    red_color = "danger" if button_states["red"] else "secondary"
    yellow_color = "warning" if button_states["yellow"] else "secondary"
    green_color = "success" if button_states["green"] else "secondary"
    buzzer_color = "info" if button_states["buzzer"] else "secondary"
    
    return (
        f"{t:.1f}°C",
        f"{h:.1f}%",
        f"{p}",
        p,
        temp_small,
        hum_small,
        ml_pred_text,
        ml_count_text,
        prediction,
        ml_icon,
        ml_confidence_display,
        pie_fig,
        last_update,
        model_info_text,
        temp_hum_fig,
        pot_fig,
        red_color,
        yellow_color,
        green_color,
        buzzer_color
    )

# Control buttons callback
@app.callback(
    [Output("command-status", "children"),
     Output("btn-red", "color"),
     Output("btn-yellow", "color"),
     Output("btn-green", "color"),
     Output("btn-buzzer", "color")],
    [Input("btn-red", "n_clicks"),
     Input("btn-yellow", "n_clicks"),
     Input("btn-green", "n_clicks"),
     Input("btn-buzzer", "n_clicks")],
    prevent_initial_call=True
)
def control_buttons(red, yellow, green, buzzer):
    global button_states
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return "Ready to send commands...", "danger", "warning", "success", "info"
    
    btn_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    button_map = {
        "btn-red": "red",
        "btn-yellow": "yellow",
        "btn-green": "green",
        "btn-buzzer": "buzzer"
    }
    
    if btn_id in button_map:
        button_name = button_map[btn_id]
        button_states[button_name] = not button_states[button_name]
        state = "on" if button_states[button_name] else "off"
        msg = f"{button_name}:{state}"
        
        try:
            mqtt_client.publish(TOPIC_PUB, msg)
            status_text = f"✅ {button_name.upper()} → {state.upper()} | {datetime.now().strftime('%H:%M:%S')}"
        except Exception as e:
            status_text = f"❌ Failed: {e}"
    else:
        status_text = "Ready to send commands..."
    
    # Button colors (outline when off, filled when on)
    red_color = "danger" if button_states["red"] else "outline-danger"
    yellow_color = "warning" if button_states["yellow"] else "outline-warning"
    green_color = "success" if button_states["green"] else "outline-success"
    buzzer_color = "info" if button_states["buzzer"] else "outline-info"
    
    return status_text, red_color, yellow_color, green_color, buzzer_color

# Collection and export callbacks
@app.callback(
    [Output("btn-collect", "color"),
     Output("btn-collect", "children"),
     Output("btn-export", "disabled"),
     Output("collect-count", "children")],
    [Input("btn-collect", "n_clicks")],
    [State("btn-collect", "color")],
    prevent_initial_call=True
)
def toggle_collection(n_clicks, current_color):
    global collection_active, collected_data
    
    if current_color == "success":
        # Start collecting
        collection_active = True
        collected_data = []  # Reset data
        return "danger", [
            html.I(className="bi bi-stop-circle me-2", id="collect-icon"),
            html.Span("Stop Collecting", id="collect-text")
        ], True, f"{len(collected_data)} samples"
    else:
        # Stop collecting
        collection_active = False
        return "success", [
            html.I(className="bi bi-play-circle me-2", id="collect-icon"),
            html.Span("Start Collecting", id="collect-text")
        ], False, f"{len(collected_data)} samples"

# Update collected data count
@app.callback(
    Output("collect-count", "children", allow_duplicate=True),
    [Input("interval", "n_intervals")],
    prevent_initial_call=True
)
def update_collected_count(n):
    global collection_active, collected_data, sensor_data
    
    if collection_active and sensor_data.get("temp", 0) > 0:
        # Collect current sensor data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        collected_data.append({
            "timestamp": timestamp,
            "temp": sensor_data.get("temp", 0),
            "hum": sensor_data.get("hum", 0),
            "pot": sensor_data.get("pot", 0),
            "prediction": sensor_data.get("prediction", "N/A")
        })
    
    return f"{len(collected_data)} samples"

# Export CSV callback
@app.callback(
    Output("btn-export", "n_clicks"),
    [Input("btn-export", "n_clicks")],
    prevent_initial_call=True
)
def export_csv(n_clicks):
    global collected_data
    
    if len(collected_data) > 0:
        # Create dataframe
        df = pd.DataFrame(collected_data)
        
        # Save to CSV with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"model/dataset/collected_data_{timestamp}.csv"
        df.to_csv(filename, index=False)
        
        print(f"✅ Data exported to {filename} ({len(collected_data)} samples)")
    
    return None

# ===============================
# Jalankan server web
# ===============================
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
