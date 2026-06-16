# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge, ReadOnly
from cocotbext.i2c import I2cMaster

import os
GATE_LEVEL = os.getenv("GATES") == "yes"

#---------------------------------------------------------------------------------
#---------------------------------- Parameters -----------------------------------
#---------------------------------------------------------------------------------
DEVICE_ADDR = 0x55

# State encoding if i2c_slave
S_IDLE     = 0
S_RCV_ADDR = 1
S_RCV_PTR  = 2
S_WRITE    = 3
S_READ     = 4

#---------------------------------------------------------------------------------
#------------------ Extending cocotbext.i2c's I2CMaster class --------------------
#---------------------------------------------------------------------------------
class I2cMasterWithAck(I2cMaster):
    """Extends I2cMaster so write() and read() return ACK information.

    Returns:
        write(): list of bools, one per byte sent (True = ACKed, False = NACKed)
        read():  tuple (data: bytearray, addr_acked: bool)
    """

    async def write(self, addr, data):
        self.log.info("Write %s to device at I2C address 0x%02x", data, addr)
        await self.send_start()
        # send_byte returns True on NACK, False on ACK — we invert to "acked"
        acks = []
        acks.append(not await self.send_byte((addr << 1) | 0))
        for b in data:
            acks.append(not await self.send_byte(b))
        return acks

    async def read(self, addr, count):
        self.log.info("Read %d bytes from device at I2C address 0x%02x", count, addr)
        await self.send_start()
        addr_acked = not await self.send_byte((addr << 1) | 1)
        data = bytearray()
        for k in range(count):
            data.append(await self.recv_byte(k == count - 1))
        return data, addr_acked


#---------------------------------------------------------------------------------
#------------------------------- Helper functions --------------------------------
#---------------------------------------------------------------------------------
async def reset_dut(dut):
    """Resetting device, making Bus idle"""
    await Timer(5000, unit="ns")
    dut.rst_n.value = 0
    dut.scl_master_drive.value = 1   # released
    dut.sda_master_drive.value = 1
    dut.ena.value = 1
    dut.ui_in.value = 0
    await Timer(5000, unit="ns")
    dut.rst_n.value = 1    
    await Timer(50000, unit="ns")
    await RisingEdge(dut.clk)

def make_master(dut, speed=400e3):
    return I2cMasterWithAck(
        sda=dut.sda_bus,                  # observed SDA
        sda_o=dut.sda_master_drive,       # master drive output
        scl=dut.scl_bus,                  # observed SCL
        scl_o=dut.scl_master_drive,       # master drive output
        speed=speed,
    )

async def read_register(master, index):
    """Set Index by write, then Repeated-START-Read one byte, then STOP."""
    await master.write(DEVICE_ADDR, [index])
    data = await master.read(DEVICE_ADDR, 1)
    await master.send_stop()
    return data[0]

def extract_reset_values(raw, n_regs=8):
    full = int(raw)
    return {i: (full >> (i * 8)) & 0xFF for i in range(n_regs)}

async def reg_write_monitor(dut, captured):
    """Background task: capture every reg_write pulse with addr and data."""
    while True:
        await RisingEdge(dut.clk)
        await ReadOnly()
        if str(dut.user_project.top_level_inst.i2c_inst.reg_write.value) == "1":
            captured.append((
                int(dut.user_project.top_level_inst.i2c_inst.reg_addr.value),
                int(dut.user_project.top_level_inst.i2c_inst.data_out.value),
            ))


#---------------------------------------------------------------------------------
#--------------------- Slave ACKing matching address + write ---------------------
#---------------------------------------------------------------------------------
@cocotb.test(skip=GATE_LEVEL)
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_write_address(dut, speed):
    """Address with write bit must be ACKed; slave enters S_RCV_PTR state."""
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    acks = await master.write(DEVICE_ADDR, [])
    assert acks[0], "Slave did not ACK its own address"

    for _ in range(5):
        await RisingEdge(dut.clk)

    state = int(dut.user_project.top_level_inst.i2c_inst.state.value)
    assert state == S_RCV_PTR, (
        f"After write address (speed={speed:.0e}), expected S_RCV_PTR "
        f"({S_RCV_PTR}), got {state}"
    )

    await master.send_stop()
    dut._log.info(f"Address ACKed at speed {speed:.0e} — passed.")


#---------------------------------------------------------------------------------
#----------------- Address match + read bit: ACK and state check -----------------
#---------------------------------------------------------------------------------
@cocotb.test(skip=GATE_LEVEL)
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_read_address(dut, speed):
    """Address with read bit must be ACKed; slave enters S_READ state."""
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    # Low-level transaction so we can check the state between two reads:
    # after the first byte the slave is guaranteed to be in S_READ (master
    # ACKed and the slave is preparing the next byte).
    await master.send_start()
    addr_nacked = await master.send_byte((DEVICE_ADDR << 1) | 1)
    assert not addr_nacked, "Slave did not ACK its own address"

    _first_byte = await master.recv_byte(False)   # ACK -> ask for another byte

    state = int(dut.user_project.top_level_inst.i2c_inst.state.value)
    assert state == S_READ, (
        f"During read transaction, expected S_READ ({S_READ}), got {state}"
    )

    _second_byte = await master.recv_byte(True)   # NACK -> end of transaction
    await master.send_stop()

    dut._log.info("Address ACKed and state correctly S_READ — passed.")


#---------------------------------------------------------------------------------
#----------------- Wrong address: no ACK, slave stays in IDLE --------------------
#---------------------------------------------------------------------------------
@cocotb.test(skip=GATE_LEVEL)
@cocotb.parametrize(wrong_addr=[0x42, 0x54, 0x56], speed=[100e3, 400e3, 1e6])
async def test_wrong_address_no_ack(dut, wrong_addr, speed):
    """Foreign address must be NACKed; slave must stay in S_IDLE."""
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    dut._log.info(f"Sending foreign address 0x{wrong_addr:02X}")
    acks = await master.write(wrong_addr, [])
    assert not acks[0], (
        f"Slave wrongly ACKed foreign address 0x{wrong_addr:02X}"
    )

    for _ in range(5):
        await RisingEdge(dut.clk)

    state = int(dut.user_project.top_level_inst.i2c_inst.state.value)
    assert state == S_IDLE, (
        f"After foreign address 0x{wrong_addr:02X}, expected S_IDLE ({S_IDLE}), "
        f"got {state}"
    )

    await master.send_stop()
    dut._log.info(f"Foreign address 0x{wrong_addr:02X} correctly NACKed; state stayed S_IDLE.")


#---------------------------------------------------------------------------------
#--------------------------- Master writes to a register -------------------------
#---------------------------------------------------------------------------------
WRITE_INDEX = 0x03
WRITE_DATA  = 0x57


@cocotb.test()
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_full_write(dut, speed):
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    # Monitor only makes sense at RTL — internal signals are gone at gate level
    captured = []
    if not GATE_LEVEL:
        cocotb.start_soon(reg_write_monitor(dut, captured))

    # Black-box: the actual transaction works the same at RTL and gate level
    acks = await master.write(DEVICE_ADDR, [WRITE_INDEX, WRITE_DATA])
    await master.send_stop()
    assert all(acks), f"Not every byte was ACKed: {acks}"

    for _ in range(5):
        await RisingEdge(dut.clk)

    # White-box checks: only at RTL
    if not GATE_LEVEL:
        assert len(captured) == 1, (
            f"Expected exactly 1 reg_write pulse, got {len(captured)}: {captured}"
        )
        addr, data = captured[0]
        dut._log.info(f"reg_write pulse: addr=0x{addr:02X}, data=0x{data:02X}")
        assert addr == WRITE_INDEX, \
            f"reg_write addr 0x{addr:02X} != expected 0x{WRITE_INDEX:02X}"
        assert data == WRITE_DATA, \
            f"reg_write data 0x{data:02X} != expected 0x{WRITE_DATA:02X}"

        reg3 = int(dut.user_project.top_level_inst.reg_block_a.registers[WRITE_INDEX].value)
        assert reg3 == WRITE_DATA, (
            f"regs[{WRITE_INDEX}] = 0x{reg3:02X}, expected 0x{WRITE_DATA:02X}"
        )

    # Black-box readback works at both RTL and gate level — add it as an
    # extra check so gate-level still verifies *something* about the write
    readback = await read_register(master, WRITE_INDEX)
    assert readback == WRITE_DATA, (
        f"Readback after write: 0x{readback:02X} != 0x{WRITE_DATA:02X}"
    )

    dut._log.info("Write transaction verified.")


#---------------------------------------------------------------------------------
#--------------- Master writes to and then reads from the slave ------------------
#---------------------------------------------------------------------------------
@cocotb.test()
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_write_then_read(dut, speed):
    """Write 0x57 to register 0, then read it back and compare."""
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    test_index = 0x00
    test_value = 0x57

    # Write transaction
    acks_write = await master.write(DEVICE_ADDR, [test_index, test_value])
    await master.send_stop()
    assert all(acks_write), f"Not every byte was ACKed during write: {acks_write}"

    # Small pause to mirror real bus traffic between transactions
    await Timer(1000, unit="ns")

    # Read transaction: set pointer, then repeated-START into read
    acks_idx = await master.write(DEVICE_ADDR, [test_index])
    assert all(acks_idx), f"Not every byte was ACKed during index phase: {acks_idx}"

    data, addr_acked = await master.read(DEVICE_ADDR, 1)
    await master.send_stop()
    assert addr_acked, "Slave did not ACK its address on read"

    dut._log.info(f"Wrote: 0x{test_value:02X}, read back: 0x{data[0]:02X}")
    assert data[0] == test_value, (
        f"Read value 0x{data[0]:02X} != written value 0x{test_value:02X}"
    )
    dut._log.info("Write-then-read roundtrip correct.")


#---------------------------------------------------------------------------------
#------------------------ Master bulk-writes to slave ----------------------------
#---------------------------------------------------------------------------------
@cocotb.test()
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_bulk_write(dut, speed):
    """Bulk-write: one index, multiple data bytes, reg_addr auto-increment."""
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    start_index = 0x02
    data_bytes  = [0x11, 0x22, 0x33]

    # Monitor only makes sense at RTL — internal signals are gone at gate level
    captured = []
    if not GATE_LEVEL:
        cocotb.start_soon(reg_write_monitor(dut, captured))

    # Bulk write transaction
    acks = await master.write(DEVICE_ADDR, [start_index] + data_bytes)
    await master.send_stop()
    assert all(acks), f"Not every byte was ACKed during bulk write: {acks}"

    # Give the monitor a few cycles to settle
    for _ in range(5):
        await RisingEdge(dut.clk)

    # White-box checks: pulse count, internal addr/data, physical registers
    if not GATE_LEVEL:
        assert len(captured) == len(data_bytes), (
            f"Expected {len(data_bytes)} reg_write pulses, got {len(captured)}: {captured}"
        )

        for i, (addr, data) in enumerate(captured):
            exp_addr = start_index + i
            exp_data = data_bytes[i]
            dut._log.info(f"Pulse {i}: addr=0x{addr:02X}, data=0x{data:02X}")
            assert addr == exp_addr, (
                f"Byte {i}: reg_addr 0x{addr:02X} != expected 0x{exp_addr:02X}"
            )
            assert data == exp_data, (
                f"Byte {i}: data 0x{data:02X} != expected 0x{exp_data:02X}"
            )

        for i, b in enumerate(data_bytes):
            reg_val = int(dut.user_project.top_level_inst.reg_block_a.registers[start_index + i].value)
            assert reg_val == b, (
                f"registers[{start_index + i}] = 0x{reg_val:02X}, expected 0x{b:02X}"
            )

    # Black-box equivalent: read each target register back via I2C and verify.
    # Works at both RTL and gate level.
    for i, expected in enumerate(data_bytes):
        addr = start_index + i
        readback = await read_register(master, addr)
        assert readback == expected, (
            f"Readback A[0x{addr:02X}] = 0x{readback:02X}, expected 0x{expected:02X}"
        )

    dut._log.info("Bulk-write correct — all bytes at the right places.")


#---------------------------------------------------------------------------------
#----------------------- Master bulk-reads from slave ----------------------------
#---------------------------------------------------------------------------------
@cocotb.test()
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_bulk_read(dut, speed):
    """Fill several registers, then read them back as an auto-incremented sequence."""
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    start_index = 0x03
    values      = [0xDE, 0xAD, 0xBE, 0xEF]

    # --- Prepare: write all values via bulk write ---
    acks_write = await master.write(DEVICE_ADDR, [start_index] + values)
    await master.send_stop()
    assert all(acks_write), f"Not every byte was ACKed during write: {acks_write}"

    # --- Read: set the index, then repeated-START into a multi-byte read ---
    acks_idx = await master.write(DEVICE_ADDR, [start_index])
    assert all(acks_idx), f"Index phase not fully ACKed: {acks_idx}"

    data, addr_acked = await master.read(DEVICE_ADDR, len(values))
    await master.send_stop()
    assert addr_acked, "Slave did not ACK its address on read"

    read_values = list(data)
    dut._log.info(f"Written: {[f'0x{v:02X}' for v in values]}")
    dut._log.info(f"Read:    {[f'0x{v:02X}' for v in read_values]}")
    assert read_values == values, (
        f"Bulk read mismatch: {read_values} != {values}"
    )
    dut._log.info("Bulk read correct — full sequence with auto-increment.")


#---------------------------------------------------------------------------------
#------------------------------- Address decoding --------------------------------
#---------------------------------------------------------------------------------
@cocotb.test()
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_address_decoding(dut, speed):
    """Writes target the correct block; the other block stays untouched.

    Block A is master-writable, Block B is read-only (fed by the LFSR).
    A write attempt to B must be ACKed by the slave but leave Block A
    completely unaffected.
    """
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    a_index, a_value = 0x02, 0xA5
    b_index          = 0x0B

    # Snapshot of all A registers via I2C read-back, right after reset.
    # At RTL level we could also read the RESET_VALUES parameter directly,
    # but reading via the bus works at both RTL and gate level.
    reset_a = {}
    for i in range(8):
        reset_a[i] = await read_register(master, i)

    # --- Write to A ---
    acks_a = await master.write(DEVICE_ADDR, [a_index, a_value])
    await master.send_stop()
    assert all(acks_a), f"Block A write not fully ACKed: {acks_a}"

    # --- Write attempt to B (will be ACKed but must have no effect) ---
    acks_b = await master.write(DEVICE_ADDR, [b_index, 0xFF])
    await master.send_stop()
    assert all(acks_b), f"Block B write not fully ACKed: {acks_b}"

    # White-box checks: only meaningful at RTL
    if not GATE_LEVEL:
        a_val = int(dut.user_project.top_level_inst.reg_block_a.registers[a_index].value)
        assert a_val == a_value, (
            f"reg_block_a.registers[{a_index}] = 0x{a_val:02X}, expected 0x{a_value:02X}"
        )
        for i in range(8):
            if i == a_index:
                continue
            val = int(dut.user_project.top_level_inst.reg_block_a.registers[i].value)
            assert val == reset_a[i], (
                f"reg_block_a.registers[{i}] disturbed: 0x{val:02X}, "
                f"expected reset value 0x{reset_a[i]:02X}"
            )

    # Black-box equivalent: read every A register back via I2C and check.
    # This runs at both RTL and gate level — the white-box version above
    # is a stronger statement at RTL but the bus-level check covers gate level.
    a_readback = await read_register(master, a_index)
    assert a_readback == a_value, (
        f"A[0x{a_index:02X}] readback = 0x{a_readback:02X}, expected 0x{a_value:02X}"
    )
    for i in range(8):
        if i == a_index:
            continue
        val = await read_register(master, i)
        assert val == reset_a[i], (
            f"A[0x{i:02X}] disturbed: 0x{val:02X}, expected 0x{reset_a[i]:02X}"
        )

    dut._log.info("Address decoding correct — A targeted precisely, "
                  "B-write had no effect on A.")
    

#---------------------------------------------------------------------------------
#-------------------- Access to non-existent register address --------------------
#---------------------------------------------------------------------------------
@cocotb.test()
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_unmapped_address(dut, speed):
    """Access to a register address that no reg_block covers.

    Block A spans 0x00..0x07, Block B spans 0x08..0x0F.
    Addresses 0x10..0xFF are unmapped.

    Expected behavior:
      - Slave ACKs the device address and all bytes (it has no idea the
        register address points nowhere).
      - Write attempt has no side effect on any real register.
      - Read attempt returns 0x00 because every reg_block outputs 0 when
        not selected and the OR-tree combines them.
    """
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    unmapped_index  = 0x20
    reference_index = 0x05
    reference_value = 0x99

    # Reference write into a real register, so we can later spot any spillover
    acks_ref = await master.write(DEVICE_ADDR, [reference_index, reference_value])
    await master.send_stop()
    assert all(acks_ref), f"Reference write not fully ACKed: {acks_ref}"

    # --- Write attempt to the unmapped address: ACKed, but must have no effect ---
    acks_write = await master.write(DEVICE_ADDR, [unmapped_index, 0xCC])
    await master.send_stop()
    assert all(acks_write), (
        f"Write to unmapped address not fully ACKed: {acks_write}"
    )

    # White-box check: only meaningful at RTL
    if not GATE_LEVEL:
        ref = int(dut.user_project.top_level_inst.reg_block_a.registers[reference_index].value)
        assert ref == reference_value, (
            f"Reference register 0x{reference_index:02X} disturbed: "
            f"0x{ref:02X}, expected 0x{reference_value:02X}"
        )

    # Black-box equivalent: read the reference register back via the bus.
    # Works at both RTL and gate level.
    ref_readback = await read_register(master, reference_index)
    assert ref_readback == reference_value, (
        f"Reference register 0x{reference_index:02X} disturbed (readback): "
        f"0x{ref_readback:02X}, expected 0x{reference_value:02X}"
    )

    # --- Read attempt from the unmapped address: must return 0x00 ---
    acks_idx = await master.write(DEVICE_ADDR, [unmapped_index])
    assert all(acks_idx), f"Index phase not fully ACKed: {acks_idx}"
    data, addr_acked = await master.read(DEVICE_ADDR, 1)
    await master.send_stop()
    assert addr_acked, "Slave did not ACK the read address"

    dut._log.info(
        f"Read from unmapped address 0x{unmapped_index:02X}: 0x{data[0]:02X}"
    )
    assert data[0] == 0x00, (
        f"Unmapped read should return 0x00, got 0x{data[0]:02X}"
    )

    dut._log.info("Unmapped address handled correctly — ACKed without effect, "
                  "read returns 0x00.")
    

#---------------------------------------------------------------------------------
#----------------------------- Block B is read-only ------------------------------
#---------------------------------------------------------------------------------
@cocotb.test()
@cocotb.parametrize(speed=[100e3, 400e3])
async def test_block_b_is_read_only(dut, speed):
    """A write attempt to a Block B address must not change the value.

    Block B is fed by the LFSR module and has no write path from the I2C
    slave. The slave will still ACK the write (it has no idea Block B is
    read-only), but the actual register value must stay independent of
    the value we tried to write.
    """
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    target_addr = 0x0A     # middle of Block B
    forbidden   = 0xFF     # value we try (and should fail) to write

    # Reference read
    acks_idx = await master.write(DEVICE_ADDR, [target_addr])
    assert all(acks_idx), f"Index phase not ACKed: {acks_idx}"
    before_data, before_acked = await master.read(DEVICE_ADDR, 1)
    await master.send_stop()
    assert before_acked, "Read address not ACKed (before)"
    dut._log.info(f"B[0x{target_addr:02X}] before write attempt: 0x{before_data[0]:02X}")

    # Write attempt — slave will ACK, but Block B must not be affected
    acks_write = await master.write(DEVICE_ADDR, [target_addr, forbidden])
    await master.send_stop()
    assert all(acks_write), f"Write attempt not fully ACKed: {acks_write}"

    # Read back right away, before the LFSR has had a chance to tick
    acks_idx2 = await master.write(DEVICE_ADDR, [target_addr])
    assert all(acks_idx2), f"Index phase (after) not ACKed: {acks_idx2}"
    after_data, after_acked = await master.read(DEVICE_ADDR, 1)
    await master.send_stop()
    assert after_acked, "Read address not ACKed (after)"
    dut._log.info(f"B[0x{target_addr:02X}] after write attempt:  0x{after_data[0]:02X}")

    assert after_data[0] != forbidden, (
        f"Block B accepted the write! Value is 0x{after_data[0]:02X}"
    )
    dut._log.info("Block B is read-only — write attempt correctly ignored.")


#---------------------------------------------------------------------------------
#------------------------------ LFSR is active -----------------------------------
#---------------------------------------------------------------------------------
async def read_register(master, index):
    """Set the register pointer and read one byte via repeated-START."""
    await master.write(DEVICE_ADDR, [index])
    data, addr_acked = await master.read(DEVICE_ADDR, 1)
    await master.send_stop()
    assert addr_acked, f"Read address not ACKed for index 0x{index:02X}"
    return data[0]


@cocotb.test()
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_lfsr_is_active(dut, speed):
    """Reads of the same B register over time must yield different values."""
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    target_addr  = 0x09
    n_samples    = 4
    wait_between = 2     # ms — longer than the ~1.3 ms per-register update period

    samples = []
    for i in range(n_samples):
        value = await read_register(master, target_addr)
        samples.append(value)
        dut._log.info(f"Sample {i}: B[0x{target_addr:02X}] = 0x{value:02X}")
        if i < n_samples - 1:
            await Timer(wait_between, unit="ms")

    unique_values = set(samples)
    assert len(unique_values) >= 2, (
        f"LFSR seems stuck: all {n_samples} reads returned {samples}"
    )
    dut._log.info(
        f"LFSR is active — {len(unique_values)} distinct values in {n_samples} reads."
    )


#---------------------------------------------------------------------------------
#----------------------- All B registers get updated -----------------------------
#---------------------------------------------------------------------------------
# @cocotb.test(skip=GATE_LEVEL)
# @cocotb.parametrize(speed=[100e3, 400e3, 1e6])
# async def test_all_b_registers_updated(dut, speed):
#     """Over time the LFSR must write each individual register in Block B."""
#     cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
#     await reset_dut(dut)
#     master = make_master(dut, speed=speed)

#     # Pull block parameters from the RTL — single source of truth
#     base_addr = int(dut.user_project.top_level_inst.reg_block_b.BASE_ADDR.value)
#     n_regs    = int(dut.user_project.top_level_inst.reg_block_b.N_REGS.value)
#     reset_b_local = extract_reset_values(
#         dut.user_project.top_level_inst.reg_block_b.RESET_VALUES.value, n_regs=n_regs
#     )
#     reset_values = {base_addr + i: v for i, v in reset_b_local.items()}

#     # Wait long enough for the LFSR to have done several full address sweeps.
#     # One sweep is ~1.3 ms (8 regs * 4096 ticks * 40 ns), so 5 ms covers ~4 sweeps.
#     await Timer(5, unit="ms")

#     changed_count = 0
#     for addr in range(base_addr, base_addr + n_regs):
#         value = await read_register(master, addr)
#         dut._log.info(
#             f"B[0x{addr:02X}] = 0x{value:02X} (reset was 0x{reset_values[addr]:02X})"
#         )
#         if value != reset_values[addr]:
#             changed_count += 1

#     # Strict assertion: every register must have been touched by the LFSR.
#     # After several sweeps, the chance of any register coincidentally landing
#     # back on its reset value is statistically negligible.
#     assert changed_count == n_regs, (
#         f"Only {changed_count}/{n_regs} B registers were updated by the LFSR"
#     )
#     dut._log.info(f"LFSR reliably updates all {n_regs} B registers.")


#---------------------------------------------------------------------------------
#------------------------- Block A unaffected by LFSR ----------------------------
#---------------------------------------------------------------------------------
@cocotb.test(skip=GATE_LEVEL)
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_block_a_unaffected_by_lfsr(dut, speed):
    """LFSR activity must not write any values into Block A."""
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    # Pull block A parameters from the RTL
    base_addr = int(dut.user_project.top_level_inst.reg_block_a.BASE_ADDR.value)
    n_regs    = int(dut.user_project.top_level_inst.reg_block_a.N_REGS.value)

    # Build a distinguishable pattern, one unique value per address.
    # 0xA0 | low3 makes each value carry its own address in the low bits.
    pattern = {base_addr + i: 0xA0 | (i & 0x07) for i in range(n_regs)}

    # Write all A registers in one bulk transaction starting at base_addr
    values = [pattern[base_addr + i] for i in range(n_regs)]
    acks = await master.write(DEVICE_ADDR, [base_addr] + values)
    await master.send_stop()
    assert all(acks), f"Bulk write to Block A not fully ACKed: {acks}"

    # Wait long enough for several full LFSR sweeps through Block B
    await Timer(5, unit="ms")

    # Every A register must still hold exactly the written pattern
    for addr, expected in pattern.items():
        value = await read_register(master, addr)
        dut._log.info(
            f"A[0x{addr:02X}] = 0x{value:02X}, expected 0x{expected:02X}"
        )
        assert value == expected, (
            f"A[0x{addr:02X}] was changed: 0x{value:02X} instead of 0x{expected:02X}"
        )

    dut._log.info("Block A remains untouched by LFSR — clean range separation.")


#---------------------------------------------------------------------------------
#--------------- Bulk read stress test over LFSR activity ------------------------
#---------------------------------------------------------------------------------
@cocotb.test()
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_bulk_read_stress(dut, speed):
    """Repeated bulk reads over a long time — design must stay consistent."""
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    n_iterations     = 20
    n_bytes_per_read = 4
    start_index      = 0x09
    all_reads        = []

    for iteration in range(n_iterations):
        # Set pointer, then repeated-START into a multi-byte read.
        # An ACK on the very next iteration's address phase implicitly
        # confirms the slave returned to S_IDLE after the previous one.
        acks_idx = await master.write(DEVICE_ADDR, [start_index])
        assert all(acks_idx), (
            f"Iter {iteration}: index phase not fully ACKed: {acks_idx} "
            f"(slave may not have returned to S_IDLE after previous iteration)"
        )

        data, addr_acked = await master.read(DEVICE_ADDR, n_bytes_per_read)
        await master.send_stop()
        assert addr_acked, f"Iter {iteration}: read address not ACKed"

        bytes_this_iter = list(data)
        all_reads.append(bytes_this_iter)

        # Wait a few cycles, then check state if we have access to internals
        for _ in range(5):
            await RisingEdge(dut.clk)

        if not GATE_LEVEL:
            state = int(dut.user_project.top_level_inst.i2c_inst.state.value)
            assert state == S_IDLE, (
                f"Iter {iteration}: state not IDLE after bulk read, got {state}"
            )

        # All values plausible (8-bit range, no x/z)?
        assert all(0 <= v <= 255 for v in bytes_this_iter), (
            f"Iter {iteration}: invalid values {bytes_this_iter}"
        )

        # Pause between iterations so the LFSR keeps running
        await Timer(500, unit="us")

    # --- Aggregate analysis across all iterations ---
    # Per address slot, check that not every read returned the same value
    for slot in range(n_bytes_per_read):
        values_in_slot = [reads[slot] for reads in all_reads]
        unique = set(values_in_slot)
        dut._log.info(
            f"Slot {slot} (addr 0x{start_index + slot:02X}): "
            f"{len(unique)} distinct values over {n_iterations} iterations"
        )
        assert len(unique) >= 2, (
            f"Slot {slot}: all {n_iterations} values identical "
            f"({values_in_slot}) — LFSR stuck?"
        )

    # Sanity check: slave still works after all that
    final_check = await read_register(master, 0x00)
    dut._log.info(f"After {n_iterations} bulk reads: A[0x00] = 0x{final_check:02X}")

    dut._log.info(
        f"Stress test passed: {n_iterations} bulk reads of "
        f"{n_bytes_per_read} bytes each, all consistent."
    )


#---------------------------------------------------------------------------------
#------------------------ Mixed read/write stress --------------------------------
#---------------------------------------------------------------------------------
@cocotb.test()
@cocotb.parametrize(speed=[100e3, 400e3, 1e6])
async def test_mixed_stress(dut, speed):
    """Random mix of read and write transactions over a long time."""
    import random
    rng = random.Random(42)   # fixed seed for reproducibility

    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=speed)

    # Block layout: hardcoded but matches the RTL parameters in top_level.v
    base_a, n_regs_a = 0x00, 8
    base_b, n_regs_b = 0x08, 8
    a_range_max  = base_a + n_regs_a - 1
    ab_range_max = base_b + n_regs_b - 1

    # Initialize the shadow model by reading every A register over the bus.
    # This works at both RTL and gate level and avoids hardcoding RESET_VALUES.
    expected_a = {}
    for i in range(n_regs_a):
        addr = base_a + i
        expected_a[addr] = await read_register(master, addr)

    n_iterations = 20

    for iteration in range(n_iterations):
        op = rng.choice(["write", "read"])

        if op == "write":
            addr  = rng.randint(base_a, a_range_max)   # writable: only A
            value = rng.randint(0x00, 0xFF)
            acks = await master.write(DEVICE_ADDR, [addr, value])
            await master.send_stop()
            assert all(acks), (
                f"Iter {iteration}: WRITE A[0x{addr:02X}] not fully ACKed: {acks}"
            )
            expected_a[addr] = value
            dut._log.info(f"Iter {iteration}: WRITE A[0x{addr:02X}] = 0x{value:02X}")

        else:  # read
            addr = rng.randint(base_a, ab_range_max)   # can be A or B
            acks_idx = await master.write(DEVICE_ADDR, [addr])
            assert all(acks_idx), (
                f"Iter {iteration}: index phase for read not ACKed: {acks_idx}"
            )
            data, addr_acked = await master.read(DEVICE_ADDR, 1)
            await master.send_stop()
            assert addr_acked, f"Iter {iteration}: read address not ACKed"

            value = data[0]
            dut._log.info(f"Iter {iteration}: READ  [0x{addr:02X}] = 0x{value:02X}")

            # Check against shadow model only for A; B values come from the LFSR
            if addr in expected_a:
                assert value == expected_a[addr], (
                    f"Iter {iteration}: A[0x{addr:02X}] = 0x{value:02X}, "
                    f"model says 0x{expected_a[addr]:02X}"
                )

        # Wait a few cycles, then check state if we have access to internals
        for _ in range(5):
            await RisingEdge(dut.clk)

        if not GATE_LEVEL:
            state = int(dut.user_project.top_level_inst.i2c_inst.state.value)
            assert state == S_IDLE, (
                f"Iter {iteration}: state not IDLE, got {state}"
            )

        await Timer(200, unit="us")

    # --- Final validation: read every A register against the shadow model ---
    for addr, expected in expected_a.items():
        value = await read_register(master, addr)
        assert value == expected, (
            f"Final: A[0x{addr:02X}] = 0x{value:02X} != model 0x{expected:02X}"
        )

    dut._log.info(
        f"Mixed stress test passed: {n_iterations} random operations, "
        f"shadow model consistent."
    )





#---------------------------------------------------------------------------------
#--------------- Config sweep for waveform viewing (not a pass/fail test) ---------
#---------------------------------------------------------------------------------
# Drives Block A configuration through phase_inc, signal amplitude and noise
# amplitude — first individually, then in combinations — holding each setting
# long enough to see at least two full waveform periods in the FST.
#
# View in the waveform viewer:
#   phase:    user_project.top_level_inst.signal_source_b.u_phase.phase
#   channels: user_project.top_level_inst.signal_source_b.u_bank.registers[1..7]
# (Add explicit $dumpvars lines for u_bank.registers[*] in tb.v — iverilog does
#  not auto-dump memory arrays. The old reg_block_b dump paths are now stale.)

# --- Design constants: MUST match the RTL parameters ---
ACC_MAX      = 1 << 16          # ACC_WIDTH = 16
TICK_DIVIDER = 4096
CLK_NS       = 40
TICK_US      = (CLK_NS * 1e-3) * TICK_DIVIDER   # 163.84 us per tick

# Block A configuration register addresses
REG_PHASE_L  = 0x00
REG_PHASE_H  = 0x01
REG_SIG_AMP  = 0x02
REG_NOISE_AMP= 0x03

# Block B channel addresses
B_STATUS     = 0x08
B_FIRST_DATA = 0x09     # sine; +1 cosine, +2 triangle, +3 sawtooth,
                        # +4 square, +5 noisy_sine, +6 noise
CH_NAMES = ["sine", "cosine", "triangle", "sawtooth", "square", "noisy_sine", "noise"]

N_PERIODS    = 4      # >= 2 periods held per configuration
DENSE_READ   = False    # True = also read channels over the bus during each hold
                        #        (shows a bus-side waveform + status flags, slower)


def hold_us_for(phase_inc, n_periods=N_PERIODS):
    """Microseconds needed to display n_periods of the waveform at phase_inc."""
    period_ticks = ACC_MAX / phase_inc
    return n_periods * period_ticks * TICK_US


async def configure(master, phase_inc, sig_amp_shift, noise_amp_shift):
    """Bulk-write the four Block A config registers in one transaction."""
    lo = phase_inc & 0xFF
    hi = (phase_inc >> 8) & 0xFF
    payload = [REG_PHASE_L, lo, hi, sig_amp_shift & 0x03, noise_amp_shift & 0x07]
    acks = await master.write(DEVICE_ADDR, payload)
    await master.send_stop()
    assert all(acks), f"Config write not fully ACKed: {acks}"


async def read_channels(master):
    """Snapshot all 7 Block B data channels in one bulk read."""
    acks = await master.write(DEVICE_ADDR, [B_FIRST_DATA])
    assert all(acks), "Channel-read pointer set not ACKed"
    data, addr_acked = await master.read(DEVICE_ADDR, 7)
    await master.send_stop()
    assert addr_acked, "Channel read address not ACKed"
    return list(data)


async def hold_and_view(dut, master, phase_inc, label):
    """Hold the current configuration for >= N_PERIODS, optionally sampling."""
    total_us = hold_us_for(phase_inc)
    period_ticks = ACC_MAX // phase_inc
    dut._log.info(
        f"  {label}: period = {period_ticks} ticks (~{period_ticks*TICK_US/1000:.2f} ms), "
        f"holding {N_PERIODS} periods (~{total_us/1000:.2f} ms)"
    )

    if not DENSE_READ:
        await Timer(round(total_us), unit="us")
        snap = await read_channels(master)
        dut._log.info(f"    snapshot: " +
                      ", ".join(f"{n}=0x{v:02X}" for n, v in zip(CH_NAMES, snap)))
    else:
        # Read ~4 times per period so the bus trace also shows the waveform.
        n_reads = max(2, round(N_PERIODS * 4))
        slice_us = total_us / n_reads
        for _ in range(n_reads):
            await Timer(round(slice_us), unit="us")
            snap = await read_channels(master)
            dut._log.info(f"    sample: " +
                          ", ".join(f"{n}=0x{v:02X}" for n, v in zip(CH_NAMES, snap)))


@cocotb.test(skip=GATE_LEVEL)
async def test_config_sweep_waveforms(dut):
    """Sweep configuration parameters for waveform inspection in the FST."""
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    await reset_dut(dut)
    master = make_master(dut, speed=400e3)

    # ---------------------------------------------------------------
    # 1) Phase increment (frequency) sweep — full amplitude, moderate noise
    # ---------------------------------------------------------------
    dut._log.info("=== 1) PHASE INCREMENT SWEEP (amp=full, noise=shift2) ===")
    for pinc in [1024, 2048, 4096]:
        await configure(master, phase_inc=pinc, sig_amp_shift=0, noise_amp_shift=2)
        await hold_and_view(dut, master, pinc, f"phase_inc={pinc}")

    # ---------------------------------------------------------------
    # 2) Signal amplitude sweep — fixed frequency, moderate noise
    # ---------------------------------------------------------------
    dut._log.info("=== 2) SIGNAL AMPLITUDE SWEEP (phase_inc=2048, noise=shift2) ===")
    for amp in [0, 1, 2, 3]:    # full, half, quarter, eighth
        await configure(master, phase_inc=2048, sig_amp_shift=amp, noise_amp_shift=2)
        await hold_and_view(dut, master, 2048, f"sig_amp_shift={amp}")

    # ---------------------------------------------------------------
    # 3) Noise amplitude sweep — fixed frequency, full signal amplitude
    # ---------------------------------------------------------------
    dut._log.info("=== 3) NOISE AMPLITUDE SWEEP (phase_inc=2048, amp=full) ===")
    for nz in [0, 2, 4]:        # loud, moderate, nearly off
        await configure(master, phase_inc=2048, sig_amp_shift=0, noise_amp_shift=nz)
        await hold_and_view(dut, master, 2048, f"noise_amp_shift={nz}")

    # ---------------------------------------------------------------
    # 4) Combinations
    # ---------------------------------------------------------------
    dut._log.info("=== 4) COMBINATIONS ===")
    combos = [
        # (phase_inc, sig_amp_shift, noise_amp_shift, description)
        (1024, 0, 5, "slow, full amplitude, noise off"),
        (4096, 1, 0, "fast, half amplitude, loud noise"),
        (2048, 2, 2, "mid, quarter amplitude, moderate noise"),
        (1024, 3, 4, "slow, eighth amplitude, light noise"),
    ]
    for pinc, amp, nz, desc in combos:
        await configure(master, phase_inc=pinc, sig_amp_shift=amp, noise_amp_shift=nz)
        await hold_and_view(dut, master, pinc, f"combo [{desc}]")

    dut._log.info("Config sweep complete — open the FST to inspect the waveforms.")