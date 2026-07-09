# ups.py — Waveshare UPS HAT (INA219) driver for SATURNIX Dione
# Reads battery voltage, current, charge percentage and charging state.
# I2C address: 0x43 (default for Waveshare UPS HAT for Pi Zero).

import time

try:
    import smbus
    _HAVE_I2C = True
except ImportError:
    _HAVE_I2C = False

# ============================================================
#   INA219 register map
# ============================================================
_REG_CONFIG = 0x00
_REG_SHUNTVOLTAGE = 0x01
_REG_BUSVOLTAGE = 0x02
_REG_POWER = 0x03
_REG_CURRENT = 0x04
_REG_CALIBRATION = 0x05

# Config bits
_CONFIG_RESET = 0x8000
_CONFIG_BVOLTAGERANGE_32V = 0x2000
_CONFIG_GAIN_8_320MV = 0x1800
_CONFIG_BADCRES_12BIT_32S = 0x0078       # 32 samples averaging
_CONFIG_SADCRES_12BIT_32S = 0x0078
_CONFIG_MODE_SANDBVOLT_CONTINUOUS = 0x0007

# Battery voltage range (Li-ion)
_V_FULL = 4.20  # 100% charged
_V_EMPTY = 3.00  # 0% (cut-off)

# Module state
_bus = None
_addr = 0x43
_initialized = False
_init_failed = False

# Cache + smoothing
_cache_t = 0.0
_cache_pct = None  # None until the first VALID reading (prevents false 0%)
_cache_charging = False
_cache_voltage = 0.0
_CACHE_INTERVAL = 10.0  # refresh every 10 seconds (was 5s — reduces UI jitter)

# Voltage smoothing: rolling median over last N readings
_v_history = []
_V_HISTORY_MAX = 7  # 7 readings × 10s = ~70s window
_HYSTERESIS_PCT = 3  # don't update displayed % unless it changed by >3%


def _write_reg(reg, value):
    """Write 16-bit big-endian to register."""
    data = [(value >> 8) & 0xFF, value & 0xFF]
    _bus.write_i2c_block_data(_addr, reg, data)


def _read_reg(reg):
    """Read 16-bit big-endian unsigned from register."""
    data = _bus.read_i2c_block_data(_addr, reg, 2)
    return (data[0] << 8) | data[1]


def _read_reg_signed(reg):
    """Read 16-bit big-endian signed from register."""
    val = _read_reg(reg)
    if val > 32767:
        val -= 65536
    return val


def init(addr=0x43, bus_num=1):
    """Initialize INA219 on I2C. Returns True on success."""
    global _bus, _addr, _initialized, _init_failed
    _addr = addr
    if not _HAVE_I2C:
        _init_failed = True
        return False
    try:
        _bus = smbus.SMBus(bus_num)
        # Calibration for 32V / 2A range with 0.1Ω shunt
        # Current_LSB = 0.0001 (100uA per bit)
        # Cal = 0.04096 / (Current_LSB * R_shunt) = 0.04096 / (0.0001 * 0.1) = 4096
        _write_reg(_REG_CALIBRATION, 4096)
        config = (_CONFIG_BVOLTAGERANGE_32V |
                  _CONFIG_GAIN_8_320MV |
                  _CONFIG_BADCRES_12BIT_32S |
                  _CONFIG_SADCRES_12BIT_32S |
                  _CONFIG_MODE_SANDBVOLT_CONTINUOUS)
        _write_reg(_REG_CONFIG, config)
        _initialized = True
        return True
    except Exception as e:
        print(f"[UPS] init failed: {e}", flush=True)
        _init_failed = True
        return False


def read_voltage():
    """Battery voltage in volts."""
    if not _initialized:
        return 0.0
    try:
        # Bus voltage register: bits 3-15 are voltage, LSB = 4mV
        raw = _read_reg(_REG_BUSVOLTAGE)
        return ((raw >> 3) * 0.004)
    except Exception as e:
        print(f"[UPS] read_voltage err: {e}", flush=True)
        return 0.0


def read_current_ma():
    """Current in milliamps. Negative = discharging, positive = charging."""
    if not _initialized:
        return 0.0
    try:
        raw = _read_reg_signed(_REG_CURRENT)
        # Current_LSB was set to 100uA = 0.1 mA
        return raw * 0.1
    except Exception as e:
        print(f"[UPS] read_current err: {e}", flush=True)
        return 0.0


def voltage_to_percent(v):
    """Convert Li-ion voltage to percentage (linear approximation).
    More accurate than linear at extremes — uses simple piecewise curve."""
    if v >= _V_FULL:
        return 100
    if v <= _V_EMPTY:
        return 0
    # Piecewise curve approximating Li-ion discharge
    # 4.20V=100%, 4.00V=80%, 3.85V=60%, 3.75V=40%, 3.65V=20%, 3.00V=0%
    points = [
        (3.00, 0),
        (3.65, 20),
        (3.75, 40),
        (3.85, 60),
        (4.00, 80),
        (4.20, 100),
    ]
    for i in range(len(points) - 1):
        v1, p1 = points[i]
        v2, p2 = points[i + 1]
        if v1 <= v <= v2:
            ratio = (v - v1) / (v2 - v1)
            return int(p1 + ratio * (p2 - p1))
    return 50  # fallback


def get_status():
    """Returns (percent, charging, voltage). Cached + smoothed.
    Uses rolling median voltage to filter out noise/load spikes,
    plus hysteresis so the displayed percentage doesn't jitter.
    Falls back to (60, False, 0.0) if INA219 not available."""
    global _cache_t, _cache_pct, _cache_charging, _cache_voltage
    if _init_failed or not _initialized:
        return (60, False, 0.0)
    now = time.monotonic()
    if now - _cache_t < _CACHE_INTERVAL:
        # No valid reading yet -> report safe placeholder, NOT 0%
        if _cache_pct is None:
            return (60, _cache_charging, _cache_voltage)
        return (_cache_pct, _cache_charging, _cache_voltage)
    try:
        # Take 3 quick readings and use the median to filter noise
        samples = []
        for _ in range(3):
            v = read_voltage()
            if v > 0.5:  # sanity check
                samples.append(v)
            time.sleep(0.02)
        if not samples:
            # I2C hiccup: return last KNOWN value; safe placeholder if none.
            if _cache_pct is None:
                return (60, _cache_charging, _cache_voltage)
            return (_cache_pct, _cache_charging, _cache_voltage)
        samples.sort()
        v_now = samples[len(samples) // 2]  # median of 3

        # Add to rolling history
        _v_history.append(v_now)
        if len(_v_history) > _V_HISTORY_MAX:
            _v_history.pop(0)

        # Use median of history for stable reading
        sorted_h = sorted(_v_history)
        v_smooth = sorted_h[len(sorted_h) // 2]

        new_pct = voltage_to_percent(v_smooth)
        c_ma = read_current_ma()
        charging = c_ma > 30

        # A shutdown-grade 0% must be backed by a real trend, not a single
        # spike: require at least 3 samples in the rolling history.
        if new_pct == 0 and len(_v_history) < 3:
            new_pct = 5

        # Hysteresis: only update displayed % if change > threshold,
        # OR if charging state changed (always show transition immediately),
        # OR if going to extreme (0% or 100%)
        if (_cache_pct is None
                or abs(new_pct - _cache_pct) >= _HYSTERESIS_PCT
                or charging != _cache_charging
                or new_pct == 0 or new_pct == 100
                or _cache_pct == 0):
            _cache_pct = new_pct

        _cache_t = now
        _cache_charging = charging
        _cache_voltage = v_smooth
        return (_cache_pct, _cache_charging, _cache_voltage)
    except Exception as e:
        print(f"[UPS] read err: {e}", flush=True)
        return (_cache_pct, _cache_charging, _cache_voltage)


def is_available():
    """Returns True if INA219 was successfully initialized."""
    return _initialized and not _init_failed
