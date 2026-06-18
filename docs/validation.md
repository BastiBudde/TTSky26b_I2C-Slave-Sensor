# Validation Document

## Protocol conformance

### VAL-001: Device address acknowledgement
<a name="val-001"></a>
**Validates:** [REQ-001](specification.md#req-001)
**Method:** Simulation; an I2C master transmits the device address 0x55 with both direction bits and the slave's SDA line is observed during the ninth SCL pulse.
**Acceptance criterion:** For an address byte equal to 0x55, the slave drives SDA low (ACK) during the ninth SCL pulse, for both the write (LSB = 0) and the read (LSB = 1) framing, at all three bus speeds.
**Verified by:** [TC-001](verification_report.md#TC-001), [TC-002](verification_report.md#TC-002), [TC-004](verification_report.md#TC-004)

### VAL-002: Foreign address rejection
<a name="val-002"></a>
**Validates:** [REQ-002](specification.md#req-002)
**Method:** Simulation; the master transmits a representative set of non-matching addresses, including the single-bit neighbours 0x54 and 0x56, and the slave response is observed.
**Acceptance criterion:** For every transmitted address other than 0x55, SDA remains released (no ACK) during the ninth SCL pulse and the slave stays in its idle state. Pass requires zero false ACKs across the tested addresses and all three speeds.
**Verified by:** [TC-003](verification_report.md#TC-003)

### VAL-003: START condition detection
<a name="val-003"></a>
**Validates:** [REQ-003](specification.md#req-003)
**Method:** Simulation; a START (SDA falling while SCL high) is issued and the slave's subsequent address sampling is observed. START detection is a precondition for any successful transaction, so it is exercised implicitly by every test that achieves an address ACK.
**Acceptance criterion:** After a START condition, the slave begins sampling the address byte such that a following valid 0x55 address is acknowledged. Pass requires that at least one transaction-based test achieves an address ACK; failure to detect START would make every transaction fail.
**Verified by:** Implicitly covered by [TC-001](verification_report.md#TC-001) (and every transaction-based test case). A dedicated test case is recommended but not required for coverage.

### VAL-004: STOP condition returns to idle
<a name="val-004"></a>
**Validates:** [REQ-004](specification.md#req-004)
**Method:** Simulation; a transaction is terminated with a STOP and the slave's readiness for a fresh transaction, together with the reset of the register pointer to zero, is observed.
**Acceptance criterion:** After a STOP, the slave is ready to process a new transaction from a defined state and the register address pointer has been reset to zero, demonstrated by a subsequent transaction behaving as if started from idle. Pass requires correct behaviour at all three speeds.
**Verified by:** [TC-004](verification_report.md#TC-004), [TC-005](verification_report.md#TC-005)

### VAL-005: Repeated START handling
<a name="val-005"></a>
**Validates:** [REQ-005](specification.md#req-005)
**Method:** Simulation; the master sets the register pointer with a write, then issues a repeated START (no intervening STOP) into a read and observes the returned data.
**Acceptance criterion:** A read performed via repeated START after setting the pointer returns the data at the previously set index, proving the pointer is preserved across the repeated START. Pass requires the read-back value to equal the value stored at the set index, at all three speeds.
**Verified by:** [TC-005](verification_report.md#TC-005)

### VAL-006: Read/write direction bit
<a name="val-006"></a>
**Validates:** [REQ-006](specification.md#req-006)
**Method:** Simulation; transactions are issued with the address LSB set to 0 and to 1, and the resulting framing (write versus read) is observed.
**Acceptance criterion:** With LSB = 0 the slave accepts an index and data byte (write framing); with LSB = 1 the slave drives register data onto SDA (read framing). Pass requires both directions to behave correctly at all three speeds.
**Verified by:** [TC-001](verification_report.md#TC-001), [TC-002](verification_report.md#TC-002), [TC-004](verification_report.md#TC-004)

### VAL-007: Clock speed range
<a name="val-007"></a>
**Validates:** [REQ-007](specification.md#req-007)
**Method:** Simulation; the entire functional test suite is parametrized over the three standard bus speeds with a 25 MHz system clock.
**Acceptance criterion:** Every functional test case passes when executed at 100 kHz, 400 kHz and 1 MHz. Pass requires a fully green functional suite at each of the three speeds.
**Verified by:** [TC-000a](verification_report.md#TC-000a)

---

## Register architecture

### VAL-008: Register block address ranges
<a name="val-008"></a>
**Validates:** [REQ-008](specification.md#req-008)
**Method:** Simulation; reads and writes are directed at addresses spanning both blocks, including the 0x07/0x08 boundary, and the targeted block is identified by the observable effect.
**Acceptance criterion:** Accesses to 0x00–0x07 affect only Block A and accesses to 0x08–0x0F affect only Block B, with each register being 8 bits wide and the block boundary at 0x07/0x08 correctly separated. Pass requires correct decoding with no cross-block leakage.
**Verified by:** [TC-008](verification_report.md#TC-008)

### VAL-009: Write to addressed register
<a name="val-009"></a>
**Validates:** [REQ-009](specification.md#req-009)
**Method:** Simulation; a known byte is written to a Block A index and subsequently read back from the same index.
**Acceptance criterion:** A byte written to Block A index N is retrievable unchanged from index N. Pass requires the read-back value to equal the written value at all three speeds.
**Verified by:** [TC-004](verification_report.md#TC-004), [TC-005](verification_report.md#TC-005), [TC-006](verification_report.md#TC-006)

### VAL-010: Register address auto-increment
<a name="val-010"></a>
**Validates:** [REQ-010](specification.md#req-010)
**Method:** Simulation; a multi-byte bulk write followed by a multi-byte bulk read is performed from a single start index, using deliberately distinct values so any shift or duplication is detectable.
**Acceptance criterion:** In a K-byte bulk transaction from start index N, byte i is written to / read from index N+i. Pass requires the read-back sequence to match the written sequence in order and position, at all three speeds.
**Verified by:** [TC-006](verification_report.md#TC-006), [TC-007](verification_report.md#TC-007)

### VAL-011: Read from addressed register
<a name="val-011"></a>
**Validates:** [REQ-011](specification.md#req-011)
**Method:** Simulation; a known value is stored at an index and read back; correct byte value confirms most-significant-bit-first transmission.
**Acceptance criterion:** A read from index N returns the stored content of N. Pass requires the read-back value to equal the stored value (a wrong bit order would corrupt the value), at all three speeds.
**Verified by:** [TC-002](verification_report.md#TC-002), [TC-005](verification_report.md#TC-005), [TC-007](verification_report.md#TC-007)

### VAL-012: Block B is read-only from the master
<a name="val-012"></a>
**Validates:** [REQ-012](specification.md#req-012)
**Method:** Simulation; the master attempts to write a sentinel value to a Block B address and the register content is read back.
**Acceptance criterion:** A write to a Block B address is acknowledged on the bus but the attempted sentinel value does not become the persistent register content (Block B remains governed by the LFSR). Pass requires the read-back value not to equal the written sentinel as a persistent result.
**Verified by:** [TC-008](verification_report.md#TC-008), [TC-010](verification_report.md#TC-010)

### VAL-013: Unmapped address — no write effect
<a name="val-013"></a>
**Validates:** [REQ-013](specification.md#req-013)
**Method:** Simulation; a reference register is written, a write to an unmapped address (0x10–0xFF) is attempted, and the reference register is re-read.
**Acceptance criterion:** A write to an unmapped address is acknowledged on the bus but no mapped register changes. Pass requires the reference register to retain its value after the unmapped write.
**Verified by:** [TC-009](verification_report.md#TC-009)

### VAL-014: Unmapped address — read returns zero
<a name="val-014"></a>
**Validates:** [REQ-014](specification.md#req-014)
**Method:** Simulation; a read is issued from an unmapped address and the returned byte is observed.
**Acceptance criterion:** A read from any unmapped address returns 0x00. Pass requires the returned byte to equal 0x00.
**Verified by:** [TC-009](verification_report.md#TC-009)

---

## LFSR (pseudo) random number generation

### VAL-016: LFSR drives Block B with pseudo-random data
<a name="val-016"></a>
**Validates:** [REQ-016](specification.md#req-016)
**Method:** Simulation; a fixed Block B register is read repeatedly over an observation window longer than the per-register update period, and the sampled values are compared.
**Acceptance criterion:** Over at least four samples spaced beyond the update period, the read values of a fixed Block B register take at least two distinct values, demonstrating an active, changing source. Pass requires at least two distinct values.
**Verified by:** [TC-011](verification_report.md#TC-011), [TC-014](verification_report.md#TC-014)

---

## Robustness

### VAL-017: State recovery after every transaction
<a name="val-017"></a>
**Validates:** [REQ-017](specification.md#req-017)
**Method:** Simulation; extended mixed sequences of single and bulk, read and write transactions (terminated by STOP and by NACK) are issued, and the slave's readiness for each following transaction is observed.
**Acceptance criterion:** After every transaction, regardless of type or termination, the slave processes the next transaction without requiring a reset. Pass requires every transaction in a long mixed/stress sequence to be acknowledged and to complete correctly.
**Verified by:** [TC-014](verification_report.md#TC-014), [TC-015](verification_report.md#TC-015)

### VAL-018: Consistency under repeated bulk reads
<a name="val-018"></a>
**Validates:** [REQ-018](specification.md#req-018)
**Method:** Simulation; at least twenty repeated bulk read transactions are performed over an extended period, and each transaction's completion and data plausibility are checked.
**Acceptance criterion:** Across at least twenty repeated bulk reads, every transaction completes correctly, returns in-range (8-bit) data, leaves the slave ready for the next access, and shows per-address-slot value variation over time. Pass requires all iterations to be valid and variation to be observed.
**Verified by:** [TC-014](verification_report.md#TC-014)
