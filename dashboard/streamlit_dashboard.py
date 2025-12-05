import streamlit as st
import json
import time
import threading
from datetime import datetime
from collections import deque
import pandas as pd
import paho.mqtt.client as mqtt
import plotly.graph_objs as go
import plotly.express as px

# ===============================
# Page Configuration
# ===============================
st.set_page_config(
    page_title="SIC7 IoT Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===============================
# Custom CSS
# ===============================
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Metric cards */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1a1d20;
    }
    
    /* Headers */
    h1 {
        color: #00d4ff;
        font-weight: 700;
        padding-bottom: 1rem;
        border-bottom: 2px solid #00d4ff;
    }
    
    h2, h3 {
        color: #ffffff;
    }
    
    /* Cards with gradient border */
    .stAlert {
        background-color: #1e2530;
        border-left: 4px solid #00d4ff;
    }
    
    /* Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 212, 255, 0.4);
    }
    
    /* Download button special styling */
    .stDownloadButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #1e2530;
        border-radius: 10px;
        padding: 10px 20px;
        color: #ffffff;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #1e2530;
        border-radius: 10px;
        font-weight: 600;
    }
    
    /* Progress bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
</style>
""", unsafe_allow_html=True)

# ===============================
# MQTT Configuration
# ===============================
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC_SUB = "sic7/sensor"
TOPIC_PUB = "sic7/control"
CLIENT_ID = f"streamlit_{int(time.time())}"
MQTT_USER = "foursome"
MQTT_PASS = "berempat"

# ===============================
# Initialize Session State
# ===============================
if 'sensor_data' not in st.session_state:
    st.session_state.sensor_data = {
        "temp": 0.0,
        "hum": 0.0,
        "pot": 0,
        "status": "Menunggu...",
        "prediction": "N/A",
        "model": "N/A"
    }

if 'data_log' not in st.session_state:
    st.session_state.data_log = {
        "time": deque(maxlen=100),
        "temp": deque(maxlen=100),
        "hum": deque(maxlen=100),
        "pot": deque(maxlen=100)
    }

if 'ml_stats' not in st.session_state:
    st.session_state.ml_stats = {
        "total_predictions": 0,
        "panas_count": 0,
        "normal_count": 0,
        "dingin_count": 0,
        "last_prediction_time": None
    }

if 'collected_data' not in st.session_state:
    st.session_state.collected_data = []

if 'collection_active' not in st.session_state:
    st.session_state.collection_active = False

if 'connection_status' not in st.session_state:
    st.session_state.connection_status = {"mqtt": False}

if 'button_states' not in st.session_state:
    st.session_state.button_states = {
        "red": False,
        "yellow": False,
        "green": False,
        "buzzer": False
    }

if 'mqtt_client' not in st.session_state:
    st.session_state.mqtt_client = None

# ===============================
# Global variables for thread-safe MQTT communication
# ===============================
mqtt_connected = False
latest_sensor_data = {
    "temp": 0.0,
    "hum": 0.0,
    "pot": 0,
    "status": "Menunggu...",
    "prediction": "N/A",
    "model": "N/A"
}

# ===============================
# MQTT Callbacks
# ===============================
def on_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        client.subscribe(TOPIC_SUB)
        print("✅ MQTT Connected")
    else:
        mqtt_connected = False
        print(f"❌ MQTT Connection Failed (rc={rc})")

def on_disconnect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    mqtt_connected = False
    if rc != 0:
        print(f"⚠️ Unexpected disconnect (rc={rc})")

def on_message(client, userdata, msg):
    global latest_sensor_data
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        
        # Update global sensor data
        latest_sensor_data.update(data)
        
    except Exception as e:
        print(f"❌ Error parsing message: {e}")

# ===============================
# Initialize MQTT Client
# ===============================
def init_mqtt():
    if st.session_state.mqtt_client is None:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID, clean_session=True, protocol=mqtt.MQTTv311)
            client.username_pw_set(MQTT_USER, MQTT_PASS)
            client.on_connect = on_connect
            client.on_disconnect = on_disconnect
            client.on_message = on_message
            client.connect(BROKER, PORT, keepalive=60)
            
            # Start loop in background thread
            client.loop_start()
            st.session_state.mqtt_client = client
            print("🚀 MQTT Client Started")
        except Exception as e:
            print(f"❌ MQTT Init Error: {e}")

# Initialize MQTT
init_mqtt()

# ===============================
# Sync global data to session state
# ===============================
def sync_mqtt_data():
    """Sync global MQTT data to session state"""
    global mqtt_connected, latest_sensor_data
    
    # Update connection status
    st.session_state.connection_status["mqtt"] = mqtt_connected
    
    # Update sensor data if new data available
    if latest_sensor_data != st.session_state.sensor_data:
        # Update sensor data
        st.session_state.sensor_data.update(latest_sensor_data)
        
        # Update data log
        current_time = datetime.now().strftime("%H:%M:%S")
        st.session_state.data_log["time"].append(current_time)
        st.session_state.data_log["temp"].append(latest_sensor_data.get("temp", 0))
        st.session_state.data_log["hum"].append(latest_sensor_data.get("hum", 0))
        st.session_state.data_log["pot"].append(latest_sensor_data.get("pot", 0))
        
        # Track ML predictions
        if "prediction" in latest_sensor_data or "status" in latest_sensor_data:
            prediction = latest_sensor_data.get("prediction", latest_sensor_data.get("status", "N/A"))
            if prediction in ["Panas", "Normal", "Dingin"]:
                st.session_state.ml_stats["total_predictions"] += 1
                st.session_state.ml_stats["last_prediction_time"] = current_time
                
                if prediction == "Panas":
                    st.session_state.ml_stats["panas_count"] += 1
                elif prediction == "Normal":
                    st.session_state.ml_stats["normal_count"] += 1
                elif prediction == "Dingin":
                    st.session_state.ml_stats["dingin_count"] += 1
        
        # Collect data if active
        if st.session_state.collection_active:
            st.session_state.collected_data.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "temp": latest_sensor_data.get("temp", 0),
                "hum": latest_sensor_data.get("hum", 0),
                "pot": latest_sensor_data.get("pot", 0),
                "prediction": latest_sensor_data.get("prediction", "N/A")
            })

# Sync data before rendering
sync_mqtt_data()

# ===============================
# Sidebar
# ===============================
with st.sidebar:
    st.markdown("# 🤖 SIC7")
    st.markdown("### IoT Control Center")
    st.markdown("---")
    
    # Connection Status
    st.markdown("### 📡 System Status")
    if st.session_state.connection_status["mqtt"]:
        st.success("🟢 MQTT Connected")
    else:
        st.error("🔴 MQTT Disconnected")
    
    st.info(f"🕐 {datetime.now().strftime('%H:%M:%S')}")
    
    st.markdown("---")
    
    # Data Collection
    st.markdown("### 📊 Data Collection")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Start" if not st.session_state.collection_active else "⏸️ Stop", 
                    type="primary" if not st.session_state.collection_active else "secondary",
                    use_container_width=True):
            st.session_state.collection_active = not st.session_state.collection_active
            if not st.session_state.collection_active and len(st.session_state.collected_data) > 0:
                st.success(f"✅ Collected {len(st.session_state.collected_data)} samples")
    
    with col2:
        if len(st.session_state.collected_data) > 0:
            df_export = pd.DataFrame(st.session_state.collected_data)
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="💾 CSV",
                data=csv,
                file_name=f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    st.caption(f"📦 {len(st.session_state.collected_data)} samples")
    
    if st.button("🗑️ Clear Data", use_container_width=True):
        st.session_state.collected_data = []
        st.rerun()
    
    st.markdown("---")
    
    # Footer
    st.markdown("#### Team Foursome")
    st.caption("© 2025 SIC7 Final Project")

# ===============================
# Main Content
# ===============================

# Header
st.markdown("# 🌡️ Smart IoT Dashboard with ML Inference")
st.markdown("### Real-time Environmental Monitoring & Prediction")

# Top Metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    temp = st.session_state.sensor_data.get("temp", 0)
    st.metric(
        label="🌡️ Temperature",
        value=f"{temp:.1f}°C",
        delta=f"{'🔥 Hot' if temp > 30 else '❄️ Cool' if temp < 25 else '🌡️ Warm'}"
    )

with col2:
    hum = st.session_state.sensor_data.get("hum", 0)
    st.metric(
        label="💧 Humidity",
        value=f"{hum:.1f}%",
        delta=f"{'💧 High' if hum > 70 else '🏜️ Low' if hum < 40 else '💦 Normal'}"
    )

with col3:
    prediction = st.session_state.sensor_data.get("prediction", "N/A")
    icon_map = {"Panas": "🔥", "Normal": "✅", "Dingin": "❄️", "N/A": "⏳"}
    st.metric(
        label="🤖 ML Prediction",
        value=prediction,
        delta=f"{icon_map.get(prediction, '⏳')} {st.session_state.ml_stats['total_predictions']} total"
    )

with col4:
    pot = st.session_state.sensor_data.get("pot", 0)
    st.metric(
        label="🎚️ Potentiometer",
        value=f"{pot}",
        delta=f"{(pot/4095)*100:.0f}%"
    )

st.markdown("---")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📈 Dashboard", "🎛️ Control Panel", "📊 ML Analytics", "🐛 Debug"])

with tab1:
    # Prediction Hero Card
    st.markdown("### 🤖 Current Condition")
    prediction = st.session_state.sensor_data.get("prediction", "Menunggu...")
    
    pred_col1, pred_col2, pred_col3 = st.columns([2, 1, 2])
    
    with pred_col1:
        if prediction == "Panas":
            st.error(f"# 🔥 {prediction}")
            st.caption("Kondisi Panas Terdeteksi")
        elif prediction == "Normal":
            st.success(f"# ✅ {prediction}")
            st.caption("Kondisi Optimal")
        elif prediction == "Dingin":
            st.info(f"# ❄️ {prediction}")
            st.caption("Kondisi Dingin Terdeteksi")
        else:
            st.warning(f"# ⏳ {prediction}")
            st.caption("Menunggu Data Sensor...")
    
    with pred_col2:
        # ML Stats
        total = st.session_state.ml_stats["total_predictions"]
        if total > 0:
            st.metric("Total Predictions", total)
            st.caption(f"🔥 Panas: {st.session_state.ml_stats['panas_count']}")
            st.caption(f"✅ Normal: {st.session_state.ml_stats['normal_count']}")
            st.caption(f"❄️ Dingin: {st.session_state.ml_stats['dingin_count']}")
    
    with pred_col3:
        # Pie Chart
        if total > 0:
            pie_data = pd.DataFrame({
                'Label': ['Panas', 'Normal', 'Dingin'],
                'Count': [
                    st.session_state.ml_stats['panas_count'],
                    st.session_state.ml_stats['normal_count'],
                    st.session_state.ml_stats['dingin_count']
                ]
            })
            fig_pie = px.pie(
                pie_data,
                values='Count',
                names='Label',
                color='Label',
                color_discrete_map={'Panas': '#ff6b6b', 'Normal': '#51cf66', 'Dingin': '#4dabf7'},
                hole=0.4
            )
            fig_pie.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=250,
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=True,
                legend=dict(font=dict(size=10))
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    
    st.markdown("---")
    
    # Charts
    chart_col1, chart_col2 = st.columns([2, 1])
    
    with chart_col1:
        st.markdown("### 📈 Temperature & Humidity Trends")
        if len(st.session_state.data_log["time"]) > 0:
            fig_temp_hum = go.Figure()
            
            fig_temp_hum.add_trace(go.Scatter(
                x=list(st.session_state.data_log["time"]),
                y=list(st.session_state.data_log["temp"]),
                mode='lines+markers',
                name='Temperature (°C)',
                line=dict(color='#ff6b6b', width=3, shape='spline'),
                marker=dict(size=6),
                fill='tonexty',
                fillcolor='rgba(255, 107, 107, 0.1)'
            ))
            
            fig_temp_hum.add_trace(go.Scatter(
                x=list(st.session_state.data_log["time"]),
                y=list(st.session_state.data_log["hum"]),
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
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis=dict(showgrid=True, gridcolor='#303030'),
                yaxis=dict(showgrid=True, gridcolor='#303030'),
                margin=dict(l=40, r=20, t=20, b=40)
            )
            
            st.plotly_chart(fig_temp_hum, use_container_width=True)
        else:
            st.info("⏳ Waiting for sensor data...")
    
    with chart_col2:
        st.markdown("### 🎚️ Potentiometer Activity")
        if len(st.session_state.data_log["time"]) > 0:
            fig_pot = go.Figure()
            
            fig_pot.add_trace(go.Scatter(
                x=list(st.session_state.data_log["time"]),
                y=list(st.session_state.data_log["pot"]),
                mode='lines',
                fill='tozeroy',
                line=dict(color='#ffd43b', width=3, shape='spline'),
                fillcolor='rgba(255, 212, 59, 0.3)'
            ))
            
            fig_pot.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                showlegend=False,
                xaxis=dict(showgrid=True, gridcolor='#303030'),
                yaxis=dict(showgrid=True, gridcolor='#303030', range=[0, 4095]),
                margin=dict(l=40, r=20, t=20, b=40)
            )
            
            st.plotly_chart(fig_pot, use_container_width=True)
        else:
            st.info("⏳ Waiting for sensor data...")

with tab2:
    st.markdown("### 🎛️ Actuator Control")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### 💡 LED Indicators")
        
        led_col1, led_col2, led_col3 = st.columns(3)
        
        with led_col1:
            if st.button("🔴 RED LED", 
                        type="primary" if st.session_state.button_states["red"] else "secondary",
                        use_container_width=True,
                        key="btn_red"):
                st.session_state.button_states["red"] = not st.session_state.button_states["red"]
                state = "on" if st.session_state.button_states["red"] else "off"
                if st.session_state.mqtt_client:
                    st.session_state.mqtt_client.publish(TOPIC_PUB, f"red:{state}")
                    st.success(f"✅ RED → {state.upper()}")
        
        with led_col2:
            if st.button("🟡 YELLOW LED",
                        type="primary" if st.session_state.button_states["yellow"] else "secondary",
                        use_container_width=True,
                        key="btn_yellow"):
                st.session_state.button_states["yellow"] = not st.session_state.button_states["yellow"]
                state = "on" if st.session_state.button_states["yellow"] else "off"
                if st.session_state.mqtt_client:
                    st.session_state.mqtt_client.publish(TOPIC_PUB, f"yellow:{state}")
                    st.success(f"✅ YELLOW → {state.upper()}")
        
        with led_col3:
            if st.button("🟢 GREEN LED",
                        type="primary" if st.session_state.button_states["green"] else "secondary",
                        use_container_width=True,
                        key="btn_green"):
                st.session_state.button_states["green"] = not st.session_state.button_states["green"]
                state = "on" if st.session_state.button_states["green"] else "off"
                if st.session_state.mqtt_client:
                    st.session_state.mqtt_client.publish(TOPIC_PUB, f"green:{state}")
                    st.success(f"✅ GREEN → {state.upper()}")
        
        st.markdown("#### 🔊 Audio Alert")
        if st.button("🔔 BUZZER",
                    type="primary" if st.session_state.button_states["buzzer"] else "secondary",
                    use_container_width=True,
                    key="btn_buzzer"):
            st.session_state.button_states["buzzer"] = not st.session_state.button_states["buzzer"]
            state = "on" if st.session_state.button_states["buzzer"] else "off"
            if st.session_state.mqtt_client:
                st.session_state.mqtt_client.publish(TOPIC_PUB, f"buzzer:{state}")
                st.success(f"✅ BUZZER → {state.upper()}")
    
    with col2:
        st.markdown("#### 📊 Actuator Status")
        
        st.markdown(f"**🔴 RED LED:** {'🟢 ON' if st.session_state.button_states['red'] else '⚫ OFF'}")
        st.markdown(f"**🟡 YELLOW LED:** {'🟢 ON' if st.session_state.button_states['yellow'] else '⚫ OFF'}")
        st.markdown(f"**🟢 GREEN LED:** {'🟢 ON' if st.session_state.button_states['green'] else '⚫ OFF'}")
        st.markdown(f"**🔔 BUZZER:** {'🟢 ON' if st.session_state.button_states['buzzer'] else '⚫ OFF'}")

with tab3:
    st.markdown("### 📊 ML Analytics")
    
    total = st.session_state.ml_stats["total_predictions"]
    
    if total > 0:
        # Stats cards
        stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
        
        with stats_col1:
            st.metric("Total Predictions", total)
        
        with stats_col2:
            st.metric("🔥 Panas", st.session_state.ml_stats["panas_count"])
        
        with stats_col3:
            st.metric("✅ Normal", st.session_state.ml_stats["normal_count"])
        
        with stats_col4:
            st.metric("❄️ Dingin", st.session_state.ml_stats["dingin_count"])
        
        st.markdown("---")
        
        # Distribution chart
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("#### Prediction Distribution")
            bar_data = pd.DataFrame({
                'Label': ['Panas', 'Normal', 'Dingin'],
                'Count': [
                    st.session_state.ml_stats['panas_count'],
                    st.session_state.ml_stats['normal_count'],
                    st.session_state.ml_stats['dingin_count']
                ]
            })
            fig_bar = px.bar(
                bar_data,
                x='Label',
                y='Count',
                color='Label',
                color_discrete_map={'Panas': '#ff6b6b', 'Normal': '#51cf66', 'Dingin': '#4dabf7'}
            )
            fig_bar.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=300,
                showlegend=False
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with chart_col2:
            st.markdown("#### Percentage Breakdown")
            panas_pct = (st.session_state.ml_stats['panas_count'] / total) * 100
            normal_pct = (st.session_state.ml_stats['normal_count'] / total) * 100
            dingin_pct = (st.session_state.ml_stats['dingin_count'] / total) * 100
            
            st.progress(panas_pct / 100, text=f"🔥 Panas: {panas_pct:.1f}%")
            st.progress(normal_pct / 100, text=f"✅ Normal: {normal_pct:.1f}%")
            st.progress(dingin_pct / 100, text=f"❄️ Dingin: {dingin_pct:.1f}%")
            
            st.caption(f"Last prediction: {st.session_state.ml_stats['last_prediction_time']}")
    else:
        st.info("⏳ No ML predictions yet. Waiting for inference data...")

with tab4:
    st.markdown("### 🐛 Debug Information")
    
    debug_col1, debug_col2, debug_col3 = st.columns(3)
    
    with debug_col1:
        st.markdown("#### MQTT Status")
        debug_mqtt = {
            "Broker": f"{BROKER}:{PORT}",
            "Client ID": CLIENT_ID,
            "Connected": st.session_state.connection_status["mqtt"],
            "Sub Topic": TOPIC_SUB,
            "Pub Topic": TOPIC_PUB
        }
        st.json(debug_mqtt)
    
    with debug_col2:
        st.markdown("#### Sensor Data")
        st.json(st.session_state.sensor_data)
    
    with debug_col3:
        st.markdown("#### ML Statistics")
        st.json(st.session_state.ml_stats)
    
    st.markdown("---")
    
    with st.expander("📦 Collected Data Preview"):
        if len(st.session_state.collected_data) > 0:
            df_preview = pd.DataFrame(st.session_state.collected_data)
            st.dataframe(df_preview.tail(20), use_container_width=True)
        else:
            st.info("No collected data yet")

# Auto-refresh every 1 second
time.sleep(1)
st.rerun()
