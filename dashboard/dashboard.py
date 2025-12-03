import json
import threading
import time
from datetime import datetime
from collections import deque
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
CLIENT_ID = "SIC7_Dash_Client"
MQTT_USER = "foursome"
MQTT_PASS = "berempat"

# ===============================
# Global data state
# ===============================
sensor_data = {"temp": 0, "hum": 0, "pot": 0, "status": "Idle"}
MAX_DATA_POINTS = 50  # Batasi data points untuk performa

# Gunakan deque untuk efisiensi memory
data_log = {
    "time": deque(maxlen=MAX_DATA_POINTS),
    "temp": deque(maxlen=MAX_DATA_POINTS),
    "hum": deque(maxlen=MAX_DATA_POINTS),
    "pot": deque(maxlen=MAX_DATA_POINTS)
}

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
    global sensor_data
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        sensor_data.update(data)
        print(f"📡 MQTT Data: Temp={data.get('temp')}°C, Hum={data.get('hum')}%, Status={data.get('status')}")
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
    external_stylesheets=[dbc.themes.CYBORG],
    meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}]
)

app.title = "SIC7 IoT Dashboard - Team Foursome"

# Header dengan animasi gradient
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H2([
                    html.I(className="bi bi-thermometer-half me-2"),
                    "Foursome IoT Monitoring Dashboard"
                ], className="text-center mb-2 fw-bold"),
                html.P("Team Foursome - Real-time Environmental Monitoring", 
                       className="text-center text-muted mb-0"),
            ], className="p-3 mb-4 bg-dark rounded border border-info")
        ])
    ]),
    
    # Connection Status Bar
    dbc.Row([
        dbc.Col([
            dbc.Alert([
                html.I(className="bi bi-wifi me-2"),
                html.Span(id="mqtt-status", children="MQTT: Connecting...")
            ], id="connection-alert", color="info", className="mb-3 text-center")
        ])
    ]),
    
    # Sensor Cards Row
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-thermometer-half me-2"),
                    "Temperature"
                ], className="bg-danger text-white fw-bold"),
                dbc.CardBody([
                    html.H2(id="temp-value", className="display-4 text-danger mb-0"),
                    html.P("°Celsius", className="text-muted mb-2"),
                    html.Div(id="temp-indicator", className="mt-2")
                ])
            ], className="shadow-lg h-100 border-danger")
        ], xs=12, sm=6, lg=3, className="mb-3"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-droplet-fill me-2"),
                    "Humidity"
                ], className="bg-primary text-white fw-bold"),
                dbc.CardBody([
                    html.H2(id="hum-value", className="display-4 text-primary mb-0"),
                    html.P("% RH", className="text-muted mb-2"),
                    html.Div(id="hum-indicator", className="mt-2")
                ])
            ], className="shadow-lg h-100 border-primary")
        ], xs=12, sm=6, lg=3, className="mb-3"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-sliders me-2"),
                    "Potentiometer"
                ], className="bg-success text-white fw-bold"),
                dbc.CardBody([
                    html.H2(id="pot-value", className="display-4 text-success mb-0"),
                    html.P("ADC Value", className="text-muted mb-2"),
                    dbc.Progress(id="pot-progress", value=0, max=4095, 
                                className="mt-2", style={"height": "10px"})
                ])
            ], className="shadow-lg h-100 border-success")
        ], xs=12, sm=6, lg=3, className="mb-3"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-info-circle-fill me-2"),
                    "System Status"
                ], className="bg-warning text-dark fw-bold"),
                dbc.CardBody([
                    html.H4(id="status-value", className="mb-2 fw-bold"),
                    html.P(id="status-time", className="text-muted small mb-0"),
                    html.Div(id="status-icon", className="mt-2")
                ])
            ], className="shadow-lg h-100 border-warning")
        ], xs=12, sm=6, lg=3, className="mb-3"),
    ]),
    
    # Control Panel
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-toggles me-2"),
                    "LED & Buzzer Control Panel"
                ], className="bg-secondary text-white fw-bold"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Button([
                                html.I(className="bi bi-lightbulb-fill me-2"),
                                "RED LED"
                            ], id="btn-red", color="danger", size="lg", 
                               className="w-100 mb-2 shadow", outline=True)
                        ], xs=6, md=3),
                        dbc.Col([
                            dbc.Button([
                                html.I(className="bi bi-lightbulb-fill me-2"),
                                "YELLOW LED"
                            ], id="btn-yellow", color="warning", size="lg", 
                               className="w-100 mb-2 shadow", outline=True)
                        ], xs=6, md=3),
                        dbc.Col([
                            dbc.Button([
                                html.I(className="bi bi-lightbulb-fill me-2"),
                                "GREEN LED"
                            ], id="btn-green", color="success", size="lg", 
                               className="w-100 mb-2 shadow", outline=True)
                        ], xs=6, md=3),
                        dbc.Col([
                            dbc.Button([
                                html.I(className="bi bi-volume-up-fill me-2"),
                                "BUZZER"
                            ], id="btn-buzzer", color="info", size="lg", 
                               className="w-100 mb-2 shadow", outline=True)
                        ], xs=6, md=3),
                    ], className="g-2"),
                    html.Hr(),
                    dbc.Alert(id="command-status", color="light", 
                             className="mb-0 text-center small",
                             children="Ready to send commands...")
                ])
            ], className="shadow-lg border-secondary mb-4")
        ])
    ]),
    
    # Charts Row
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-graph-up me-2"),
                    "Temperature & Humidity Trends"
                ], className="bg-dark text-white fw-bold"),
                dbc.CardBody([
                    dcc.Graph(id="temp-hum-graph", config={'displayModeBar': False})
                ])
            ], className="shadow-lg border-info mb-3")
        ], lg=8),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-activity me-2"),
                    "Potentiometer Activity"
                ], className="bg-dark text-white fw-bold"),
                dbc.CardBody([
                    dcc.Graph(id="pot-graph", config={'displayModeBar': False})
                ])
            ], className="shadow-lg border-success mb-3")
        ], lg=4),
    ]),
    
    # Update interval
    dcc.Interval(id="interval", interval=1000, n_intervals=0),  # Update setiap 1 detik
    
    # Footer
    dbc.Row([
        dbc.Col([
            html.Hr(),
            html.P([
                "© 2025 Team Foursome | SIC7 Final Project | ",
                html.I(className="bi bi-github me-1"),
                "Real-time IoT Dashboard"
            ], className="text-center text-muted small")
        ])
    ])
    
], fluid=True, className="p-4 bg-dark")

# ===============================
# Callbacks
# ===============================

# Update connection status
# Update connection status
@app.callback(
    [Output("mqtt-status", "children"),
     Output("connection-alert", "color")],
    [Input("interval", "n_intervals")]
)
def update_connection_status(n):
    mqtt_text = "MQTT: ✅ Connected" if connection_status["mqtt"] else "MQTT: ❌ Disconnected"
    color = "success" if connection_status["mqtt"] else "danger"
    
    return mqtt_text, color

# Update sensor values and charts
@app.callback(
    [Output("temp-value", "children"),
     Output("hum-value", "children"),
     Output("pot-value", "children"),
     Output("pot-progress", "value"),
     Output("status-value", "children"),
     Output("status-time", "children"),
     Output("temp-indicator", "children"),
     Output("hum-indicator", "children"),
     Output("status-icon", "children"),
     Output("temp-hum-graph", "figure"),
     Output("pot-graph", "figure")],
    [Input("interval", "n_intervals")]
)
def update_sensor_data(n):
    global data_log, sensor_data
    
    # Get sensor values
    t = sensor_data.get("temp", 0)
    h = sensor_data.get("hum", 0)
    p = sensor_data.get("pot", 0)
    s = sensor_data.get("status", "Idle")
    
    # Update data log
    current_time = datetime.now().strftime("%H:%M:%S")
    data_log["time"].append(current_time)
    data_log["temp"].append(t)
    data_log["hum"].append(h)
    data_log["pot"].append(p)
    
    # Temperature indicator
    if t > 30:
        temp_badge = dbc.Badge("🔥 Hot", color="danger", className="fs-6")
    elif t >= 25:
        temp_badge = dbc.Badge("🌡️ Warm", color="warning", className="fs-6")
    else:
        temp_badge = dbc.Badge("❄️ Cool", color="info", className="fs-6")
    
    # Humidity indicator
    if h > 70:
        hum_badge = dbc.Badge("💧 High", color="primary", className="fs-6")
    elif h >= 40:
        hum_badge = dbc.Badge("💦 Normal", color="success", className="fs-6")
    else:
        hum_badge = dbc.Badge("🏜️ Low", color="warning", className="fs-6")
    
    # Status icon
    status_icons = {
        "Panas": html.Span([html.I(className="bi bi-fire fs-1 text-danger")]),
        "Hangat": html.Span([html.I(className="bi bi-sun-fill fs-1 text-warning")]),
        "Dingin": html.Span([html.I(className="bi bi-snow fs-1 text-info")]),
        "Idle": html.Span([html.I(className="bi bi-hourglass-split fs-1 text-secondary")])
    }
    status_icon = status_icons.get(s, status_icons["Idle"])
    
    # Temperature & Humidity Graph
    temp_hum_fig = go.Figure()
    temp_hum_fig.add_trace(go.Scatter(
        x=list(data_log["time"]),
        y=list(data_log["temp"]),
        mode='lines+markers',
        name='Temperature (°C)',
        line=dict(color='#dc3545', width=3),
        marker=dict(size=6)
    ))
    temp_hum_fig.add_trace(go.Scatter(
        x=list(data_log["time"]),
        y=list(data_log["hum"]),
        mode='lines+markers',
        name='Humidity (%)',
        line=dict(color='#0d6efd', width=3),
        marker=dict(size=6)
    ))
    temp_hum_fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.3)',
        margin=dict(l=40, r=20, t=40, b=40),
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode='x unified'
    )
    
    # Potentiometer Graph (Gauge style)
    pot_fig = go.Figure()
    pot_fig.add_trace(go.Scatter(
        x=list(data_log["time"]),
        y=list(data_log["pot"]),
        mode='lines',
        fill='tozeroy',
        name='Potentiometer',
        line=dict(color='#198754', width=2),
        fillcolor='rgba(25, 135, 84, 0.3)'
    ))
    pot_fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.3)',
        margin=dict(l=40, r=20, t=40, b=40),
        height=300,
        showlegend=False,
        hovermode='x'
    )
    pot_fig.update_yaxes(range=[0, 4095])
    
    return (
        f"{t:.1f}",
        f"{h:.1f}",
        f"{p}",
        p,
        s,
        f"Updated: {current_time}",
        temp_badge,
        hum_badge,
        status_icon,
        temp_hum_fig,
        pot_fig
    )

# Control buttons callback
@app.callback(
    [Output("command-status", "children"),
     Output("command-status", "color"),
     Output("btn-red", "outline"),
     Output("btn-yellow", "outline"),
     Output("btn-green", "outline"),
     Output("btn-buzzer", "outline")],
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
        return "Ready to send commands...", "light", True, True, True, True
    
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
            status_text = f"✅ Command sent: {button_name.upper()} → {state.upper()}"
            status_color = "success"
        except Exception as e:
            status_text = f"❌ Failed to send command: {e}"
            status_color = "danger"
    else:
        status_text = "Ready to send commands..."
        status_color = "light"
    
    # Update button outline states (False = filled, True = outline)
    return (
        status_text,
        status_color,
        not button_states["red"],
        not button_states["yellow"],
        not button_states["green"],
        not button_states["buzzer"]
    )

# ===============================
# Jalankan server web
# ===============================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
