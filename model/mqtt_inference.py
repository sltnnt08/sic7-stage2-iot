import os
import sys
import json
import time
import joblib
import numpy as np
import paho.mqtt.client as mqtt

# ===============================
# Configuration
# ===============================
MODEL_PATH = "model/models/best_model.pkl"
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
TOPIC_SENSOR = "sic7/sensor"      # Subscribe: receive sensor data from ESP32
TOPIC_CONTROL = "sic7/control"    # Publish: send control commands to ESP32
CLIENT_ID = "mqttx_22adfc93"
MQTT_USER = "foursome"
MQTT_PASS = "berempat"

# Mapping label to control commands
COMMAND_MAP = {
    'Panas': ['red:on', 'buzzer:on', 'green:off', 'yellow:off'],
    'Normal': ['green:on', 'red:off', 'yellow:off', 'buzzer:off'],
    'Dingin': ['yellow:on', 'red:off', 'green:off', 'buzzer:off']
}

# ===============================
# Load ML Model
# ===============================
def load_model():
    """Load trained ML model"""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
    print(f"Loading model from: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    print("✅ Model loaded successfully\n")
    return model

model = None

# ===============================
# MQTT Callbacks
# ===============================
def on_connect(client, userdata, flags, rc, properties=None):
    """Callback when connected to MQTT broker"""
    if rc == 0:
        print("✅ Connected to MQTT broker")
        client.subscribe(TOPIC_SENSOR)
        print(f"📡 Subscribed to topic: {TOPIC_SENSOR}")
        print("🎯 Waiting for sensor data...\n")
    else:
        print(f"❌ Connection failed with code {rc}")

def on_message(client, userdata, msg):
    """Callback when message received from MQTT"""
    global model
    
    try:
        # Parse JSON payload
        payload = msg.payload.decode()
        data = json.loads(payload)
        
        temp = float(data.get('temp', 0))
        hum = float(data.get('hum', 0))
        pot = data.get('pot', 0)
        
        print(f"📥 Received: temp={temp}°C, hum={hum}%, pot={pot}")
        
        # Predict using ML model
        X = np.array([[temp, hum]])
        prediction = model.predict(X)[0]
        
        print(f"🤖 Prediction: {prediction}")
        
        # Publish status to OLED display
        status_msg = f"status:{prediction}"
        client.publish(TOPIC_CONTROL, status_msg)
        print(f"📤 Published: {status_msg}")
        
        # Publish control commands based on prediction
        commands = COMMAND_MAP.get(prediction, [])
        for cmd in commands:
            client.publish(TOPIC_CONTROL, cmd)
            print(f"📤 Published: {cmd}")
            time.sleep(0.1)  # Small delay between commands
        
        print("-" * 60)
        
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON: {msg.payload.decode()}")
    except Exception as e:
        print(f"❌ Error processing message: {e}")

def on_disconnect(client, userdata, flags, rc, properties=None):
    """Callback when disconnected from MQTT broker"""
    if rc != 0:
        print(f"⚠️ Unexpected disconnect (code {rc}). Reconnecting...")

# ===============================
# Main Function
# ===============================
def main():
    global model
    
    print("=" * 60)
    print("🚀 SIC7 MQTT Inference Server")
    print("=" * 60)
    
    # Load ML model
    try:
        model = load_model()
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        sys.exit(1)
    
    # Setup MQTT client (using CallbackAPIVersion for compatibility)
    client = mqtt.Client(
        client_id=CLIENT_ID,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    # Uncomment if your broker requires authentication
    # client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    # Connect to MQTT broker
    print(f"Connecting to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"❌ Failed to connect to MQTT broker: {e}")
        sys.exit(1)
    
    # Start MQTT loop
    print("✅ MQTT Inference Server is running...")
    print("Press Ctrl+C to stop\n")
    
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    finally:
        client.loop_stop()
        client.disconnect()
        print("👋 MQTT client disconnected. Goodbye!")

if __name__ == "__main__":
    main()
