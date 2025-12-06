import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import json
import time
from datetime import datetime
from collections import deque
import pandas as pd
import paho.mqtt.client as mqtt
import dash_bootstrap_components as dbc

# ===============================
# MQTT Configuration
# ===============================
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC_SUB = "sic7/sensor"
TOPIC_PUB = "sic7/control"
CLIENT_ID = f"dash_{int(time.time())}"
MQTT_USER = "foursome"
MQTT_PASS = "berempat"

# ===============================
# Global Data Storage
# ===============================
sensor_data = {
    "temp": 0.0,
    "hum": 0.0,
    "pot": 0,
    "status": "Menunggu...",
    "prediction": "N/A"
}

data_log = {
    "time": deque(),
    "temp": deque(),
    "hum": deque(),
    "pot": deque()
}

ml_stats = {
    "total_predictions": 0,
    "panas_count": 0,
    "hangat_count": 0,
    "dingin_count": 0,
    "last_prediction_time": None
}

mqtt_connected = False
collected_data = []
collection_active = False

# ===============================
# MQTT Callbacks
# ===============================
def on_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        client.subscribe(TOPIC_SUB)
        client.subscribe(TOPIC_PUB)
        print("✅ MQTT Connected")
        print(f"📡 Subscribed to: {TOPIC_SUB}, {TOPIC_PUB}")
    else:
        mqtt_connected = False
        print(f"❌ Connection Failed (rc={rc})")

def on_disconnect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    mqtt_connected = False
    if rc != 0:
        print(f"⚠️ Unexpected disconnect (rc={rc})")

def on_message(client, userdata, msg):
    global sensor_data, data_log, ml_stats, collection_active, collected_data
    try:
        payload = msg.payload.decode()
        
        # Handle sensor data
        if msg.topic == TOPIC_SUB:
            data = json.loads(payload)
            sensor_data.update(data)
            
            # Update data log
            current_time = datetime.now().strftime("%H:%M:%S")
            data_log["time"].append(current_time)
            data_log["temp"].append(data.get("temp", 0))
            data_log["hum"].append(data.get("hum", 0))
            data_log["pot"].append(data.get("pot", 0))
            
            print(f"📥 Sensor: temp={data.get('temp')}°C, hum={data.get('hum')}%, pot={data.get('pot')}")
        
        # Handle prediction/status
        elif msg.topic == TOPIC_PUB:
            if payload.startswith('status:'):
                prediction = payload.split(':')[1]
                sensor_data['prediction'] = prediction
                sensor_data['status'] = prediction
                
                if prediction in ["Panas", "Hangat", "Dingin"]:
                    ml_stats["total_predictions"] += 1
                    ml_stats["last_prediction_time"] = datetime.now().strftime("%H:%M:%S")
                    
                    if prediction == "Panas":
                        ml_stats["panas_count"] += 1
                    elif prediction == "Hangat":
                        ml_stats["hangat_count"] += 1
                    elif prediction == "Dingin":
                        ml_stats["dingin_count"] += 1
                
                print(f"🤖 Prediction: {prediction}")
        
        # Collect data if active
        if collection_active:
            collected_data.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "temp": sensor_data.get("temp", 0),
                "hum": sensor_data.get("hum", 0),
                "pot": sensor_data.get("pot", 0),
                "prediction": sensor_data.get("prediction", "N/A")
            })
        
    except Exception as e:
        print(f"❌ Error: {e}")

# ===============================
# Initialize MQTT
# ===============================
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID, clean_session=True, protocol=mqtt.MQTTv311)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message
mqtt_client.connect(BROKER, PORT, keepalive=60)
mqtt_client.loop_start()
print("🚀 MQTT Client Started")

# ===============================
# Dash App
# ===============================
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], suppress_callback_exceptions=True)
app.title = "SIC7 IoT Dashboard"

# Custom CSS for better layout
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                margin: 0;
                padding: 0;
                overflow: hidden;
                background-color: #060606;
            }
            .main-container {
                display: flex;
                height: 100vh;
                width: 100vw;
            }
            .sidebar {
                width: 280px;
                background: linear-gradient(135deg, #1a1d29 0%, #0f1117 100%);
                border-right: 2px solid #00d4ff;
                transition: all 0.3s ease;
                overflow-y: auto;
                position: relative;
            }
            .sidebar.collapsed {
                width: 70px;
            }
            .sidebar.collapsed .sidebar-content {
                display: none;
            }
            .content-area {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                background-color: #0a0e14;
                max-height: 100vh;
            }
            .toggle-btn {
                position: absolute;
                top: 10px;
                right: 10px;
                z-index: 1000;
                background: #00d4ff !important;
                border: none !important;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: all 0.3s;
            }
            .toggle-btn:hover {
                background: #00b8e6 !important;
                transform: scale(1.1);
            }
            .metric-card {
                background: linear-gradient(135deg, #1e2530 0%, #141921 100%);
                border: 1px solid #2d3748;
                border-radius: 15px;
                padding: 20px;
                height: 100%;
                transition: all 0.3s;
                box-shadow: 0 4px 20px rgba(0, 212, 255, 0.1);
            }
            .metric-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 8px 30px rgba(0, 212, 255, 0.2);
                border-color: #00d4ff;
            }
            .chart-card {
                background: linear-gradient(135deg, #1e2530 0%, #141921 100%);
                border: 1px solid #2d3748;
                border-radius: 15px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            }
            .control-btn {
                border-radius: 12px !important;
                font-weight: 600 !important;
                transition: all 0.3s !important;
                margin-bottom: 10px !important;
            }
            .control-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(0, 212, 255, 0.4) !important;
            }
            .sidebar-header {
                padding: 20px;
                text-align: center;
                border-bottom: 2px solid #00d4ff;
                margin-bottom: 20px;
            }
            .sidebar-header h2 {
                color: #00d4ff;
                font-weight: 700;
                margin: 0;
                text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
            }
            .status-badge {
                display: inline-block;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: 600;
                margin: 5px;
            }
            .metric-value {
                font-size: 2.5rem;
                font-weight: 700;
                margin: 10px 0;
                text-shadow: 0 0 20px currentColor;
            }
            .metric-label {
                font-size: 0.9rem;
                opacity: 0.7;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            /* Scrollbar styling */
            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            ::-webkit-scrollbar-track {
                background: #0a0e14;
            }
            ::-webkit-scrollbar-thumb {
                background: #00d4ff;
                border-radius: 4px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: #00b8e6;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Layout with sidebar
app.layout = html.Div([
    dcc.Interval(id='interval', interval=1000),
    dcc.Store(id='sidebar-state', data={'collapsed': False}),
    
    html.Div([
        # Sidebar
        html.Div([
            # Toggle button
            html.Button("☰", id="toggle-sidebar", className="toggle-btn"),
            
            # Sidebar content
            html.Div([
                html.Div([
                    html.H2("🤖 SIC7", style={'margin': '0'}),
                    html.P("IoT Dashboard", style={'margin': '5px 0 0 0', 'color': '#aaa', 'fontSize': '0.9rem'})
                ], className="sidebar-header"),
                
                html.Div([
                    # Connection Status
                    html.H6("📡 Status", style={'color': '#00d4ff', 'marginBottom': '15px', 'marginTop': '20px'}),
                    html.Div(id="sidebar-status"),
                    html.Div(id="sidebar-time", style={'fontSize': '0.85rem', 'color': '#888', 'marginTop': '10px'}),
                    
                    html.Hr(style={'borderColor': '#2d3748', 'margin': '20px 0'}),
                    
                    # ML Stats Summary
                    html.H6("🤖 ML Stats", style={'color': '#00d4ff', 'marginBottom': '15px'}),
                    html.Div(id="sidebar-ml-stats"),
                    
                    html.Hr(style={'borderColor': '#2d3748', 'margin': '20px 0'}),
                    
                    # Data Collection
                    html.H6("📊 Data Collection", style={'color': '#00d4ff', 'marginBottom': '15px'}),
                    dbc.Button("▶️ Start/Stop", id="btn-collect", color="primary", className="w-100 mb-2 control-btn"),
                    html.Div(id="collect-status", className="text-center mb-2", style={'fontSize': '0.85rem'}),
                    dbc.Button("💾 Download CSV", id="btn-download", color="info", className="w-100 control-btn"),
                    dcc.Download(id="download-csv"),
                    
                    html.Hr(style={'borderColor': '#2d3748', 'margin': '20px 0'}),
                    
                    # Actuator Controls
                    html.H6("🎛️ Controls", style={'color': '#00d4ff', 'marginBottom': '15px'}),
                    dbc.Button("🔴 RED", id="btn-red", color="danger", className="w-100 control-btn", size="sm"),
                    dbc.Button("🟡 YELLOW", id="btn-yellow", color="warning", className="w-100 control-btn", size="sm"),
                    dbc.Button("🟢 GREEN", id="btn-green", color="success", className="w-100 control-btn", size="sm"),
                    dbc.Button("🔔 BUZZER", id="btn-buzzer", color="secondary", className="w-100 control-btn", size="sm"),
                    
                    html.Hr(style={'borderColor': '#2d3748', 'margin': '20px 0'}),
                    
                    # Footer
                    html.Div([
                        html.P("Team Foursome", style={'margin': '0', 'fontWeight': '600', 'color': '#00d4ff'}),
                        html.P("© 2025 SIC7", style={'margin': '0', 'fontSize': '0.75rem', 'color': '#666'})
                    ], style={'textAlign': 'center', 'padding': '10px'})
                ], style={'padding': '0 20px 20px 20px'})
            ], className="sidebar-content")
        ], id="sidebar", className="sidebar"),
        
        # Main Content Area
        html.Div([
            # Header
            html.Div([
                html.H3("🌡️ Smart IoT Dashboard with ML Inference", 
                       style={'color': '#00d4ff', 'fontWeight': '700', 'marginBottom': '3px', 'fontSize': '1.5rem'}),
                html.P("Real-time Environmental Monitoring & Prediction", 
                      style={'color': '#888', 'fontSize': '0.85rem', 'marginBottom': '15px'})
            ]),
            
            # Top Metrics Row
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Div("🌡️", style={'fontSize': '2rem', 'marginBottom': '10px'}),
                        html.Div("Temperature", className="metric-label"),
                        html.Div(id="temp-metric", className="metric-value", style={'color': '#ff6b6b'}),
                        html.Div(id="temp-label", style={'fontSize': '0.85rem', 'color': '#aaa'})
                    ], className="metric-card")
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.Div("💧", style={'fontSize': '2rem', 'marginBottom': '10px'}),
                        html.Div("Humidity", className="metric-label"),
                        html.Div(id="hum-metric", className="metric-value", style={'color': '#4dabf7'}),
                        html.Div(id="hum-label", style={'fontSize': '0.85rem', 'color': '#aaa'})
                    ], className="metric-card")
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.Div("🤖", style={'fontSize': '2rem', 'marginBottom': '10px'}),
                        html.Div("ML Prediction", className="metric-label"),
                        html.Div(id="pred-metric", className="metric-value", style={'color': '#51cf66'}),
                        html.Div(id="pred-label", style={'fontSize': '0.85rem', 'color': '#aaa'})
                    ], className="metric-card")
                ], width=4),
            ], style={'marginBottom': '20px'}),
            
            # Charts Row
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H5("📈 Temperature & Humidity Trends", style={'color': '#00d4ff', 'marginBottom': '15px'}),
                        dcc.Graph(id="temp-hum-chart", config={'displayModeBar': False}, style={'height': '300px'})
                    ], className="chart-card")
                ], width=12),
            ]),
            
            # ML Analytics Row
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H5("🤖 ML Prediction Distribution", style={'color': '#00d4ff', 'marginBottom': '15px'}),
                        dcc.Graph(id="ml-pie-chart", config={'displayModeBar': False}, style={'height': '300px'})
                    ], className="chart-card")
                ], width=6),
                dbc.Col([
                    html.Div([
                        html.H5("📊 Prediction Statistics", style={'color': '#00d4ff', 'marginBottom': '15px'}),
                        html.Div(id="ml-stats-detail")
                    ], className="chart-card")
                ], width=6),
            ])
        ], className="content-area")
    ], className="main-container")
])

# ===============================
# Callbacks
# ===============================

# Sidebar toggle
@app.callback(
    Output("sidebar", "className"),
    Output("sidebar-state", "data"),
    Input("toggle-sidebar", "n_clicks"),
    State("sidebar-state", "data"),
    prevent_initial_call=True
)
def toggle_sidebar(n, state):
    if n:
        state['collapsed'] = not state['collapsed']
        return "sidebar collapsed" if state['collapsed'] else "sidebar", state
    return "sidebar", state

# Main dashboard update
@app.callback(
    [Output("sidebar-status", "children"),
     Output("sidebar-time", "children"),
     Output("sidebar-ml-stats", "children"),
     Output("temp-metric", "children"),
     Output("temp-label", "children"),
     Output("hum-metric", "children"),
     Output("hum-label", "children"),
     Output("pred-metric", "children"),
     Output("pred-label", "children"),
     Output("temp-hum-chart", "figure"),
     Output("ml-pie-chart", "figure"),
     Output("ml-stats-detail", "children"),
     Output("collect-status", "children")],
    Input("interval", "n_intervals")
)
def update_dashboard(n):
    # Sidebar status
    if mqtt_connected:
        sidebar_status = html.Div([
            html.Span("🟢 Connected", className="status-badge", 
                     style={'background': 'rgba(81, 207, 102, 0.2)', 'color': '#51cf66'})
        ])
    else:
        sidebar_status = html.Div([
            html.Span("🔴 Disconnected", className="status-badge",
                     style={'background': 'rgba(255, 107, 107, 0.2)', 'color': '#ff6b6b'})
        ])
    
    # Time
    sidebar_time = f"🕐 {datetime.now().strftime('%H:%M:%S')}"
    
    # Sidebar ML stats
    sidebar_ml = html.Div([
        html.Div([
            html.Span("Total: ", style={'color': '#888'}),
            html.Span(f"{ml_stats['total_predictions']}", style={'color': '#00d4ff', 'fontWeight': '700', 'fontSize': '1.2rem'})
        ], style={'marginBottom': '8px'}),
        html.Div([
            html.Span("🔥 ", style={'fontSize': '1rem'}),
            html.Span(f"Panas: {ml_stats['panas_count']}", style={'color': '#ff6b6b', 'fontSize': '0.9rem'})
        ], style={'marginBottom': '5px'}),
        html.Div([
            html.Span("🟡 ", style={'fontSize': '1rem'}),
            html.Span(f"Hangat: {ml_stats['hangat_count']}", style={'color': '#ffd43b', 'fontSize': '0.9rem'})
        ], style={'marginBottom': '5px'}),
        html.Div([
            html.Span("❄️ ", style={'fontSize': '1rem'}),
            html.Span(f"Dingin: {ml_stats['dingin_count']}", style={'color': '#4dabf7', 'fontSize': '0.9rem'})
        ])
    ])
    
    # Metrics
    temp = sensor_data.get("temp", 0)
    temp_text = f"{temp:.1f}°C"
    temp_label = "🔥 Hot" if temp > 30 else "❄️ Cool" if temp < 25 else "🌡️ Warm"
    
    hum = sensor_data.get("hum", 0)
    hum_text = f"{hum:.1f}%"
    hum_label = "💧 High" if hum > 70 else "🏜️ Low" if hum < 40 else "💦 Normal"
    
    prediction = sensor_data.get("prediction", "N/A")
    pred_icon = {"Panas": "🔥", "Hangat": "🟡", "Dingin": "❄️", "N/A": "⏳"}.get(prediction, "⏳")
    pred_label = f"{pred_icon} {ml_stats['total_predictions']} predictions"
    
    # Temp & Humidity Chart
    fig_temp_hum = go.Figure()
    if len(data_log["time"]) > 0:
        fig_temp_hum.add_trace(go.Scatter(
            x=list(data_log["time"]),
            y=list(data_log["temp"]),
            mode='lines+markers',
            name='Temperature (°C)',
            line=dict(color='#ff6b6b', width=3, shape='spline'),
            marker=dict(size=6),
            fill='tonexty',
            fillcolor='rgba(255, 107, 107, 0.1)'
        ))
        fig_temp_hum.add_trace(go.Scatter(
            x=list(data_log["time"]),
            y=list(data_log["hum"]),
            mode='lines+markers',
            name='Humidity (%)',
            line=dict(color='#4dabf7', width=3, shape='spline'),
            marker=dict(size=6),
            fill='tonexty',
            fillcolor='rgba(77, 171, 247, 0.1)'
        ))
    fig_temp_hum.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(20, 25, 33, 0.5)',
        height=300,
        margin=dict(l=40, r=20, t=10, b=40),
        hovermode='x unified',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor='#2d3748'),
        yaxis=dict(showgrid=True, gridcolor='#2d3748')
    )
    
    # ML Pie Chart
    fig_pie = go.Figure()
    if ml_stats["total_predictions"] > 0:
        fig_pie.add_trace(go.Pie(
            labels=['Panas', 'Hangat', 'Dingin'],
            values=[ml_stats['panas_count'], ml_stats['hangat_count'], ml_stats['dingin_count']],
            marker=dict(colors=['#ff6b6b', '#ffd43b', '#4dabf7']),
            hole=0.5,
            textposition='inside',
            textfont=dict(size=14, color='white')
        ))
    fig_pie.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=300,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.1)
    )
    
    # ML Stats Detail
    total = ml_stats["total_predictions"]
    if total > 0:
        panas_pct = (ml_stats['panas_count'] / total) * 100
        hangat_pct = (ml_stats['hangat_count'] / total) * 100
        dingin_pct = (ml_stats['dingin_count'] / total) * 100
        
        ml_detail = html.Div([
            html.Div([
                html.Div("🔥 Panas", style={'fontSize': '1.1rem', 'marginBottom': '5px'}),
                dbc.Progress(value=panas_pct, color="danger", className="mb-3", 
                           style={'height': '25px'}, label=f"{panas_pct:.1f}%")
            ], style={'marginBottom': '20px'}),
            html.Div([
                html.Div("🟡 Hangat", style={'fontSize': '1.1rem', 'marginBottom': '5px'}),
                dbc.Progress(value=hangat_pct, color="warning", className="mb-3",
                           style={'height': '25px'}, label=f"{hangat_pct:.1f}%")
            ], style={'marginBottom': '20px'}),
            html.Div([
                html.Div("❄️ Dingin", style={'fontSize': '1.1rem', 'marginBottom': '5px'}),
                dbc.Progress(value=dingin_pct, color="info", className="mb-3",
                           style={'height': '25px'}, label=f"{dingin_pct:.1f}%")
            ], style={'marginBottom': '20px'}),
            html.Hr(style={'borderColor': '#2d3748'}),
            html.Div([
                html.Strong("Last Prediction: ", style={'color': '#888'}),
                html.Span(ml_stats['last_prediction_time'] or "N/A", style={'color': '#00d4ff'})
            ])
        ])
    else:
        ml_detail = html.Div([
            html.P("⏳ No predictions yet...", style={'textAlign': 'center', 'color': '#888', 'marginTop': '80px'})
        ])
    
    # Collection status
    collect_text = f"📦 {len(collected_data)} samples"
    
    return (sidebar_status, sidebar_time, sidebar_ml,
            temp_text, temp_label, hum_text, hum_label,
            prediction, pred_label,
            fig_temp_hum, fig_pie, ml_detail, collect_text)

# LED/Buzzer Control Callbacks
@app.callback(Output("btn-red", "children"), Input("btn-red", "n_clicks"), prevent_initial_call=True)
def control_red(n):
    if n:
        mqtt_client.publish(TOPIC_PUB, "red:on" if n % 2 == 1 else "red:off")
        return "🔴 RED ON" if n % 2 == 1 else "🔴 RED OFF"
    return "🔴 RED LED"

@app.callback(Output("btn-yellow", "children"), Input("btn-yellow", "n_clicks"), prevent_initial_call=True)
def control_yellow(n):
    if n:
        mqtt_client.publish(TOPIC_PUB, "yellow:on" if n % 2 == 1 else "yellow:off")
        return "🟡 YELLOW ON" if n % 2 == 1 else "🟡 YELLOW OFF"
    return "🟡 YELLOW LED"

@app.callback(Output("btn-green", "children"), Input("btn-green", "n_clicks"), prevent_initial_call=True)
def control_green(n):
    if n:
        mqtt_client.publish(TOPIC_PUB, "green:on" if n % 2 == 1 else "green:off")
        return "🟢 GREEN ON" if n % 2 == 1 else "🟢 GREEN OFF"
    return "🟢 GREEN LED"

@app.callback(Output("btn-buzzer", "children"), Input("btn-buzzer", "n_clicks"), prevent_initial_call=True)
def control_buzzer(n):
    if n:
        mqtt_client.publish(TOPIC_PUB, "buzzer:on" if n % 2 == 1 else "buzzer:off")
        return "🔔 BUZZER ON" if n % 2 == 1 else "🔔 BUZZER OFF"
    return "🔔 BUZZER"

# Collection toggle
@app.callback(Output("btn-collect", "color"), Input("btn-collect", "n_clicks"), prevent_initial_call=True)
def toggle_collection(n):
    global collection_active
    if n:
        collection_active = not collection_active
        return "success" if collection_active else "primary"
    return "primary"

# CSV Download
@app.callback(Output("download-csv", "data"), Input("btn-download", "n_clicks"), prevent_initial_call=True)
def download_csv(n):
    if n and len(collected_data) > 0:
        df = pd.DataFrame(collected_data)
        return dcc.send_data_frame(df.to_csv, f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", index=False)

if __name__ == '__main__':
    print("🚀 Starting Dash IoT Dashboard...")
    print("📡 Dashboard URL: http://127.0.0.1:8050")
    app.run(debug=False, host='127.0.0.1', port=8050)
