# Protocol conformance validations
### REQ-001: Device address acknowledgement
<a name="req-001"></a>
The slave shall acknowledge a valid 7-bit device address (0x55) by driving SDA low during the ninth SCL clock pulse of the address byte, for both read and write transactions.  
**Validated by:** [TC-001](verification_report.md#TC-001), [TC-002](verification_report.md#TC-002), [TC-004](verification_report.md#TC-004)

### REQ-002: Foreign address rejection
<a name="req-002"></a>
The slave shall not acknowledge any device address other than 0x55. SDA shall remain released (high via pull-up) during the ninth SCL pulse, and the slave shall return to its idle state.  
**Validated by:** [TC-003](verification_report.md#TC-003)

### REQ-003: START condition detection
<a name="req-003"></a>
The slave shall detect a START condition (falling edge on SDA while SCL is high) at any point during operation and begin sampling the subsequent address byte.  
**Validated by:** (to be assigned)

### REQ-004: STOP condition returns to idle
<a name="req-004"></a>
The slave shall detect a STOP condition (rising edge on SDA while SCL is high) and return its internal state machine to the idle state, releasing the bus and resetting the register address pointer to zero.  
**Validated by:** [TC-004](verification_report.md#TC-004), [TC-005](verification_report.md#TC-005)

### REQ-005: Repeated START handling
<a name="req-005"></a>
The slave shall correctly process a repeated START condition (a new START without a preceding STOP), re-entering the address phase while preserving the previously set register address pointer.  
**Validated by:** [TC-005](verification_report.md#TC-005)

### REQ-006: Read/write direction bit
<a name="req-006"></a>
The slave shall interpret the least significant bit of the address byte as the direction bit: 0 selects a write transaction (master sends register index and data), 1 selects a read transaction (slave outputs register data).  
**Validated by:** [TC-001](verification_report.md#TC-001), [TC-002](verification_report.md#TC-002), [TC-004](verification_report.md#TC-004)

### REQ-007: Clock speed range
<a name="req-007"></a>
The slave shall operate correctly at the three standard I2C bus speeds: Standard Mode (100 kHz), Fast Mode (400 kHz), and Fast Mode Plus (1 MHz), given a system clock of 25 MHz.  
**Validated by:** [TC-000a](verification_report.md#TC-000a)

---

# Register architecture
### REQ-008: Register block address ranges
<a name="req-008"></a>
The design shall expose two register blocks at disjoint address ranges: Block A at register addresses 0x00–0x07 (8 registers) and Block B at 0x08–0x0F (8 registers). Each register shall be 8 bits wide.  
**Validated by:** [TC-008](verification_report.md#TC-008)

### REQ-009: Write to addressed register
<a name="req-009"></a>
On a write transaction targeting a register in Block A, the slave shall store the received data byte in the register identified by the preceding register-index byte.  
**Validated by:** [TC-004](verification_report.md#TC-004), [TC-005](verification_report.md#TC-005), [TC-006](verification_report.md#TC-006)

### REQ-010: Register address auto-increment
<a name="req-010"></a>
During a multi-byte (bulk) transaction, the register address pointer shall increment by one after each data byte, so that consecutive bytes are written to or read from consecutive register addresses.  
**Validated by:** [TC-006](verification_report.md#TC-006), [TC-007](verification_report.md#TC-007)

### REQ-011: Read from addressed register
<a name="req-011"></a>
On a read transaction, the slave shall output the contents of the register identified by the current register address pointer, most-significant-bit first.  
**Validated by:** [TC-002](verification_report.md#TC-002), [TC-005](verification_report.md#TC-005), [TC-007](verification_report.md#TC-007)

### REQ-012: Block B is read-only from the master
<a name="req-012"></a>
The slave shall not allow a master write transaction to modify any register in Block B. A write attempt targeting a Block B address shall be acknowledged on the bus but shall have no effect on the register contents.
(Block B represents sensor data fed internally by the LFSR. The master may read but not overwrite it)  
**Validated by:** [TC-008](verification_report.md#TC-008), [TC-010](verification_report.md#TC-010)

### REQ-013: Unmapped address — no write effect
<a name="req-013"></a>
A write transaction targeting a register address outside both block ranges (0x10–0xFF) shall be acknowledged on the bus but shall not modify any register in either block.  
**Validated by:** [TC-009](verification_report.md#TC-009)

### REQ-014: Unmapped address — read returns zero
<a name="req-014"></a>
A read transaction from an unmapped register address shall return 0x00, as a consequence of each unselected register block outputting zero and the outputs being combined by an OR reduction.  
**Validated by:** [TC-009](verification_report.md#TC-009)

---

# LFSR (pseudo) random number generation
### REQ-016: LFSR drives Block B with pseudo-random data
<a name="req-016"></a>
An internal LFSR module shall continuously generate pseudo-random 8-bit values and write them into the registers of Block B, simulating an autonomous sensor data source. The master shall observe changing values when reading Block B over time.
Rationale: Provides a self-contained, observable "sensor" without requiring external stimulus.  
**Validated by:** [TC-011](verification_report.md#TC-011), [TC-014](verification_report.md#TC-014)

---

# Robustness
### REQ-017: State recovery after every transaction
<a name="req-017"></a>
After completing any transaction — single or bulk, read or write, terminated by STOP or NACK — the slave shall return to the idle state and be ready to process the next transaction without requiring a reset.  
**Validated by:** [TC-014](verification_report.md#TC-014), [TC-015](verification_report.md#TC-015)

### REQ-018: Consistency under repeated bulk reads
<a name="req-018"></a>
The slave shall handle repeated bulk read transactions over an extended period without loss of consistency: every transaction shall complete correctly, return plausible data, and leave the slave ready for the next access.  
**Validated by:** [TC-014](verification_report.md#TC-014)
