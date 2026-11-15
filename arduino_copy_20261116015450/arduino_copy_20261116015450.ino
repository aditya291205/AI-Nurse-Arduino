#include <Wire.h>
#include "MAX30105.h"
#include <OneWire.h>
#include <DallasTemperature.h>

MAX30105 particleSensor;
#define ONE_WIRE_BUS 2
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

bool maxConnected = false;

void setup() {
  Serial.begin(115200);
  delay(2000); 

  Wire.begin();
  
  // Safe non-blocking check for MAX30102 at address 0x57
  Wire.beginTransmission(0x57);
  if (Wire.endTransmission() == 0) {
    if (particleSensor.begin(Wire, I2C_SPEED_FAST)) {
      particleSensor.setup();
      maxConnected = true;
    }
  }

  sensors.begin();

  pinMode(10, INPUT);
  pinMode(11, INPUT);
  pinMode(A0, INPUT);
}

void loop() {
  sensors.requestTemperatures();
  float tempC = sensors.getTempCByIndex(0);
  
  long irValue = 0;
  if (maxConnected) {
    irValue = particleSensor.getIR();
  }

  int ecgValue = analogRead(A0);
  int leadPlus = digitalRead(10);
  int leadMinus = digitalRead(11);

  Serial.print("{\"temp\": ");
  Serial.print(tempC);
  Serial.print(", \"ir\": ");
  Serial.print(irValue);
  Serial.print(", \"ecg\": ");
  Serial.print(ecgValue);
  Serial.print(", \"lead_plus\": ");
  Serial.print(leadPlus);
  Serial.print(", \"lead_minus\": ");
  Serial.print(leadMinus);
  Serial.println("}");

  delay(30);
}