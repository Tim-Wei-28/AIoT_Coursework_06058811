#include <driver/i2s.h>
#include <math.h>

#define I2S_WS 6
#define I2S_SD 5
#define I2S_SCK 7

#define I2S_PORT I2S_NUM_0

#define SAMPLE_RATE 16000
#define BUFFER_SIZE 1024

int32_t buffer[BUFFER_SIZE];

float calibrationOffset = 108.0; // this is my observed offset between the NIOSH SLM and my INMP441 detected noise

void setupI2S() {

  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = -1,
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
  i2s_zero_dma_buffer(I2S_PORT);
}

float calculateRMS(int32_t *samples, int count) {

  double sum = 0;

  for (int i = 0; i < count; i++) {
    float sample = samples[i] / 2147483648.0; // normalisation
    sum += sample * sample;
  }

  return sqrt(sum / count);
}

void setup() {

  Serial.begin(115200);
  delay(1000);

  Serial.println("INMP441 Calibration Start");

  setupI2S();
}

void loop() {

  size_t bytesRead;

  i2s_read(
    I2S_PORT,
    &buffer,
    sizeof(buffer),
    &bytesRead,
    portMAX_DELAY
  );

  int samples = bytesRead / sizeof(int32_t);

  float rms = calculateRMS(buffer, samples);

  float dbfs = 20 * log10(rms);

  float db = dbfs + calibrationOffset;

  Serial.print("RMS: ");
  Serial.print(rms, 6);

  Serial.print(" | dBFS: ");
  Serial.print(dbfs, 2);

  Serial.print(" | dB (calibrated): ");
  Serial.println(db, 2);

  delay(200);
}