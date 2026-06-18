/*
 * main.c — Hardware bring-up test suite for the ORIGINAL TSky26b I2C slave
 *          design (no signal generator), ported from the cocotb testbench
 *          to ESP-IDF for the ESP32-C6 acting as I2C master against the FPGA.
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Memory map (original design):
 *   Block A (general registers), master writable/readable:  0x00..0x07
 *   Block B (LFSR pseudo-sensor), master read-only:          0x08..0x0F
 *   Signature (constant), read-only:                         0xF8..0xFF
 *   Everything else is unmapped: writes ACKed-but-ignored, reads return 0x00.
 *
 * On real hardware there is no internal visibility, so every white-box check
 * from cocotb (state, registers[i], reg_write monitor) is replaced by its
 * black-box read-back equivalent — the same fallback the cocotb tests use at
 * gate level.
 */

#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2c_master.h"
#include "esp_log.h"

static const char *TAG = "i2c_suite";

/* ----------------------------- Configuration ----------------------------- */
#define I2C_SCL_GPIO        7
#define I2C_SDA_GPIO        6
#define DEVICE_ADDR         0x55
#define TIMEOUT_MS          1000
#define OUTER_DELAY_MS      100

/* Memory map */
#define A_BASE              0x00     /* 0x00..0x07 general scratch (writable) */
#define B_BASE              0x08     /* 0x08..0x0F LFSR, read-only            */
#define SIG_BASE            0xF8     /* 0xF8..0xFF constant signature         */
#define UNMAPPED_ADDR       0x20     /* in the gap, neither block             */

/* First-run discovery: leave this at the empty string to just print what the
 * signature registers contain, then paste the 8 observed bytes here to enable
 * the pass/fail check (e.g. "SBJS2026"). */
#define SIG_EXPECTED        "SBJS2026"       /* 8 chars, or "" to only log */

/* Speeds (cocotb parametrized over these). 1 MHz needs strong external
 * pull-ups and short wiring; remove it if the bus is unreliable. */
typedef struct { const char *name; uint32_t hz; } speed_t;
static const speed_t SPEEDS[] = {
    {"100kHz", 100000},
    {"400kHz", 400000},
    {"1MHz",   1000000},
};
#define N_SPEEDS (sizeof(SPEEDS) / sizeof(SPEEDS[0]))

/* --------------------------- Global handles ------------------------------ */
static i2c_master_bus_handle_t bus;
static i2c_master_dev_handle_t dev_at[N_SPEEDS];

/* --------------------------- Pass/fail tally ----------------------------- */
static int g_pass = 0, g_fail = 0;
#define FAILV(fmt, ...) do { ESP_LOGE(TAG, "    FAIL: " fmt, ##__VA_ARGS__); return false; } while (0)

/* ------------------------- Reproducible PRNG ----------------------------- */
static uint32_t lcg_state;
static void     rng_seed(uint32_t s) { lcg_state = s; }
static uint32_t rng_next(void)       { lcg_state = lcg_state * 1664525u + 1013904223u; return lcg_state; }
static int      rng_range(int lo, int hi) { return lo + (int)((rng_next() >> 16) % (uint32_t)(hi - lo + 1)); }

/* --------------------------- I2C helpers --------------------------------- */
static esp_err_t reg_write_n(i2c_master_dev_handle_t dev, uint8_t start,
                             const uint8_t *data, size_t n)
{
    uint8_t buf[16];
    buf[0] = start;
    memcpy(&buf[1], data, n);
    return i2c_master_transmit(dev, buf, n + 1, TIMEOUT_MS);
}
static esp_err_t reg_write1(i2c_master_dev_handle_t dev, uint8_t reg, uint8_t val)
{
    uint8_t b[2] = { reg, val };
    return i2c_master_transmit(dev, b, 2, TIMEOUT_MS);
}
static esp_err_t reg_read_n(i2c_master_dev_handle_t dev, uint8_t start,
                            uint8_t *buf, size_t n)
{
    return i2c_master_transmit_receive(dev, &start, 1, buf, n, TIMEOUT_MS);
}
static esp_err_t reg_read1(i2c_master_dev_handle_t dev, uint8_t reg, uint8_t *val)
{
    return reg_read_n(dev, reg, val, 1);
}

/* ============================== TEST CASES =============================== */

/* 1) Address ACK (was test_write_address; internal state not visible) */
static bool test_address_ack(i2c_master_dev_handle_t dev)
{
    if (i2c_master_probe(bus, DEVICE_ADDR, TIMEOUT_MS) != ESP_OK)
        FAILV("device 0x%02X did not ACK its address", DEVICE_ADDR);
    return true;
}

/* 2) Read returns data (was test_read_address) */
static bool test_read_returns_data(i2c_master_dev_handle_t dev)
{
    uint8_t v;
    if (reg_read1(dev, A_BASE, &v) != ESP_OK) FAILV("read transaction not ACKed");
    return true;
}

/* 3) Wrong address must NACK (fully faithful, black-box) */
static bool test_wrong_address(i2c_master_dev_handle_t dev)
{
    const uint8_t wrong[] = { 0x42, 0x54, 0x56 };  /* 0x54/0x56 are 1 bit off */
    for (size_t i = 0; i < sizeof(wrong); i++)
        if (i2c_master_probe(bus, wrong[i], TIMEOUT_MS) == ESP_OK)
            FAILV("foreign address 0x%02X was wrongly ACKed", wrong[i]);
    if (i2c_master_probe(bus, DEVICE_ADDR, TIMEOUT_MS) != ESP_OK)
        FAILV("own address 0x%02X did not ACK", DEVICE_ADDR);
    return true;
}

/* 4) Single write + read-back (was test_full_write) */
static bool test_write_readback(i2c_master_dev_handle_t dev)
{
    uint8_t v;
    if (reg_write1(dev, 0x03, 0x57) != ESP_OK) FAILV("write not ACKed");
    if (reg_read1(dev, 0x03, &v)    != ESP_OK) FAILV("read not ACKed");
    if (v != 0x57) FAILV("read-back 0x%02X != 0x57", v);
    return true;
}

/* 5) Write, then separate read (was test_write_then_read) */
static bool test_write_then_read(i2c_master_dev_handle_t dev)
{
    uint8_t v;
    if (reg_write1(dev, 0x00, 0x57) != ESP_OK) FAILV("write not ACKed");
    vTaskDelay(pdMS_TO_TICKS(1));
    if (reg_read1(dev, 0x00, &v)    != ESP_OK) FAILV("read not ACKed");
    if (v != 0x57) FAILV("read-back 0x%02X != 0x57", v);
    return true;
}

/* 6) Bulk write with auto-increment (was test_bulk_write) */
static bool test_bulk_write(i2c_master_dev_handle_t dev)
{
    const uint8_t data[3] = { 0x11, 0x22, 0x33 };
    if (reg_write_n(dev, 0x02, data, 3) != ESP_OK) FAILV("bulk write not ACKed");
    for (int i = 0; i < 3; i++) {
        uint8_t v;
        if (reg_read1(dev, 0x02 + i, &v) != ESP_OK) FAILV("read-back not ACKed");
        if (v != data[i]) FAILV("reg 0x%02X = 0x%02X, expected 0x%02X", 0x02 + i, v, data[i]);
    }
    return true;
}

/* 7) Bulk read as auto-incremented sequence (was test_bulk_read) */
static bool test_bulk_read(i2c_master_dev_handle_t dev)
{
    const uint8_t vals[4] = { 0xDE, 0xAD, 0xBE, 0xEF };
    uint8_t rd[4];
    if (reg_write_n(dev, 0x03, vals, 4) != ESP_OK) FAILV("prep write not ACKed");
    if (reg_read_n(dev, 0x03, rd, 4)    != ESP_OK) FAILV("bulk read not ACKed");
    for (int i = 0; i < 4; i++)
        if (rd[i] != vals[i]) FAILV("byte %d = 0x%02X, expected 0x%02X", i, rd[i], vals[i]);
    return true;
}

/* 8) Address decoding / block isolation (was test_address_decoding) */
static bool test_address_decoding(i2c_master_dev_handle_t dev)
{
    uint8_t snap[8], v;
    for (int i = 0; i < 8; i++)
        if (reg_read1(dev, A_BASE + i, &snap[i]) != ESP_OK) FAILV("snapshot read failed");

    if (reg_write1(dev, 0x02, 0xA5) != ESP_OK) FAILV("A write not ACKed");
    /* attempt a write into Block B (0x0B) — ACKed but must not leak into A */
    if (reg_write1(dev, 0x0B, 0xFF) != ESP_OK) FAILV("B write attempt not ACKed");

    if (reg_read1(dev, 0x02, &v) != ESP_OK) FAILV("A read-back failed");
    if (v != 0xA5) FAILV("A target = 0x%02X, expected 0xA5", v);

    for (int i = 0; i < 8; i++) {
        if (i == 2) continue;
        if (reg_read1(dev, A_BASE + i, &v) != ESP_OK) FAILV("A read-back failed");
        if (v != snap[i]) FAILV("A 0x%02X disturbed: 0x%02X != 0x%02X", A_BASE + i, v, snap[i]);
    }
    return true;
}

/* 9) Unmapped address (was test_unmapped_address) */
static bool test_unmapped_address(i2c_master_dev_handle_t dev)
{
    uint8_t v;
    if (reg_write1(dev, 0x05, 0x99) != ESP_OK) FAILV("reference write not ACKed");
    if (reg_write1(dev, UNMAPPED_ADDR, 0xCC) != ESP_OK) FAILV("unmapped write not ACKed");

    if (reg_read1(dev, 0x05, &v) != ESP_OK) FAILV("reference read failed");
    if (v != 0x99) FAILV("reference reg disturbed: 0x%02X != 0x99", v);

    if (reg_read1(dev, UNMAPPED_ADDR, &v) != ESP_OK) FAILV("unmapped read not ACKed");
    if (v != 0x00) FAILV("unmapped read = 0x%02X, expected 0x00", v);
    return true;
}

/* 10) Block B read-only (was test_block_b_is_read_only).
 * The LFSR keeps writing Block B, so we check "write did not stick": after
 * trying to write 0xFF, the value should not read back as 0xFF. (A 1/256
 * coincidence with the live LFSR is possible; a re-run distinguishes it.) */
static bool test_block_b_read_only(i2c_master_dev_handle_t dev)
{
    uint8_t v;
    if (reg_write1(dev, 0x0A, 0xFF) != ESP_OK) FAILV("write attempt not ACKed");
    if (reg_read1(dev, 0x0A, &v)    != ESP_OK) FAILV("read-back not ACKed");
    if (v == 0xFF) FAILV("Block B may have accepted the write (read 0xFF)");
    return true;
}

/* 11) LFSR is active (was test_lfsr_is_active) */
static bool test_lfsr_is_active(i2c_master_dev_handle_t dev)
{
    uint8_t s[4];
    for (int i = 0; i < 4; i++) {
        if (reg_read1(dev, B_BASE + 1, &s[i]) != ESP_OK) FAILV("sample read failed");
        if (i < 3) vTaskDelay(pdMS_TO_TICKS(10));
    }
    if (!((s[0] != s[1]) || (s[1] != s[2]) || (s[2] != s[3])))
        FAILV("LFSR appears stuck: %02X %02X %02X %02X", s[0], s[1], s[2], s[3]);
    return true;
}

/* 12) Block A unaffected by the LFSR (was test_block_a_unaffected_by_lfsr) */
static bool test_block_a_stable(i2c_master_dev_handle_t dev)
{
    uint8_t pattern[8];
    for (int i = 0; i < 8; i++) pattern[i] = 0xA0 | i;
    if (reg_write_n(dev, A_BASE, pattern, 8) != ESP_OK) FAILV("pattern write not ACKed");
    vTaskDelay(pdMS_TO_TICKS(5));   /* several LFSR sweeps through Block B */
    for (int i = 0; i < 8; i++) {
        uint8_t v;
        if (reg_read1(dev, A_BASE + i, &v) != ESP_OK) FAILV("read-back failed");
        if (v != pattern[i]) FAILV("A 0x%02X changed: 0x%02X != 0x%02X", A_BASE + i, v, pattern[i]);
    }
    return true;
}

/* 13) Bulk-read stress over LFSR activity (was test_bulk_read_stress) */
static bool test_bulk_read_stress(i2c_master_dev_handle_t dev)
{
    const int N_ITER = 20, N_BYTES = 4;
    uint8_t all[20][4];
    for (int it = 0; it < N_ITER; it++) {
        if (reg_read_n(dev, B_BASE + 1, all[it], N_BYTES) != ESP_OK)
            FAILV("iter %d: bulk read not ACKed", it);
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    for (int slot = 0; slot < N_BYTES; slot++) {
        bool varies = false;
        for (int it = 1; it < N_ITER; it++)
            if (all[it][slot] != all[0][slot]) { varies = true; break; }
        if (!varies) FAILV("slot %d (0x%02X) identical across iterations", slot, B_BASE + 1 + slot);
    }
    uint8_t v;
    if (reg_read1(dev, A_BASE, &v) != ESP_OK) FAILV("slave unresponsive after stress");
    return true;
}

/* 14) Mixed read/write stress with shadow model (was test_mixed_stress).
 * Writes span all of Block A (0x00..0x07); reads span A (checked) and B (not). */
static bool test_mixed_stress(i2c_master_dev_handle_t dev)
{
    const int N_ITER = 20;
    uint8_t shadow[8];
    rng_seed(42);

    for (int i = 0; i < 8; i++)
        if (reg_read1(dev, A_BASE + i, &shadow[i]) != ESP_OK) FAILV("shadow init failed");

    for (int it = 0; it < N_ITER; it++) {
        if (rng_next() & 1) {
            int idx   = rng_range(0, 7);
            uint8_t v = (uint8_t)rng_range(0, 255);
            if (reg_write1(dev, A_BASE + idx, v) != ESP_OK) FAILV("iter %d: write not ACKed", it);
            shadow[idx] = v;
        } else {
            int addr = rng_range(A_BASE, B_BASE + 7);   /* A or B */
            uint8_t v;
            if (reg_read1(dev, addr, &v) != ESP_OK) FAILV("iter %d: read not ACKed", it);
            if (addr >= A_BASE && addr <= A_BASE + 7 && v != shadow[addr - A_BASE])
                FAILV("iter %d: A 0x%02X = 0x%02X, model says 0x%02X",
                      it, addr, v, shadow[addr - A_BASE]);
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    for (int i = 0; i < 8; i++) {
        uint8_t v;
        if (reg_read1(dev, A_BASE + i, &v) != ESP_OK) FAILV("final read failed");
        if (v != shadow[i]) FAILV("final A 0x%02X = 0x%02X, model says 0x%02X",
                                  A_BASE + i, v, shadow[i]);
    }
    return true;
}

/* 15) Signature registers at 0xF8..0xFF — logs content; checks if expected set. */
static bool test_signature(i2c_master_dev_handle_t dev)
{
    uint8_t sig[8];
    if (reg_read_n(dev, SIG_BASE, sig, 8) != ESP_OK) FAILV("signature read not ACKed");

    ESP_LOGI(TAG, "    signature bytes: %02X %02X %02X %02X %02X %02X %02X %02X",
             sig[0], sig[1], sig[2], sig[3], sig[4], sig[5], sig[6], sig[7]);
    ESP_LOGI(TAG, "    signature ascii: %.8s", (char *)sig);

    if (sizeof(SIG_EXPECTED) - 1 == 8) {   /* a real 8-char expectation is set */
        if (memcmp(sig, SIG_EXPECTED, 8) != 0)
            FAILV("signature mismatch (expected \"%s\")", SIG_EXPECTED);
    } else {
        ESP_LOGW(TAG, "    (SIG_EXPECTED not set — logging only, no pass/fail)");
    }
    return true;
}

/* ============================== TEST RUNNER ============================== */
typedef bool (*test_fn)(i2c_master_dev_handle_t);
typedef struct { const char *name; test_fn fn; bool slow; } entry_t;

static const entry_t TESTS[] = {
    { "address_ack",        test_address_ack,        false },
    { "read_returns_data",  test_read_returns_data,  false },
    { "wrong_address",      test_wrong_address,      false },
    { "write_readback",     test_write_readback,     false },
    { "write_then_read",    test_write_then_read,    false },
    { "bulk_write",         test_bulk_write,         false },
    { "bulk_read",          test_bulk_read,          false },
    { "address_decoding",   test_address_decoding,   false },
    { "unmapped_address",   test_unmapped_address,   false },
    { "block_b_read_only",  test_block_b_read_only,  false },
    { "signature",          test_signature,          false },
    { "lfsr_is_active",     test_lfsr_is_active,      true  },
    { "block_a_stable",     test_block_a_stable,      true  },
    { "bulk_read_stress",   test_bulk_read_stress,    true  },
    { "mixed_stress",       test_mixed_stress,        true  },
};
#define N_TESTS (sizeof(TESTS) / sizeof(TESTS[0]))

static void run_suite(i2c_master_dev_handle_t dev, const char *label, bool include_slow)
{
    ESP_LOGI(TAG, "=== Suite @ %s%s ===", label, include_slow ? " (incl. extended)" : "");
    for (size_t i = 0; i < N_TESTS; i++) {
        if (TESTS[i].slow && !include_slow) continue;
        bool pass = TESTS[i].fn(dev);
        if (pass) { g_pass++; ESP_LOGI(TAG, "  [PASS] %s", TESTS[i].name); }
        else      { g_fail++; ESP_LOGE(TAG, "  [FAIL] %s", TESTS[i].name); }
    }
}

void app_main(void)
{
    i2c_master_bus_config_t bus_cfg = {
        .clk_source                   = I2C_CLK_SRC_DEFAULT,
        .i2c_port                     = I2C_NUM_0,
        .scl_io_num                   = I2C_SCL_GPIO,
        .sda_io_num                   = I2C_SDA_GPIO,
        .glitch_ignore_cnt            = 7,
        .flags.enable_internal_pullup = true,   /* weak; external 4.7k recommended */
    };
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &bus));

    for (size_t i = 0; i < N_SPEEDS; i++) {
        i2c_device_config_t dc = {
            .dev_addr_length = I2C_ADDR_BIT_LEN_7,
            .device_address  = DEVICE_ADDR,
            .scl_speed_hz    = SPEEDS[i].hz,
        };
        ESP_ERROR_CHECK(i2c_master_bus_add_device(bus, &dc, &dev_at[i]));
    }

    uint32_t run = 0;
    while (1) {
        g_pass = g_fail = 0;
        ESP_LOGI(TAG, "########## RUN %lu ##########", (unsigned long)++run);
        for (size_t i = 0; i < N_SPEEDS; i++) {
            // bool include_slow = (i == 1);   /* extended tests only at 400 kHz */
            bool include_slow = true;   // extended tests at every speed
            run_suite(dev_at[i], SPEEDS[i].name, include_slow);
        }
        ESP_LOGI(TAG, "########## SUMMARY: %d passed, %d failed ##########", g_pass, g_fail);
        vTaskDelay(pdMS_TO_TICKS(OUTER_DELAY_MS));
    }
}