#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_GFX.h>

#define DHTPIN 4
#define DHTTYPE DHT11
#define BUZZER_PIN 27
#define LED_RED 18
#define LED_YELLOW 19
#define LED_GREEN 23
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
DHT dht(DHTPIN, DHTTYPE);

// WiFi & MQTT
const char* ssid = "SISWA NESKAR";
const char* password = "siswa@neskar";
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;

WiFiClient espClient;
PubSubClient client(espClient);

String suhuStatus = "N/A";
unsigned long lastMsg = 0;
bool buzzerActive = false;

// Buzzer tone full power
void playToneFull() {
  long freq = 2000;                    // frekuensi tinggi = lebih lantang
  long period = 1000000L / freq;
  long halfPeriod = period / 2;
  
  digitalWrite(BUZZER_PIN, HIGH);
  delayMicroseconds(halfPeriod);
  digitalWrite(BUZZER_PIN, LOW);
  delayMicroseconds(halfPeriod);
}

void setup_wifi() {
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
}

// MQTT callback
void callback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];

  int colon = msg.indexOf(':');
  if (colon < 0) {
    Serial.println("Malformed MQTT payload");
    return;
  }

  String which = msg.substring(0, colon);
  String state = msg.substring(colon + 1);
  bool on = (state == "on");

  if (which == "red") {
    digitalWrite(LED_RED, on ? HIGH : LOW);
  } 
  else if (which == "yellow") {
    digitalWrite(LED_YELLOW, on ? HIGH : LOW);
  }
  else if (which == "green") {
    digitalWrite(LED_GREEN, on ? HIGH : LOW);
  }
  else if (which == "buzzer") {
    buzzerActive = on;
    if (!on) digitalWrite(BUZZER_PIN, LOW);
  }
  else if (which == "status") {
    suhuStatus = state;
    
    // AUTO CONTROL LED & BUZZER BERDASARKAN PREDIKSI
    // Matikan semua LED dulu
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_GREEN, LOW);
    buzzerActive = false;
    
    if (state == "Panas") {
      // PANAS = LED MERAH + BUZZER
      digitalWrite(LED_RED, HIGH);
      buzzerActive = true;
      Serial.println("🔥 AUTO: RED LED + BUZZER ON (Panas)");
    }
    else if (state == "Hangat" || state == "Normal") {
      // HANGAT/NORMAL = LED KUNING
      digitalWrite(LED_YELLOW, HIGH);
      Serial.println("🟡 AUTO: YELLOW LED ON (Hangat/Normal)");
    }
    else if (state == "Dingin") {
      // DINGIN = LED HIJAU
      digitalWrite(LED_GREEN, HIGH);
      Serial.println("❄️ AUTO: GREEN LED ON (Dingin)");
    }
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("SIC7_ESP32_Client")) {
      Serial.println("connected");
      client.subscribe("sic7/control");
    } else {
      Serial.print("failed, rc=");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  // Pin setup
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  digitalWrite(LED_RED, LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  // OLED boot screen
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED init failed!");
    for(;;);
  }

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);

  display.setCursor(20, 10); display.println("SIC7");
  display.setCursor(20, 30); display.println("FINAL");
  display.setCursor(10, 50); display.println("PROJECT");
  display.display();

  delay(2000);

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) reconnect();
  client.loop();

  unsigned long now = millis();
  if (now - lastMsg > 3000) {
    lastMsg = now;

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (isnan(h) || isnan(t)) {
      Serial.println("DHT gagal membaca data!");
      return;
    }

    // OLED Display Update
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("TEAM FOURSOME - SIC7");

    display.print("Temp: "); display.print(t, 1); display.println(" C");
    display.print("Hum:  "); display.print(h, 1); display.println(" %");
    display.print("Status: "); display.println(suhuStatus);

    display.display();

    // Publish raw sensor data (tanpa pot)
    String payload = 
      "{\"temp\":" + String(t, 2) +
      ",\"hum\":" + String(h, 2) +
      "}";

    client.publish("sic7/sensor", payload.c_str());
    Serial.println("Published: " + payload);
  }

  // Buzzer kontrol ML (full volume)
  if (buzzerActive) {
    playToneFull();
  } else {
    digitalWrite(BUZZER_PIN, LOW);
    delay(3);
  }
}
