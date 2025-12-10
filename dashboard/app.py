import streamlit as st
import pandas as pd
import numpy as np
import joblib
import json
import time
import queue
import threading
from datetime import datetime
import plotly.graph_objs as go
import paho.mqtt.client as mqtt

# Optional auto-refresh
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False
    st_autorefresh = None

# ===============================
# Configuration
# ===============================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
TOPIC_SENSOR = "sic7/sensor"
TOPIC_CONTROL = "sic7/control"
MODEL_PATH = "model/models/model_random_forest.pkl"
CLIENT_ID = f"streamlit_dashboard_{int(time.time())}"
MQTT_USER = "foursome"
MQTT_PASS = "berempat"

# Global queue for MQTT messages
GLOBAL_MQ = queue.Queue()

# Global ML model and stats (accessible from MQTT thread)
GLOBAL_MODEL = None
GLOBAL_STATS = {"total": 0, "panas": 0, "hangat": 0, "dingin": 0}
GLOBAL_MQTT_CLIENT = None  # Global MQTT client for button controls

# ===============================
# Page Config
# ===============================
st.set_page_config(
    page_title="SIC7 IoT Dashboard",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better UI
st.markdown("""
<style>
    /* Main styling */
    .main {
        background: linear-gradient(135deg, #0a0e14 0%, #1a1d29 100%);
        padding-top: 0 !important;
    }
    
    /* Remove top padding */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
    }
    
    /* Remove emotion cache padding */
    div[data-testid="stVerticalBlock"] > div:has(div.stHeadingContainer) {
        padding-top: 0 !important;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        text-shadow: 0 0 20px currentColor;
    }
    
    /* Cards */
    .stAlert {
        background: linear-gradient(135deg, #1e2530 0%, #141921 100%);
        border: 1px solid #2d3748;
        border-radius: 15px;
        padding: 20px;
    }
    
    /* Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.3s;
        margin: 5px 0;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0, 212, 255, 0.4);
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #00d4ff !important;
        text-shadow: 0 0 10px rgba(0, 212, 255, 0.3);
        margin-top: 0 !important;
    }
    
    /* Hide default streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Scrollbar */
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
</style>
""", unsafe_allow_html=True)

# ===============================
# Session State Init
# ===============================
if "msg_queue" not in st.session_state:
    st.session_state.msg_queue = GLOBAL_MQ
if "logs" not in st.session_state:
    st.session_state.logs = []
if "last" not in st.session_state:
    st.session_state.last = None
if "mqtt_thread_started" not in st.session_state:
    st.session_state.mqtt_thread_started = False
if "ml_model" not in st.session_state:
    st.session_state.ml_model = None
if "mqtt_client" not in st.session_state:
    st.session_state.mqtt_client = None
if "ml_stats" not in st.session_state:
    st.session_state.ml_stats = {
        "total": 0,
        "panas": 0,
        "hangat": 0,
        "dingin": 0
    }

# ===============================
# Load ML Model
# ===============================
@st.cache_resource
def load_ml_model():
    global GLOBAL_MODEL
    try:
        import os
        if not os.path.exists(MODEL_PATH):
            st.error(f"❌ Model not found: {MODEL_PATH}")
            return None
        model = joblib.load(MODEL_PATH)
        GLOBAL_MODEL = model  # Store in global variable
        st.success(f"✅ Model loaded: {MODEL_PATH}")
        return model
    except Exception as e:
        st.error(f"❌ Failed to load model: {e}")
        return None

if st.session_state.ml_model is None:
    st.session_state.ml_model = load_ml_model()

# Ensure GLOBAL_MODEL is loaded for predictions
if GLOBAL_MODEL is None and st.session_state.ml_model is not None:
    GLOBAL_MODEL = st.session_state.ml_model

# ===============================
# MQTT Functions
# ===============================
def predict_and_publish(client, temp, hum):
    """Predict label and publish to MQTT - uses GLOBAL variables"""
    global GLOBAL_MODEL, GLOBAL_STATS
    
    # Use global model (accessible from thread)
    if GLOBAL_MODEL is None:
        return "N/A"
    
    try:
        X = np.array([[float(temp), float(hum)]])
        prediction = GLOBAL_MODEL.predict(X)[0]
        
        # Update global stats (thread-safe for this use case)
        GLOBAL_STATS["total"] += 1
        if prediction == "Panas":
            GLOBAL_STATS["panas"] += 1
        elif prediction == "Hangat":
            GLOBAL_STATS["hangat"] += 1
        elif prediction == "Dingin":
            GLOBAL_STATS["dingin"] += 1
        
        # Debug: print updated stats
        print(f"📊 GLOBAL_STATS updated: {GLOBAL_STATS}")
        
        # Publish status to ESP32
        status_msg = f"status:{prediction}"
        client.publish(TOPIC_CONTROL, status_msg)
        print(f"✅ Predicted: {prediction} (Temp={temp}°C, Hum={hum}%)")
        
        return prediction
    except Exception as e:
        print(f"❌ Prediction error: {e}")
        return "ERROR"

def on_connect(client, userdata, flags, rc, properties=None):
    """MQTT connect callback"""
    if rc == 0:
        client.subscribe(TOPIC_SENSOR)
        GLOBAL_MQ.put({"_type": "status", "connected": True, "ts": time.time()})
    else:
        GLOBAL_MQ.put({"_type": "status", "connected": False, "ts": time.time()})

def on_message(client, userdata, msg):
    """MQTT message callback"""
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        
        temp = float(data.get('temp', 0))
        hum = float(data.get('hum', 0))
        
        print(f"📥 Received sensor data: temp={temp}°C, hum={hum}%")
        
        # Predict and publish (integrated inference)
        prediction = predict_and_publish(client, temp, hum)
        
        print(f"🤖 Prediction result: {prediction}")
        
        row = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "temp": temp,
            "hum": hum,
            "pred": prediction
        }
        
        # Send updated stats through queue
        GLOBAL_MQ.put({
            "_type": "sensor", 
            "data": row, 
            "stats": GLOBAL_STATS.copy(),
            "ts": time.time()
        })
        
    except Exception as e:
        print(f"❌ Message processing error: {e}")
        import traceback
        traceback.print_exc()

def on_disconnect(client, userdata, flags, rc, properties=None):
    """MQTT disconnect callback"""
    if rc != 0:
        GLOBAL_MQ.put({"_type": "status", "connected": False, "ts": time.time()})

def start_mqtt_thread():
    """Start MQTT client thread"""
    global GLOBAL_MQTT_CLIENT
    
    def worker():
        global GLOBAL_MQTT_CLIENT
        client = mqtt.Client(
            client_id=CLIENT_ID,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        
        # Store client globally for manual controls
        GLOBAL_MQTT_CLIENT = client
        st.session_state.mqtt_client = client
        
        while True:
            try:
                client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
                client.loop_forever()
            except Exception as e:
                GLOBAL_MQ.put({"_type": "error", "msg": str(e), "ts": time.time()})
                time.sleep(5)
    
    if not st.session_state.mqtt_thread_started:
        t = threading.Thread(target=worker, daemon=True, name="mqtt_worker")
        t.start()
        st.session_state.mqtt_thread_started = True
        time.sleep(0.1)

# Start MQTT thread
start_mqtt_thread()

# ===============================
# Process Queue
# ===============================
def process_queue():
    """Process incoming MQTT messages"""
    global GLOBAL_STATS
    
    q = st.session_state.msg_queue
    updated = False
    
    while not q.empty():
        item = q.get()
        ttype = item.get("_type")
        
        if ttype == "status":
            st.session_state.mqtt_connected = item.get("connected", False)
            updated = True
        elif ttype == "sensor":
            row = item.get("data", {})
            st.session_state.last = row
            st.session_state.logs.append(row)
            
            # Update stats from queue message
            if "stats" in item:
                st.session_state.ml_stats = item["stats"]
                updated = True
            
            # Keep logs bounded
            if len(st.session_state.logs) > 1000:
                st.session_state.logs = st.session_state.logs[-1000:]
            updated = True
        elif ttype == "error":
            st.error(f"⚠️ {item.get('msg')}")
            updated = True
    
    return updated

# Process queue
updated = process_queue()

# Auto-refresh every 2 seconds
if HAS_AUTOREFRESH and st_autorefresh:
    st_autorefresh(interval=2000, limit=None, key="autorefresh")

# ===============================
# UI Layout
# ===============================

# Header
st.markdown("""
<div style='text-align: center; padding: 5px 0 10px 0;'>
    <h1>🌡️ SIC7 IoT Dashboard with ML Inference</h1>
    <p style='color: #888; font-size: 1.1rem;'>Real-time Environmental Monitoring & Prediction</p>
</div>
""", unsafe_allow_html=True)

# Status bar
col_status = st.columns([1, 2, 1, 1])
with col_status[0]:
    connected = getattr(st.session_state, "mqtt_connected", False)
    if connected:
        st.success("🟢 MQTT Connected")
    else:
        st.error("🔴 MQTT Disconnected")

with col_status[1]:
    st.info(f"📡 Broker: {MQTT_BROKER}:{MQTT_PORT} | Topic: {TOPIC_SENSOR}")

with col_status[2]:
    st.info(f"🕐 {datetime.now().strftime('%H:%M:%S')}")

with col_status[3]:
    # Manual refresh button
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

st.markdown("---")

# Main dashboard - 2 columns
left_col, right_col = st.columns([2, 3])

# ===============================
# LEFT COLUMN - Metrics
# ===============================
with left_col:
    st.subheader("📊 Current Readings")
    
    # Show update status
    total_logs = len(st.session_state.logs)
    if total_logs > 0:
        st.caption(f"📊 Total data points: {total_logs} | 🔄 Auto-updates every 2s")
    
    if st.session_state.last:
        last = st.session_state.last
        
        # Metrics in 2 columns
        m1, m2 = st.columns(2)
        with m1:
            temp = last.get('temp', 0)
            st.metric("🌡️ Temperature", f"{temp:.1f}°C", 
                     delta=None if len(st.session_state.logs) < 2 else f"{temp - st.session_state.logs[-2].get('temp', temp):.1f}°C")
        with m2:
            hum = last.get('hum', 0)
            st.metric("💧 Humidity", f"{hum:.1f}%",
                     delta=None if len(st.session_state.logs) < 2 else f"{hum - st.session_state.logs[-2].get('hum', hum):.1f}%")
        
        # Prediction
        pred = last.get('pred', 'N/A')
        pred_emoji = {"Panas": "🔥", "Hangat": "🟡", "Dingin": "❄️"}.get(pred, "⏳")
        pred_color = {"Panas": "#ff6b6b", "Hangat": "#ffd43b", "Dingin": "#4dabf7"}.get(pred, "#888")
        
        st.markdown(f"""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #1e2530 0%, #141921 100%); 
                    border: 2px solid {pred_color}; border-radius: 15px; margin: 10px 0;'>
            <h2 style='margin: 0; color: {pred_color};'>{pred_emoji} {pred}</h2>
            <p style='color: #888; margin: 5px 0 0 0;'>ML Prediction</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.caption(f"🕐 Last update: {last.get('ts')}")
    else:
        st.info("⏳ Waiting for sensor data...")
    
    st.markdown("---")
    
    # ML Statistics
    st.subheader("🤖 ML Statistics")
    stats = st.session_state.ml_stats
    
    # Debug info
    st.caption(f"🔍 Debug: Stats = {stats}")
    
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.metric("Total", stats["total"])
    with s2:
        st.metric("Panas", stats["panas"])
    with s3:
        st.metric("Hangat", stats["hangat"])
    with s4:
        st.metric("Dingin", stats["dingin"])

# ===============================
# RIGHT COLUMN - Charts & Logs
# ===============================
with right_col:
    st.subheader("📈 Live Monitoring")
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📊 Time Series", "🥧 Distribution", "📋 Logs"])
    
    with tab1:
        df_plot = pd.DataFrame(st.session_state.logs[-200:])
        
        if not df_plot.empty and {"temp", "hum", "ts"}.issubset(df_plot.columns):
            # Temperature & Humidity Chart
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df_plot["ts"],
                y=df_plot["temp"],
                mode="lines+markers",
                name="Temperature (°C)",
                line=dict(color='#ff6b6b', width=3),
                marker=dict(size=6),
                fill='tonexty',
                fillcolor='rgba(255, 107, 107, 0.1)'
            ))
            
            fig.add_trace(go.Scatter(
                x=df_plot["ts"],
                y=df_plot["hum"],
                mode="lines+markers",
                name="Humidity (%)",
                line=dict(color='#4dabf7', width=3),
                marker=dict(size=6),
                yaxis="y2",
                fill='tonexty',
                fillcolor='rgba(77, 171, 247, 0.1)'
            ))
            
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(20, 25, 33, 0.5)',
                height=400,
                hovermode='x unified',
                yaxis=dict(title="Temperature (°C)", showgrid=True, gridcolor='#2d3748'),
                yaxis2=dict(title="Humidity (%)", overlaying="y", side="right", showgrid=False),
                xaxis=dict(showgrid=True, gridcolor='#2d3748'),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("⏳ Waiting for data to plot...")
    
    with tab2:
        stats = st.session_state.ml_stats
        
        # Debug info
        st.caption(f"🔍 Debug: Distribution stats = {stats}")
        
        if stats["total"] > 0:
            fig_pie = go.Figure()
            
            fig_pie.add_trace(go.Pie(
                labels=['Panas', 'Hangat', 'Dingin'],
                values=[stats['panas'], stats['hangat'], stats['dingin']],
                marker=dict(colors=['#ff6b6b', '#ffd43b', '#4dabf7']),
                hole=0.5,
                textposition='inside',
                textfont=dict(size=16, color='white')
            ))
            
            fig_pie.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
            )
            
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # Statistics bars
            st.markdown("### Prediction Breakdown")
            
            if stats["total"] > 0:
                panas_pct = (stats['panas'] / stats['total']) * 100
                hangat_pct = (stats['hangat'] / stats['total']) * 100
                dingin_pct = (stats['dingin'] / stats['total']) * 100
                
                st.progress(panas_pct / 100, text=f"🔥 Panas: {panas_pct:.1f}% ({stats['panas']})")
                st.progress(hangat_pct / 100, text=f"🟡 Hangat: {hangat_pct:.1f}% ({stats['hangat']})")
                st.progress(dingin_pct / 100, text=f"❄️ Dingin: {dingin_pct:.1f}% ({stats['dingin']})")
        else:
            st.info("⏳ No predictions yet...")
    
    with tab3:
        if st.session_state.logs:
            df_logs = pd.DataFrame(st.session_state.logs[::-1][:100])
            st.dataframe(df_logs, use_container_width=True, height=400)
        else:
            st.info("⏳ No logs yet...")
    
    # Download button below charts
    st.markdown("---")
    if st.session_state.logs:
        df_dl = pd.DataFrame(st.session_state.logs)
        csv = df_dl.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Log CSV",
            data=csv,
            file_name=f"iot_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("⏳ No data to download yet...")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p><strong>Team Foursome</strong> | SIC7 Final Project | © 2025</p>
</div>
""", unsafe_allow_html=True)

# Process queue again after UI render
process_queue()
