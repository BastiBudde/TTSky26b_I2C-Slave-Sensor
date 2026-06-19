# FPGA Test Report — TSky26b I2C Slave

## 1. Purpose and scope

This report documents the **hardware bring-up and functional testing** of the design on a physical FPGA, as a complement to the simulation results in [verification_report.md](verification_report.md). The goal is to confirm that the synthesised design behaves on real hardware as it does in RTL and gate-level simulation, exercised over the actual I2C bus by an independent microcontroller acting as bus master.

Because there is no internal signal visibility on the FPGA, all checks are **black-box** observations over the I2C bus. This is the same approach used for the gate-level simulation. White-box assertions from the cocotb suite (internal state, register inspection) are therefore not part of this hardware report.

## 2. Device under test

Device I2C address: ```0x55``` (7-bit).

Register map:  
| Address range | Block | Access |
|---|---|---|
| 0x00–0x07 | Block A (general registers) | Master read/write |
| 0x08–0x0F | Block B (LFSR pseudo-random) | Master read-only |
| 0xF8–0xFF | Signature ("SBJS2026") | Read-only constant |
| all others | unmapped | write ACKed-but-ignored, read returns 0x00 |



## 3. Test setup

### 3.1 FPGA board and toolchain

| Item | Detail |
|---|---|
| FPGA board | Sipeed Tang Primer 25K |
| FPGA device | Gowin Arora V GW5A-25 `GW5A-LV25MG121NC1/I0` |
| Synthesis / P&R IDE | Gowin FPGA Designer `Version V1.9.11.03 Education build(81398)` |
| FPGA project location | [test/fpga/Tang_Primer_25k_fpga_project](/test/fpga/Tang_Primer_25k_fpga_project) |
| System clock | `50 MHz` (note: the LFSR update period scales with this clock) |

To open and build the design: launch Gowin FPGA Designer, open the project under `test/fpga/Tang_Primer_25k_fpga_project`. The SDA and SCL bidirectional ports habe been mapped to the boards pins `K1` and `K2`. Internal pull-ups have been activated. The rst_n input of the slave design was mapped to the boards pin `H11` as it is connected to a push button. The pin mapping and configuration can be seen and changed in the file test/fpga/Tang_Primer_25k_fpga_project/src/physical_constraint.cst. When everything is configured as desired synthesise, place-and-route and generate the bitstream. 
Then connect Tang Primer 25K over its onboard USB-C connector (USB-JTAG) to the pc. From within GOWIN FPGA Desinger open the Programmer via the ```Programmer``` button. In the ```Cable Settings```-menu make the following settings and save:
- Cable: `USB Debugger A`
- Port: `USB Debugger A/0/null`
- Frequency: `15 MHz`
  
Then right click on the device entry in the Programmer window and choose ```Configure Device```. In the new window make these settings and save:
- Access Mode: `External Flash Mode 5A`
- Operation: `exFlash Background Erase, Program, Verify 5A`
- Device: `Generic Flash`
- Start Address: `0x000000`


<!-- Optionally note here the clock pin and reset pin assignments that were
     resolved during bring-up. -->

### 3.2 I2C master (microcontroller)

| Item | Detail |
|---|---|
| Microcontroller | Espressif ESP32-C6 (DevKitC-1) |
| Framework | ESP-IDF `Version >= 5.5.2 ` |
| IDE | Visual Studio Code with the ESP-IDF extension |
| Firmware project location | `test/fpga/ESP32_C6_fpga_test` |
| Serial monitor | 115200 baud over USB |

The firmware (`main.c`) reproduces the black-box test cases of the cocotb suite as a self-contained, repeating regression. It is built and flashed natively with ESP-IDF (`idf.py set-target esp32c6`, `idf.py build flash monitor`).

### 3.3 Bus wiring

| Signal | ESP32-C6 GPIO | FPGA pin | Notes |
|---|---|---|---|
| SCL | `GPIO 7` | `K2` | external pull-up `[e.g. 4.7 kΩ to 3.3 V]` |
| SDA | `GPIO 7` | `K1` | external pull-up `[e.g. 4.7 kΩ to 3.3 V]` |
| GND | GND | GND | common ground required |

External pull-ups are recommended over the ESP32-C6's weak internal pull-ups, especially for reliable operation at 1 MHz.

### 3.4 Instrumentation

| Instrument | Use |
|---|---|
| Rigol MSO5074 mixed-signal oscilloscope | Capture SCL/SDA waveforms and I2C protocol decode |
| Sensepeek PCBITE SQ200 probes | 200 MHz max. hands-free oscilloscope probes for SCL/SDA |

## 4. Firmware test description

The firmware runs the full suite at three bus speeds (100 kHz, 400 kHz, 1 MHz). The suite repeats continuously with a pass/fail summary per run. The individual tests and the requirements they exercise on hardware resemble the cocotb testcases:

| Firmware test | Exercises | Requirement |
|---|---|---|
| `address_ack` | address ACK for 0x55 | [REQ-001](specification.md#req-001), [REQ-006](specification.md#req-006) |
| `read_returns_data` | read path returns a byte | [REQ-011](specification.md#req-011) |
| `wrong_address` | foreign addresses NACKed | [REQ-002](specification.md#req-002) |
| `write_readback` | write then read back | [REQ-009](specification.md#req-009) |
| `write_then_read` | write, STOP, read back | [REQ-009](specification.md#req-009), [REQ-011](specification.md#req-011) |
| `bulk_write` | bulk write, auto-increment | [REQ-010](specification.md#req-010) |
| `bulk_read` | bulk read, auto-increment | [REQ-010](specification.md#req-010), [REQ-011](specification.md#req-011) |
| `address_decoding` | A/B block isolation | [REQ-008](specification.md#req-008) |
| `unmapped_address` | unmapped write/read behaviour | [REQ-013](specification.md#req-013), [REQ-014](specification.md#req-014) |
| `block_b_read_only` | Block B rejects writes | [REQ-012](specification.md#req-012) |
| `signature` | constant signature read-back | device identification (0xF8–0xFF) |
| `lfsr_is_active` | Block B changes over time | [REQ-016](specification.md#req-016) |
| `block_a_stable` | Block A untouched by LFSR | [REQ-008](specification.md#req-008) |
| `bulk_read_stress` | repeated bulk reads consistent | [REQ-018](specification.md#req-018) |
| `mixed_stress` | state recovery over mixed ops | [REQ-017](specification.md#req-017) |

The full firmware source is in `test/fpga/ESP32_C6_fpga_test/main/main.c`.

## 5. Test execution

1. Synthesise and program the FPGA from the Gowin project ([Section 3.1](#31-fpga-board-and-toolchain)).
2. Wire the ESP32-C6 to the FPGA and add bus pull-ups ([Section 3.3](#31-fpga-board-and-toolchain)).
3. Build and flash the firmware with ESP-IDF. Then open the serial monitor.
4. Observe the per-run pass/fail summary and capture bus waveforms with the oscilloscope at each speed as needed.

## 6. Results

### 6.1 Serial log

The firmware reports a per-run summary. A representative run:

```
I (34712) i2c_suite: ########## RUN 42 ##########
I (34712) i2c_suite: === Suite @ 100kHz (incl. extended) ===
I (34712) i2c_suite:   [PASS] address_ack
I (34712) i2c_suite:   [PASS] read_returns_data
I (34712) i2c_suite:   [PASS] wrong_address
I (34722) i2c_suite:   [PASS] write_readback
I (34722) i2c_suite:   [PASS] write_then_read
I (34732) i2c_suite:   [PASS] bulk_write
I (34732) i2c_suite:   [PASS] bulk_read
I (34742) i2c_suite:   [PASS] address_decoding
I (34742) i2c_suite:   [PASS] unmapped_address
I (34742) i2c_suite:   [PASS] block_b_read_only
I (34742) i2c_suite:     signature bytes: 53 42 4A 53 32 30 32 36
I (34752) i2c_suite:     signature ascii: SBJS2026
I (34752) i2c_suite:   [PASS] signature
I (34792) i2c_suite:   [PASS] lfsr_is_active
I (34792) i2c_suite:   [PASS] block_a_stable
I (34812) i2c_suite:   [PASS] bulk_read_stress
I (34822) i2c_suite:   [PASS] mixed_stress
I (34822) i2c_suite: === Suite @ 400kHz (incl. extended) ===
I (34822) i2c_suite:   [PASS] address_ack
I (34822) i2c_suite:   [PASS] read_returns_data
I (34832) i2c_suite:   [PASS] wrong_address
I (34832) i2c_suite:   [PASS] write_readback
I (34842) i2c_suite:   [PASS] write_then_read
I (34842) i2c_suite:   [PASS] bulk_write
I (34842) i2c_suite:   [PASS] bulk_read
I (34852) i2c_suite:   [PASS] address_decoding
I (34852) i2c_suite:   [PASS] unmapped_address
I (34862) i2c_suite:   [PASS] block_b_read_only
I (34862) i2c_suite:     signature bytes: 53 42 4A 53 32 30 32 36
I (34872) i2c_suite:     signature ascii: SBJS2026
I (34872) i2c_suite:   [PASS] signature
I (34902) i2c_suite:   [PASS] lfsr_is_active
I (34902) i2c_suite:   [PASS] block_a_stable
I (34902) i2c_suite:   [PASS] bulk_read_stress
I (34912) i2c_suite:   [PASS] mixed_stress
I (34912) i2c_suite: === Suite @ 1MHz (incl. extended) ===
I (34912) i2c_suite:   [PASS] address_ack
I (34912) i2c_suite:   [PASS] read_returns_data
I (34912) i2c_suite:   [PASS] wrong_address
I (34922) i2c_suite:   [PASS] write_readback
I (34922) i2c_suite:   [PASS] write_then_read
I (34932) i2c_suite:   [PASS] bulk_write
I (34932) i2c_suite:   [PASS] bulk_read
I (34932) i2c_suite:   [PASS] address_decoding
I (34942) i2c_suite:   [PASS] unmapped_address
I (34942) i2c_suite:   [PASS] block_b_read_only
I (34952) i2c_suite:     signature bytes: 53 42 4A 53 32 30 32 36
I (34952) i2c_suite:     signature ascii: SBJS2026
I (34962) i2c_suite:   [PASS] signature
I (34992) i2c_suite:   [PASS] lfsr_is_active
I (34992) i2c_suite:   [PASS] block_a_stable
I (34992) i2c_suite:   [PASS] bulk_read_stress
I (34992) i2c_suite:   [PASS] mixed_stress
I (34992) i2c_suite: ########## SUMMARY: 45 passed, 0 failed ##########
```

**Result: 45 of 45 checks passed**, with the signature reading `SBJS2026` identically at all three bus speeds. 

### 6.2 Oscilloscope captures

<!-- Place image files under test/fpga/.../images/ and reference them. -->

![Address byte and ACK at 100 kHz](/docs/img/fpga/scope_ack_100k.png)
*Figure 1: Device address 0x55 + WRITE followed by the slave ACK (SDA pulled low on the ninth SCL pulse) at 100 kHz.*

![Bulk read at 400 kHz](/docs/img/fpga/scope_bulk_read_400k.png)
*Figure 2: Auto-incremented bulk read of Block B at 400 kHz.*

![Bulk write at 1 MHz](/docs/img/fpga/scope_bulk_write_1M.png)
*Figure 3:Auto-incremented bulk write of Block B at 1 MHz, confirming signal integrity at the highest specified speed.*

### 6.3 Test setup photos / video

![Test bench overview](/docs/img/fpga/bench_setup.png)
*Figure 4: Test bench — Tang Primer 25K, ESP32-C6, Rigol MSO5074, Sensepeek PCBITE SQ200 probes.*

Video of a live test run: 
[bench_setup.gif](/docs/img/fpga/bench_setup.gif)


## 7. Conclusion

The synthesised I2C slave design operates correctly on the Sipeed Tang Primer 25K across all three specified bus speeds, with every black-box check passing and the device signature read back intact. The hardware behaviour is consistent with the RTL and gate-level simulation results, providing confidence that the design is ready for tape-out submission.
