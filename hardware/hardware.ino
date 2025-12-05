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
#define POT_PIN 34
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
DHT dht(DHTPIN, DHTTYPE);

// WiFi & MQTT
const char* ssid = "SISWA NESKAR";
const char* password = "siswa@neskar";
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
// Jika broker butuh auth, isi; kalau tidak bisa dibiarkan kosong
const char* mqtt_user = "foursome";
const char* mqtt_password = "berempat";

String suhuStatus = "N/A"; // sekarang berasal dari ML lewat MQTT
WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastMsg = 0;
bool buzzerActive = false;

// Fungsi tone manual tanpa PWM
void playTone(int freq) {
  if (freq <= 0) return;
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

// MQTT callback: menerima perintah dari Python/ML
void callback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.print("MQTT msg: "); Serial.println(msg);

  int colon = msg.indexOf(':');
  if (colon > 0) {
    String which = msg.substring(0, colon);
    String state = msg.substring(colon + 1);
    bool on = (state == "on" || state == "1");

    // Baca potentiometer untuk brightness dan frekuensi saat eksekusi
    int pot = analogRead(POT_PIN);
    int brightness = map(pot, 0, 4095, 0, 255);

    if (which == "red") {
      analogWrite(LED_RED, on ? brightness : 0);
    } else if (which == "yellow") {
      analogWrite(LED_YELLOW, on ? brightness : 0);
    } else if (which == "green") {
      analogWrite(LED_GREEN, on ? brightness : 0);
    } else if (which == "buzzer") {
      if (on) {
        buzzerActive = true;
        Serial.println("MQTT -> Buzzer ON");
      } else {
        buzzerActive = false;
        digitalWrite(BUZZER_PIN, LOW);
        Serial.println("MQTT -> Buzzer OFF");
      }
    } else if (which == "status") {
      // status dikirim dari Python/ML untuk ditampilkan di OLED
      suhuStatus = state;
      Serial.print("Status updated from MQTT: ");
      Serial.println(suhuStatus);
    } else {
      Serial.println("Unknown command topic payload");
    }
  } else {
    Serial.println("Malformed MQTT payload (expected format 'key:value')");
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Client ID bisa disesuaikan
    if (client.connect("SIC7_ESP32_Client")) {
      Serial.println("connected");
      client.subscribe("sic7/control"); // topic untuk perintah (ML -> ESP32)
    } else {
      Serial.print("failed, rc="); Serial.print(client.state());
      Serial.println(" try again in 3 seconds");
      delay(3000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  pinMode(LED_RED, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(POT_PIN, INPUT);

  // Setup PWM untuk setiap LED (ESP32 Core API)
  analogWriteFrequency(LED_RED, 1000);      // 1kHz PWM frequency
  analogWriteResolution(LED_RED, 8);        // 8-bit resolution (0-255)
  
  analogWriteFrequency(LED_YELLOW, 1000);
  analogWriteResolution(LED_YELLOW, 8);
  
  analogWriteFrequency(LED_GREEN, 1000);
  analogWriteResolution(LED_GREEN, 8);

  // Matikan semua LED & buzzer
  analogWrite(LED_RED, 0);
  analogWrite(LED_YELLOW, 0);
  analogWrite(LED_GREEN, 0);
  digitalWrite(BUZZER_PIN, LOW);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED gagal diinisialisasi!");
    for (;;);
  }

  // Boot screen
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);
  int16_t x1, y1;
  uint16_t w, h;
  display.getTextBounds("SIC7", 0, 0, &x1, &y1, &w, &h);
  display.setCursor((SCREEN_WIDTH - w) / 2, 10);
  display.println("SIC7");
  display.getTextBounds("FINAL", 0, 0, &x1, &y1, &w, &h);
  display.setCursor((SCREEN_WIDTH - w) / 2, 30);
  display.println("FINAL");
  display.getTextBounds("PROJECT", 0, 0, &x1, &y1, &w, &h);
  display.setCursor((SCREEN_WIDTH - w) / 2, 50);
  display.println("PROJECT");
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
    int pot = analogRead(POT_PIN);
    
    // Konversi potentiometer (0-4095) ke brightness LED (0-255)
    int brightness = map(pot, 0, 4095, 0, 255);

    if (isnan(h) || isnan(t)) {
      Serial.println("DHT gagal membaca data!");
      return;
    }

    // OLED - menampilkan data sensor + status (status berasal dari ML via MQTT)
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("TEAM FOURSOME - SIC7");
    display.print("Temp: "); display.print(t); display.println(" C");
    display.print("Hum:  "); display.print(h); display.println(" %");
    display.print("Status: "); display.println(suhuStatus);
    display.print("Pot:  "); display.print(pot);
    display.print(" ("); display.print(brightness); display.println(")");
    display.display();

    // MQTT Publish: KIRIM DATA MENTAH (tanpa status)
    String payload = String("{\"temp\":") + String(t, 2) +
                     ",\"hum\":" + String(h, 2) +
                     ",\"pot\":" + String(pot) + "}";
    client.publish("sic7/sensor", payload.c_str());
    Serial.println("Published: " + payload);
  }

  // Jika buzzer aktif (diperintah via MQTT), mainkan tone dengan frekuensi dari pot
  if (buzzerActive) {
    int potValue = analogRead(POT_PIN);
    int freq = map(potValue, 0, 4095, 100, 2000); // frekuensi 100-2000 Hz
    playTone(freq);
    // Buzzer akan berhenti hanya saat menerima perintah "buzzer:off" dari MQTT
  } else {
    digitalWrite(BUZZER_PIN, LOW);
    delay(5);
  }
}
