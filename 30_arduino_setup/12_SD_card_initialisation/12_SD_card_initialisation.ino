#include <SPI.h>
#include <SD.h>

#define SD_SCK 21
#define SD_MISO 34
#define SD_MOSI 26
#define SD_CS 19

void setup() {

  Serial.begin(115200);
  delay(2000); 
  Serial.println("Starting SD card test...");

  // Initialize SPI with custom pins
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);

  Serial.println("Initializing SD card...");

  if (!SD.begin(SD_CS, SPI, 1000000)) {
    Serial.println("SD card initialization FAILED!");
    return;
  }

  Serial.println("SD card initialization SUCCESS.");

  File file = SD.open("/test2.txt", FILE_WRITE);

  if (!file) {
    Serial.println("Failed to open file!");
    return;
  }

  Serial.println("Writing to file...");

  file.println("ESP32 SD card test successful.");
  file.println("If you can read this, SD logging works!");

  file.close();

  Serial.println("File written successfully.");
}

void loop() {
}