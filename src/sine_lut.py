import math

# --- Quarter-wave sine LUT generator with midpoint sampling ---
# 8-bit phase index (0..255) -> 8-bit unsigned output (0..255), centered at 127.5
# We store only the first quadrant (64 entries) and derive the rest by
# mirroring (bit-flip of the low 6 phase bits) and negating (quadrant MSBs).
#
# Midpoint sampling: entry i represents sin(2*pi*(i+0.5)/256).
# This avoids an entry sitting exactly on 0 deg / 90 deg, which makes the
# bit-flip symmetry exact and removes the awkward seam at the peak.

N = 256
QUARTER = 64

# Quarter table: magnitude above center, 0..~127
qlut = []
for i in range(QUARTER):
    angle = 2 * math.pi * (i + 0.5) / N
    val = round(127.5 * math.sin(angle))
    qlut.append(val)

print("Quarter LUT (64 entries):")
for r in range(0, QUARTER, 8):
    print("  " + ", ".join(f"{v:3d}" for v in qlut[r:r+8]))

# --- Reconstruct full 256-point wave using the same logic the hardware will use ---
def reconstruct(phase):
    quadrant = (phase >> 6) & 0x3      # top 2 bits
    pos      = phase & 0x3F            # low 6 bits
    if quadrant == 0:                  # 0..90 deg, ascending positive
        return 128 + qlut[pos]
    elif quadrant == 1:                # 90..180 deg, descending positive
        return 128 + qlut[(~pos) & 0x3F]
    elif quadrant == 2:                # 180..270 deg, descending negative
        return 127 - qlut[pos]
    else:                              # 270..360 deg, ascending negative
        return 127 - qlut[(~pos) & 0x3F]

recon = [reconstruct(p) for p in range(N)]

# --- Reference: direct full sine, same midpoint convention ---
ref = [round(127.5 + 127.5 * math.sin(2*math.pi*(p+0.5)/N)) for p in range(N)]
# clamp ref to 0..255 just in case of rounding to 256
ref = [min(255, max(0, v)) for v in ref]

max_err = max(abs(recon[p] - ref[p]) for p in range(N))
print(f"\nReconstructed range: min={min(recon)}, max={max(recon)}")
print(f"Max error vs direct full sine: {max_err}")

# Check key points
print(f"phase 0   -> {recon[0]:3d} (expect ~128, zero crossing rising)")
print(f"phase 63  -> {recon[63]:3d} (near +peak)")
print(f"phase 64  -> {recon[64]:3d} (+peak)")
print(f"phase 127 -> {recon[127]:3d} (near center, falling)")
print(f"phase 128 -> {recon[128]:3d} (center, falling)")
print(f"phase 191 -> {recon[191]:3d} (-peak)")
print(f"phase 192 -> {recon[192]:3d} (-peak)")
print(f"phase 255 -> {recon[255]:3d} (near center, rising)")

# verify symmetry about center 127.5
sym_ok = all(recon[p] + recon[(p + 128) & 0xFF] == 255 for p in range(N))
print(f"\nHalf-wave anti-symmetry (recon[p] + recon[p+128] == 255): {sym_ok}")

# --- Emit Verilog case for the quarter table ---
print("\n--- Verilog quarter-LUT case ---")
for i, v in enumerate(qlut):
    print(f"            6'd{i:<2d}: q = 8'd{v};")
