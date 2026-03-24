#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include "driver/i2s.h"

// ---------------- SD CARD ----------------
#define SD_SCK 21
#define SD_MISO 34
#define SD_MOSI 26
#define SD_CS 19

// ---------------- MICROPHONE ----------------
#define I2S_WS 6
#define I2S_SD 5
#define I2S_SCK 7

#define SAMPLE_RATE 16000
#define BUFFER_SIZE 1024

#define DB_OFFSET 108.0 // determined using mic_cal.ino

int32_t i2sBuffer[BUFFER_SIZE];

// -------- ENERGY ACCUMULATION --------
double energySum = 0;
uint32_t sampleCount = 0;

// -------- TIMING --------
unsigned long lastSecond = 0;
unsigned long secondsSinceStart = 0;

// -------- FILE NAME --------
char filename[32];

// ---------------- I2S SETUP ----------------
void setupI2S() {

  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = BUFFER_SIZE,
    .use_apll = false
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
  i2s_zero_dma_buffer(I2S_NUM_0);
}


// ---------------- SETUP ----------------
void setup() {

  Serial.begin(115200);
  delay(2000);

  Serial.println("Starting sound logger...");

  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);

  if (!SD.begin(SD_CS, SPI, 1000000)) {
    Serial.println("SD card initialization failed!");
    while (1);
  }

  Serial.println("SD card initialized.");

  // -------- FIND NEXT FILE NUMBER --------
  int fileIndex = 1;

  while (true) {
    sprintf(filename, "/sound_log_%d.csv", fileIndex);

    if (!SD.exists(filename)) {
      break;
    }

    fileIndex++;
  }

  Serial.print("Logging to file: ");
  Serial.println(filename);

  // create file header once
  File file = SD.open(filename, FILE_WRITE);

  if (file) {

    file.println("seconds;db");

    file.close();
  }

  setupI2S();
}


// ---------------- LOOP ----------------
void loop() {

  size_t bytesRead;

  i2s_read(
    I2S_NUM_0,
    i2sBuffer,
    sizeof(i2sBuffer),
    &bytesRead,
    portMAX_DELAY
  );

  int samples = bytesRead / sizeof(int32_t);

  for (int i = 0; i < samples; i++) {

    int32_t sample = i2sBuffer[i] >> 8;

    energySum += (double)sample * sample;
    sampleCount++;
  }

  unsigned long now = millis();

  if (now - lastSecond >= 1000) {

    lastSecond += 1000;

    if (sampleCount == 0) return;

    double mean = energySum / sampleCount;
    double rms = sqrt(mean);

    if (rms < 1) rms = 1;

    float dbfs = 20.0 * log10(rms / 8388608.0);
    float dbspl = dbfs + DB_OFFSET;

    Serial.print(secondsSinceStart);
    Serial.print(" s  ");
    Serial.print(dbspl);
    Serial.println(" dB");

    // -------- OPEN / WRITE / CLOSE FILE --------

    File file = SD.open(filename, FILE_APPEND);

    if (file) {

      file.print(secondsSinceStart);
      file.print(";");
      file.println(dbspl, 2);

      file.close();

      Serial.println("Logged to SD.");
    }
    else {
      Serial.println("SD write failed!");
    }

    energySum = 0;
    sampleCount = 0;

    secondsSinceStart++;
  }
}