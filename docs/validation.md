# Validation document


---

## Protocol conformance validations
### VAL-001 - [REQ-001](specification.md#req-001) - Device address acknowledgement
<a name="val-001"></a>
The requirement names everything needed to test it without interpretation: the 7-bit address `0x55`, the exact ninth SCL pulse, and the SDA-low acknowledgement level, which makes it both specific and directly measurable by observing the bus. The specifiaction is relevant because it captures the fundamental handshake of a I2C transaction. Describing the acknowledgement once for both read and write keeps it as a single coherent function.  

### VAL-002 - [REQ-002](specification.md#req-002) - Foreign address rejection
<a name="val-002"></a>
By fixing the one accepted address and prescribing that SDA stays released on the ninth pulse for everything else, the requirement is concrete enough to be checked by bus observation. Returning to idle is part of the same rejection response. The specification is relevant so that coexisting cleanly with other devices on a shared bus is possible.  

### VAL-003 - [REQ-003](specification.md#req-003) - START condition detection
<a name="val-003"></a>
The trigger is defined as a falling edge on SDA while SCL is high. Because correct detection is confirmed through the address sampling that immediately follows, it is verifiable in simulation. The specification is relevant because the START condition is the entry-point function on which every transaction depends.  

### VAL-004 - [REQ-004](specification.md#req-004) - STOP returns to idle
<a name="val-004"></a>
This requirement specifies the response to a STOP condition in concrete terms. Returning to idle, releasing the bus, and clearing the pointer are each observable in simulation, so it is fully measurable.  The specification is needed for a clean transaction boundary and can be verified by simulation at low cost.

### VAL-005 - [REQ-005](specification.md#req-005) - Repeated START handling
<a name="val-005"></a>
The requirement describes the scenario of a new START with no preceding STOP. It states exactly what must happen: re-entering the address phase while the register pointer is preserved. That makes it measurable directly by confirming the pointer survives the repeated START, and it reflects a common I2C use case where a master switches from writing an index to reading. It is realistic to implement and test in the available timeframe.

### VAL-006 - [REQ-006](specification.md#req-006) - Read/write direction bit
<a name="val-006"></a>
The least significant bit of the address byte selects write or read. That leaves no room for interpretation and is measurable by exercising both polarities. It addresses exactly one function and is central to every transaction.

### VAL-007 - [REQ-007](specification.md#req-007) - Clock speed range
<a name="val-007"></a>
The requirement is anchored to three concrete, standardised bus speeds and a defined 25 MHz system clock, which makes its scope specific and the success condition easy to confirm by running full transactions at each speed. It targets the supported speed range as a single performance characteristic. That is directly relevant to real-world interoperability, and all three speeds are realistically attainable on the target technology within the project budget.

---

## Register architecture

### VAL-008 - [REQ-008](specification.md#req-008) - Register block address ranges
<a name="val-008"></a>
The two address ranges (`0x00`–`0x07` and `0x08`–`0x0F`) and the 8-bit register width are all given as exact figures, so the register map is fully specified. This makes it easy to confirm by reading across the full range. Defining the two blocks together is appropriate because they form one memory-map that the rest of the design builds on, and that map is clearly relevant.

### VAL-009 - [REQ-009](specification.md#req-009) - Write to addressed register
<a name="val-009"></a>
This requirement describes a single, clearly bounded action by storing the received byte at the register named by the preceding index. This makes it directly measurable through a write followed by a read-back. It is core to the write path and achievable.

### VAL-010 - [REQ-010](specification.md#req-010) - Register address auto-increment
<a name="val-010"></a>
The increment-by-one-after-each-byte rule is stated precisely and concerns exactly one behaviour, which makes it both specific and independently testable by writing or reading a sequence and checking the addressing. It is exactly what bulk transfers need, so its relevance is clear.

### VAL-011 - [REQ-011](specification.md#req-011) - Read from addressed register
<a name="val-011"></a>
By naming both the source register (the one at the current pointer) and the bit order (most significant first), the requirement is concrete and objectively checkable against a known value. Register selection and bit ordering together form one read operation, so it reads as a single function, and it is plainly relevant.

### VAL-012 - [REQ-012](specification.md#req-012) - Block B is read-only
<a name="val-012"></a>
The requirement states a single behaviour: a Block B write is acknowledged but leaves the contents untouched. This can be measured directly both on the bus and in the register state. The behaviour is straightforward to implement and test within scope.

### VAL-013 - [REQ-013](specification.md#req-013) - Unmapped address, no write effect
<a name="val-013"></a>
With the unmapped range (`0x10`–`0xF7`) and the expected outcome stated exactly, this requirement gives an objective pass/fail criterion and covers one case. It is relevant to safe operation.

### VAL-014 - [REQ-014](specification.md#req-014) - Unmapped address, read returns zero
<a name="val-014"></a>
The requirement is specific and directly measurable: a read from any unmapped address must return `0x00`, which is trivial to confirm. The behaviour is relevant and achievable.

---

## LFSR (pseudo) random number generation

### VAL-016 - [REQ-016](specification.md#req-016) - LFSR drives Block B
<a name="val-016"></a>
This requirement captures one coherent feature. An internal LFSR that continuously supplies Block B with values, emulating a live sensor without external stimulus. It provides a useful, self-contained stimulus source, which makes it relevant for simulating a simple sensor, and it is realistic to build within the project.

---

## Robustness

### VAL-017 - [REQ-017](specification.md#req-017) - State recovery after every transaction
<a name="val-017"></a>
The requirement sets a clear, checkable expectation: after any transaction the slave returns to idle and is ready for the next one without a reset. That can be confirmed simply by probing with a follow-up transaction. Robustness of this kind is relevant for continuous operation and is achievable within the design's scope.

### VAL-018 - [REQ-018](specification.md#req-018) - Consistency under repeated bulk reads
<a name="val-018"></a>
This requirement targets sustained, repeated bulk reads and asks that each one complete correctly and leave the slave ready, which is exactly the endurance property a sensor-style interface needs. It is verifiable by running a long series of transactions and confirming consistent results. It addresses one reliability concern. The behaviour is relevant to real use and realistic to demonstrate within the project's timeframe.
