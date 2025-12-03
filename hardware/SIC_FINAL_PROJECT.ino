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
const char* ssid = "KKTBSYS";
const char* password = "unidentified";
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* mqtt_user = "foursome";
const char* mqtt_password = "berempat";

String suhuStatus = "";
String prevStatus = "";
unsigned long lastBuzzerMillis = 0;
bool buzzerActive = false;
int buzzerDuration = 0;

WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastMsg = 0;

void setup_wifi() {
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
}

void callback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.print("MQTT msg: "); Serial.println(msg);

  int colon = msg.indexOf(':');
  if (colon > 0) {
    String which = msg.substring(0, colon);
    String state = msg.substring(colon + 1);
    bool on = (state == "on" || state == "1");
    
    // Baca potentiometer untuk brightness
    int pot = analogRead(POT_PIN);
    int brightness = map(pot, 0, 4095, 0, 255);

    // Gunakan analogWrite dengan brightness dari potentiometer
    if (which == "red") analogWrite(LED_RED, on ? brightness : 0);
    else if (which == "yellow") analogWrite(LED_YELLOW, on ? brightness : 0);
    else if (which == "green") analogWrite(LED_GREEN, on ? brightness : 0);
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("SIC7_ESP32_Client")) {
      Serial.println("connected");
      client.subscribe("sic7/control");
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

  // Setup PWM untuk setiap LED (ESP32 Core 3.x API)
  analogWriteFrequency(LED_RED, 1000);      // 1kHz PWM frequency
  analogWriteResolution(LED_RED, 8);        // 8-bit resolution (0-255)
  
  analogWriteFrequency(LED_YELLOW, 1000);
  analogWriteResolution(LED_YELLOW, 8);
  
  analogWriteFrequency(LED_GREEN, 1000);
  analogWriteResolution(LED_GREEN, 8);

  // Matikan semua LED
  analogWrite(LED_RED, 0);
  analogWrite(LED_YELLOW, 0);
  analogWrite(LED_GREEN, 0);
  digitalWrite(BUZZER_PIN, LOW);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED gagal diinisialisasi!");
    for (;;);
  }

  // Boot screen dengan text besar dan di tengah
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);  // Text lebih besar
  
  // Teks "SIC7" di baris pertama (tengah)
  int16_t x1, y1;
  uint16_t w, h;
  display.getTextBounds("SIC7", 0, 0, &x1, &y1, &w, &h);
  display.setCursor((SCREEN_WIDTH - w) / 2, 10);
  display.println("SIC7");
  
  // Teks "FINAL" di baris kedua
  display.getTextBounds("FINAL", 0, 0, &x1, &y1, &w, &h);
  display.setCursor((SCREEN_WIDTH - w) / 2, 30);
  display.println("FINAL");
  
  // Teks "PROJECT" di baris ketiga
  display.getTextBounds("PROJECT", 0, 0, &x1, &y1, &w, &h);
  display.setCursor((SCREEN_WIDTH - w) / 2, 50);
  display.println("PROJECT");
  
  display.display();
  delay(2000);  // Tampilkan selama 2 detik

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

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

void updateTemperatureStatus(float t, int brightness) {
  // Tentukan status suhu baru
  if (t > 30) {
    suhuStatus = "Panas";
    analogWrite(LED_RED, brightness);    // RED dengan brightness dari pot
    analogWrite(LED_YELLOW, 0);
    analogWrite(LED_GREEN, 0);
    buzzerDuration = 5000;
  } else if (t >= 25) {
    suhuStatus = "Hangat";
    analogWrite(LED_RED, 0);
    analogWrite(LED_YELLOW, brightness); // YELLOW dengan brightness dari pot
    analogWrite(LED_GREEN, 0);
    buzzerDuration = 2000;
  } else {
    suhuStatus = "Dingin";
    analogWrite(LED_RED, 0);
    analogWrite(LED_YELLOW, 0);
    analogWrite(LED_GREEN, brightness);  // GREEN dengan brightness dari pot
    buzzerDuration = 1000;
  }

  // 🔁 Nyalakan buzzer hanya jika status berubah
  if (suhuStatus != prevStatus) {
    Serial.println("⚡ Status berubah! Buzzer aktif");
    buzzerActive = true;
    lastBuzzerMillis = millis();
    prevStatus = suhuStatus;
  }
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

    updateTemperatureStatus(t, brightness);

    // OLED - Ukuran text kembali normal (size 1)
    display.clearDisplay();
    display.setTextSize(1);  // Text normal untuk loop
    display.setCursor(0, 0);
    display.println("TEAM FOURSOME - SIC7");
    display.print("Temp: "); display.print(t); display.println(" C");
    display.print("Hum:  "); display.print(h); display.println(" %");
    display.print("Status: "); display.println(suhuStatus);
    display.print("Pot:  "); display.print(pot);
    display.print(" ("); display.print(brightness); display.println(")");
    display.display();

    // MQTT Publish
    String payload = String("{\"temp\":") + t +
                     ",\"hum\":" + h +
                     ",\"status\":\"" + suhuStatus +
                     "\",\"pot\":" + pot + "}";
    client.publish("sic7/sensor", payload.c_str());
    Serial.println(payload);
  }

  // Kontrol buzzer
  if (buzzerActive) {
    int potValue = analogRead(POT_PIN);
    int freq = map(potValue, 0, 4095, 100, 2000); // frekuensi 100-2000 Hz
    playTone(freq);

    if (millis() - lastBuzzerMillis >= buzzerDuration) {
      buzzerActive = false;
      digitalWrite(BUZZER_PIN, LOW);
      Serial.println("✅ Buzzer OFF");
    }
  } else {
    digitalWrite(BUZZER_PIN, LOW);
    delay(5);
  }
}
