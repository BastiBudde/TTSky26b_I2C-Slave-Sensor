![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# I2C Slave Template with Emulated Sensor

A I2C slave peripheral that emulates a sensor, designed as a reusable template for a real I2C sensor frontend. Built for and submitted in shuttle [Tiny Tapeout GF 26b](https://app.tinytapeout.com/shuttles/ttgf26b).

- [Read the project datasheet](docs/info.md)

## Overview

The design is a synchronous I2C slave (device address `0x55`) operating across all three standard bus speeds - Standard Mode (100 kHz), Fast Mode (400 kHz) and Fast Mode Plus (1 MHz) - with a 25 MHz system clock. It exposes two register banks of eight 8-bit registers:

- **Block A (`0x00`-`0x07`)** - master read/write. Configuration registers; a placeholder for the configuration interface a real sensor would expose.
- **Block B (`0x08`-`0x0F`)** - master read-only. Driven by an internal LFSR that cyclically updates each register with pseudo-random values, emulating changing sensor data.

A constant device signature is available at `0xF8`-`0xFF`. Unmapped reads return `0x00`; writes to read-only or unmapped addresses are acknowledged but have no effect.

Replacing the LFSR with a real sensor frontend turns the design into a functional I2C sensor - that is the template idea.

## Pinout

| Pin | Function |
|---|---|
| `uio[0]` | SCL (I2C clock) |
| `uio[3]` | SDA (I2C data) |

External pull-up resistors (e.g. 4.7 kΩ to 3.3 V) are required on SCL and SDA.

## How to test

The device responds at 7-bit I2C address `0x55`. To read a register, write the register index, then issue a repeated START and read one or more bytes (the pointer auto-increments for bulk reads). To write Block A, send the register index followed by data bytes.

The design was verified in simulation (cocotb) and on hardware using a Sipeed Tang Primer 25K FPGA with an ESP32-C6 as I2C master, running a test suite at all three bus speeds. See the [FPGA test report](test/fpga/fpga_test_report.md) and the [verification documents](docs/) for details.

## Repository structure

- `src/` - the Verilog design source
- `docs/info.md` - project datasheet
- `docs/specification.md`, `docs/validation.md`, `docs/verification_report.md` - requirements, validation and verification
- `docs/fpga_report.md` - Test report for fpga 
- `test/` - cocotb testbench
- `test/fpga/` - FPGA project and the ESP32-C6 hardware test firmware

## About Tiny Tapeout

Tiny Tapeout is an educational project that makes it easier and cheaper than ever to get your digital and analog designs manufactured on a real chip. To learn more and get started, visit https://tinytapeout.com.

### Resources

- [FAQ](https://tinytapeout.com/faq/)
- [Digital design lessons](https://tinytapeout.com/digital_design/)
- [Learn how semiconductors work](https://tinytapeout.com/siliwiz/)
- [Join the community](https://tinytapeout.com/discord)