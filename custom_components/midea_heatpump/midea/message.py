"""
Midea M-Smart AA-frame message builder/parser for C3 (ATW heat pump) devices.
"""

from enum import IntEnum


# -- Message types --

class MessageType(IntEnum):
    SET = 0x02
    QUERY = 0x03
    NOTIFY1 = 0x04
    NOTIFY2 = 0x05
    QUERY_APPLIANCE = 0xA0


# -- Base AA-frame --

def checksum(data: bytes) -> int:
    """Compute M-Smart checksum: (~sum(bytes[1:]) + 1) & 0xFF."""
    return (~sum(data[1:]) + 1) & 0xFF


def build_frame(device_type: int, msg_type: int, body: bytes, protocol_ver: int = 0) -> bytes:
    """Build a complete AA-frame with header, body, and checksum.

    Frame: [0xAA, length, device_type, 0x00, 0x00, 0x00, 0x00, 0x00, protocol_ver, msg_type, ...body..., checksum]
    """
    # Header (10 bytes)
    header = bytearray([
        0xAA,
        0x00,       # length placeholder (filled below)
        device_type & 0xFF,
        0x00, 0x00, 0x00, 0x00, 0x00,
        protocol_ver & 0xFF,
        msg_type & 0xFF,
    ])

    frame = header + bytearray(body)
    frame[1] = len(frame)  # length includes everything except checksum
    frame.append(checksum(frame))
    return bytes(frame)


def parse_frame(data: bytes) -> dict | None:
    """Parse an AA-frame, returning header info and body."""
    if len(data) < 11 or data[0] != 0xAA:
        return None

    length = data[1]
    if len(data) < length + 1:
        return None

    return {
        "length": length,
        "device_type": data[2],
        "protocol_ver": data[8],
        "msg_type": data[9],
        "body": data[10:-1],
        "checksum": data[-1],
        "raw": data,
    }


# -- C3 Device Type --

DEVICE_TYPE_C3 = 0xC3
NO_CHANGE = 0x7F  # Sentinel value: "don't change this field"


# -- C3 Query Messages --

def build_query_basic() -> bytes:
    """Query basic status (body_type=0x01)."""
    return build_frame(DEVICE_TYPE_C3, MessageType.QUERY, bytes([0x01]))


def build_query_silence() -> bytes:
    """Query silence/quiet mode (body_type=0x05)."""
    return build_frame(DEVICE_TYPE_C3, MessageType.QUERY, bytes([0x05]))


def build_query_eco() -> bytes:
    """Query ECO mode (body_type=0x07)."""
    return build_frame(DEVICE_TYPE_C3, MessageType.QUERY, bytes([0x07]))


def build_query_disinfect() -> bytes:
    """Query disinfect mode (body_type=0x09)."""
    return build_frame(DEVICE_TYPE_C3, MessageType.QUERY, bytes([0x09]))


def build_query_unit_para() -> bytes:
    """Query unit parameters / detailed sensor data (body_type=0x10)."""
    return build_frame(DEVICE_TYPE_C3, MessageType.QUERY, bytes([0x10]))


def build_query_appliance() -> bytes:
    """Query appliance info (msg_type=0xA0) -- used for protocol detection."""
    return build_frame(DEVICE_TYPE_C3, MessageType.QUERY_APPLIANCE, bytes([0x00] * 20))


# -- C3 Set Messages --

def _encode_temp_heat(temp: float) -> int:
    """Encode heating water flow target: raw = (temp - 9) * 2.

    Verified: 39°C→60, 42°C→66, 47°C→76. Readable back from C0 byte[18].
    """
    return int((temp - 9) * 2) & 0xFF


def _decode_temp_heat(value: int) -> float | None:
    """Decode heating water flow target: temp = raw / 2 + 9.

    C0 byte[18]. NOT XC0 encoding. Previously misidentified as outdoor temp.
    Verified: raw=60→39°C, raw=66→42°C, raw=76→47°C.
    """
    if value == 0xFF or value == 0x00:
        return None
    return value / 2 + 9


def build_set_command(
    dhw_target_temp: float | None = None,
    heat_target_temp: float | None = None,
    zone1_target_temp: float | None = None,
    zone2_target_temp: float | None = None,
    room_target_temp: float | None = None,
    flags: int = 0x43,
) -> bytes:
    """Build SET command (body_type=0x40, protocol_ver=3).

    DHW target (byte 2) uses linear encoding: raw = temp + 99.
    Heating target (byte 18) uses encoding: raw = (temp - 9) * 2.
    Zone targets (bytes 4/5) unverified -- device accepts but effect unknown.
    Pass None for any temp to send 0x00 (no change).

    Body layout (26 bytes):
        [0]  = 0x40 body_type
        [1]  = flags (default 0x43: bits 0,1,6)
        [2]  = DHW target (linear, temp + 99) or 0x00
        [3]  = 0x00
        [4]  = zone1 target (encoding unverified) or 0x00
        [5]  = zone2 target (encoding unverified) or 0x00
        [6]  = 0x00
        [7]  = room target (temp * 2) or 0x00
        [8-17] = zeros
        [18] = heating water flow target (raw = (temp-9)*2) or 0x00
        [19-23] = zeros
        [24] = 0x05
        [25] = 0x00
    """
    body = bytearray(26)
    body[0] = 0x40
    body[1] = flags & 0xFF
    body[2] = _encode_temp_target(dhw_target_temp) if dhw_target_temp is not None else 0x00
    body[4] = int(zone1_target_temp) & 0xFF if zone1_target_temp is not None else 0x00
    body[5] = int(zone2_target_temp) & 0xFF if zone2_target_temp is not None else 0x00
    body[7] = int(room_target_temp * 2) & 0xFF if room_target_temp is not None else 0x00
    body[18] = _encode_temp_heat(heat_target_temp) if heat_target_temp is not None else 0x00
    body[24] = 0x05
    return build_frame(DEVICE_TYPE_C3, MessageType.SET, bytes(body), protocol_ver=3)


def build_set_silent(silent_mode: bool = False, silent_level: int = 0) -> bytes:
    """Build Set silent mode (body_type=0x05). 9-byte body."""
    body = bytes([0x05, int(silent_mode), silent_level & 0xFF]) + bytes(7)
    return build_frame(DEVICE_TYPE_C3, MessageType.SET, body)


def build_set_eco(eco_mode: bool = False) -> bytes:
    """Build Set ECO mode (body_type=0x07). 6-byte body."""
    body = bytes([0x07, int(eco_mode)]) + bytes(4)
    return build_frame(DEVICE_TYPE_C3, MessageType.SET, body)


def build_set_disinfect(disinfect: bool = False) -> bytes:
    """Build Set disinfect (body_type=0x09). 4-byte body."""
    body = bytes([0x09, int(disinfect)]) + bytes(2)
    return build_frame(DEVICE_TYPE_C3, MessageType.SET, body)


# -- C3 Response Body Parsers --

def _signed_temp(value: int) -> float:
    """Convert unsigned byte to signed temperature (two's complement)."""
    if value > 127:
        return value - 256
    return float(value)


def _temp_with_half(integer_byte: int, decimal_bit: bool = False) -> float:
    """Temperature with optional 0.5 degree precision."""
    temp = _signed_temp(integer_byte)
    if decimal_bit:
        temp += 0.5 if temp >= 0 else -0.5
    return temp


def parse_basic_body(body: bytes) -> dict:
    """Parse BasicBody response (body_type=0x01). 24+ bytes."""
    if len(body) < 21:
        return {"error": f"BasicBody too short: {len(body)} bytes", "raw": body.hex()}

    state = {}
    state["body_type"] = 0x01

    b = body

    state["zone1_power"] = bool(b[1] & 0x01)
    state["zone2_power"] = bool(b[1] & 0x02)
    state["dhw_power"] = bool(b[1] & 0x04)
    state["zone1_curve"] = bool(b[1] & 0x08)
    state["zone2_curve"] = bool(b[1] & 0x10)
    state["disinfect"] = bool(b[1] & 0x20)
    state["fast_dhw"] = bool(b[1] & 0x40)

    state["mode"] = b[2]
    state["mode_str"] = {0: "cool", 1: "heat", 2: "auto"}.get(b[2], f"unknown({b[2]})")

    state["zone1_target_temp"] = _signed_temp(b[3])
    state["zone2_target_temp"] = _signed_temp(b[4])
    state["dhw_target_temp"] = _signed_temp(b[5])
    state["room_target_temp"] = b[6] / 2.0

    state["zone1_water_temp_target"] = _signed_temp(b[7])
    state["zone2_water_temp_target"] = _signed_temp(b[8])

    state["tank_actual_temp"] = _signed_temp(b[9])

    # Status flags
    if len(b) > 10:
        state["zone1_active"] = bool(b[10] & 0x01)
        state["zone2_active"] = bool(b[10] & 0x02)
        state["dhw_active"] = bool(b[10] & 0x04)

    if len(b) > 11:
        state["error_code"] = b[11]

    if len(b) > 12:
        state["zone1_water_temp"] = _signed_temp(b[12])

    if len(b) > 13:
        state["zone2_water_temp"] = _signed_temp(b[13])

    if len(b) > 14:
        state["outdoor_temp"] = _signed_temp(b[14])

    if len(b) > 15:
        state["room_temp"] = b[15] / 2.0

    if len(b) > 16:
        state["tbh"] = bool(b[16] & 0x01)

    if len(b) > 17:
        state["error_code_2"] = b[17]

    # Extended status bytes (if present)
    if len(b) > 18:
        state["compressor_running"] = bool(b[18] & 0x01)
        state["defrosting"] = bool(b[18] & 0x02)

    if len(b) > 19:
        state["zone1_flow_temp"] = _signed_temp(b[19])

    if len(b) > 20:
        state["zone2_flow_temp"] = _signed_temp(b[20])

    return state


def parse_energy_body(body: bytes) -> dict:
    """Parse EnergyBody response (body_type=0x04). 14 bytes."""
    if len(body) < 10:
        return {"error": f"EnergyBody too short: {len(body)} bytes", "raw": body.hex()}

    state = {}
    state["body_type"] = 0x04

    b = body
    state["heating_status"] = bool(b[1] & 0x01)
    state["cooling_status"] = bool(b[1] & 0x02)
    state["dhw_heating_status"] = bool(b[1] & 0x04)

    # Cumulative energy: 4 bytes (big-endian kWh * 100)
    if len(b) >= 6:
        energy_raw = int.from_bytes(b[2:6], "big")
        state["total_energy_kwh"] = energy_raw / 100.0

    if len(b) >= 10:
        heating_energy = int.from_bytes(b[6:10], "big")
        state["heating_energy_kwh"] = heating_energy / 100.0

    if len(b) >= 14:
        state["outdoor_temp"] = _signed_temp(b[13])

    return state


def parse_silence_body(body: bytes) -> dict:
    """Parse SilenceBody response (body_type=0x05)."""
    if len(body) < 3:
        return {"error": f"SilenceBody too short: {len(body)} bytes", "raw": body.hex()}

    state = {}
    state["body_type"] = 0x05
    state["silent_mode"] = bool(body[1])
    state["silent_level"] = body[2]

    if len(body) >= 6:
        state["silent_auto"] = bool(body[3])
        state["silent_timer_on"] = body[4]
        state["silent_timer_off"] = body[5]

    return state


def parse_eco_body(body: bytes) -> dict:
    """Parse ECOBody response (body_type=0x07)."""
    if len(body) < 2:
        return {"error": f"ECOBody too short: {len(body)} bytes", "raw": body.hex()}

    state = {}
    state["body_type"] = 0x07
    state["eco_mode"] = bool(body[1])

    if len(body) >= 4:
        state["eco_timer"] = bool(body[2])
        state["eco_timer_hours"] = body[3]

    return state


def parse_disinfect_body(body: bytes) -> dict:
    """Parse DisinfectBody response (body_type=0x09)."""
    if len(body) < 2:
        return {"error": f"DisinfectBody too short: {len(body)} bytes", "raw": body.hex()}

    state = {}
    state["body_type"] = 0x09
    state["disinfect_on"] = bool(body[1] & 0x01)
    state["disinfect_running"] = bool(body[1] & 0x02)

    if len(body) >= 4:
        state["disinfect_schedule"] = bool(body[2])
        state["disinfect_day"] = body[3]

    return state


def parse_unit_para_body(body: bytes) -> dict:
    """Parse UnitParaBody response (body_type=0x10). 80+ bytes of sensor data."""
    if len(body) < 20:
        return {"error": f"UnitParaBody too short: {len(body)} bytes", "raw": body.hex()}

    state = {}
    state["body_type"] = 0x10

    b = body

    # Compressor
    if len(b) > 2:
        state["compressor_frequency"] = b[1] | (b[2] << 8) if len(b) > 2 else b[1]

    # Temperatures (with sign handling)
    if len(b) > 3:
        state["t1_outdoor_coil_temp"] = _signed_temp(b[3])
    if len(b) > 4:
        state["t2_discharge_temp"] = _signed_temp(b[4])
    if len(b) > 5:
        state["t2b_suction_temp"] = _signed_temp(b[5])
    if len(b) > 6:
        state["t3_condenser_temp"] = _signed_temp(b[6])
    if len(b) > 7:
        state["t4_outdoor_ambient"] = _signed_temp(b[7])
    if len(b) > 8:
        state["t5_exhaust_temp"] = _signed_temp(b[8])

    # Water circuit temperatures
    if len(b) > 9:
        state["tw_in"] = _signed_temp(b[9])
    if len(b) > 10:
        state["tw_out"] = _signed_temp(b[10])

    # More sensor data
    if len(b) > 12:
        state["high_pressure"] = b[11] | (b[12] << 8)

    if len(b) > 14:
        state["low_pressure"] = b[13] | (b[14] << 8)

    if len(b) > 16:
        state["voltage"] = b[15] | (b[16] << 8)

    if len(b) > 18:
        state["current_a"] = (b[17] | (b[18] << 8)) / 10.0

    if len(b) > 20:
        state["flow_rate"] = (b[19] | (b[20] << 8)) / 10.0

    if len(b) > 22:
        state["instant_power_w"] = b[21] | (b[22] << 8)

    # Extended sensors (varies by firmware)
    if len(b) > 24:
        state["eev_opening"] = b[23] | (b[24] << 8)

    if len(b) > 25:
        state["fan_speed_rpm"] = b[25] | (b[26] << 8) if len(b) > 26 else b[25]

    # Tank / DHW temps
    if len(b) > 27:
        state["t_tank_sensor"] = _signed_temp(b[27])

    if len(b) > 28:
        state["t_solar"] = _signed_temp(b[28])

    return state


# -- 0xC0 Status Response (non-standard, used by this heat pump) --

def _decode_temp_xc0(value: int) -> float | None:
    """Decode Midea XC0 temperature encoding: (value - 50) / 2.

    Returns degrees Celsius with 0.5 degree precision. 0xFF/0x00 = not available.
    """
    if value == 0xFF or value == 0x00:
        return None
    return (value - 50) / 2


def _encode_temp_xc0(temp: float) -> int:
    """Encode sensor temperature to XC0 format: raw = temp * 2 + 50."""
    return int(temp * 2 + 50) & 0xFF


def _decode_temp_target(value: int) -> int | None:
    """Decode DHW target setpoint: temp = raw - 99.

    NOT XC0 encoding. C0 byte[2] uses simple linear encoding with offset 99.
    Sensor temps (bytes 11/12/18) still use XC0 (offset 50, /2).

    Verified against all four data points:
        raw=146 → controller=47, raw=144 → controller=45,
        raw=148 → controller=49, raw=150 → controller=51.
    """
    if value == 0xFF or value == 0x00:
        return None
    return value - 99


def _encode_temp_target(temp: float) -> int:
    """Encode DHW target setpoint: raw = temp + 99."""
    return int(temp + 99) & 0xFF


def parse_c0_status_body(body: bytes) -> dict:
    """Parse the non-standard 0xC0 status response from this heat pump.

    This device responds to SET (msg_type=0x02) with a 25-byte 0xC0 body.
    Sensor temps (bytes 11/12/18) use XC0: (value - 50) / 2.
    DHW target (byte 2) uses linear encoding: value - 99.

    Confirmed byte map:
        [0]     = 0xC0 body_type
        [1]     = 0x01 sub-type (bit 0 = power)
        [2]     = DHW target temperature (linear: value - 99)
        [3-10]  = zeros (unused zone/feature fields)
        [11]    = T1: DHW tank temperature (XC0 sensor, drifts)
        [12]    = T2: water circuit temperature (XC0 sensor, drifts)
        [13-17] = zeros
        [18]    = heating water flow target (raw/2 + 9, NOT XC0)
        [19-22] = zeros
        [23-24] = counter/CRC (not temperature)
    """
    if len(body) < 19:
        return {"error": f"C0 body too short: {len(body)} bytes", "raw": body.hex()}

    state = {}
    state["body_type"] = 0xC0

    # byte[1]: power/sub-type
    state["power"] = bool(body[1] & 0x01)

    # byte[2]: DHW target temperature (linear: value - 99)
    state["dhw_target_temp"] = _decode_temp_target(body[2])
    state["dhw_target_raw"] = body[2]

    # Temperature sensors (using XC0 encoding: (v-50)/2)
    if len(body) > 11 and body[11] != 0x00:
        state["t1_dhw_tank"] = _decode_temp_xc0(body[11])
    if len(body) > 12 and body[12] != 0x00:
        state["t2_water_circuit"] = _decode_temp_xc0(body[12])

    # byte[18]: heating water flow target (NOT outdoor temp, NOT XC0)
    if len(body) > 18 and body[18] != 0x00:
        state["heat_target_temp"] = _decode_temp_heat(body[18])
        state["heat_target_raw"] = body[18]

    # bytes[3-10], [13-17], [19-22]: report any non-zero values
    for i in [3, 4, 5, 6, 7, 8, 9, 10, 13, 14, 15, 16, 17, 19, 20, 21, 22]:
        if len(body) > i and body[i] != 0x00:
            state[f"byte_{i}"] = body[i]
            state[f"byte_{i}_temp"] = _decode_temp_xc0(body[i])

    # bytes[23-24] are counter/CRC, not temperature (confirmed by observation)

    return state


def parse_b5_version_body(body: bytes) -> dict:
    """Parse the B5 version/capability response.

    Known response: b5 01 14 02 01 01 c2
    """
    state = {"body_type": 0xB5}

    if len(body) >= 3:
        state["protocol_version"] = body[2]
    if len(body) >= 4:
        state["capabilities_count"] = body[3]

    return state


# -- Working query for this device --

def build_query_status() -> bytes:
    """Query device status. Returns a 0xC0 body with temps and status flags.

    Uses SET msg_type with body [0x01] -- works with all getToken keys.
    """
    return build_frame(DEVICE_TYPE_C3, MessageType.SET, bytes([0x01]))


def build_query_status_v3() -> bytes:
    """Query device status using the app's format (body_type=0x41, protocol_ver=3).

    Same 0xC0 response as build_query_status(). Captured from NetHome Plus via Frida.
    """
    body = bytearray(20)
    body[0] = 0x41
    body[1] = 0x81
    body[3] = 0xFF
    body[4] = 0x03
    body[5] = 0xFF
    body[7] = 0x02
    body[18] = 0x03
    return build_frame(DEVICE_TYPE_C3, MessageType.QUERY, bytes(body))


def build_query_version() -> bytes:
    """Query protocol version (B5). Uses QUERY msg_type."""
    return build_frame(DEVICE_TYPE_C3, MessageType.QUERY, bytes([0xB5]))


def parse_response(data: bytes) -> dict | None:
    """Parse an AA-frame response, dispatching to the appropriate body parser."""
    frame = parse_frame(data)
    if not frame:
        return None

    body = frame["body"]
    if len(body) < 1:
        return {"msg_type": frame["msg_type"], "body": body.hex()}

    body_type = body[0]

    parsers = {
        0x01: parse_basic_body,
        0x04: parse_energy_body,
        0x05: parse_silence_body,
        0x07: parse_eco_body,
        0x09: parse_disinfect_body,
        0x10: parse_unit_para_body,
        0xB5: parse_b5_version_body,
        0xC0: parse_c0_status_body,
    }

    parser = parsers.get(body_type)
    if parser:
        result = parser(body)
        result["msg_type"] = frame["msg_type"]
        return result

    return {
        "msg_type": frame["msg_type"],
        "body_type": body_type,
        "body_hex": body.hex(),
    }


# -- All C3 queries --

ALL_QUERIES = [
    ("basic", build_query_basic),
    ("silence", build_query_silence),
    ("eco", build_query_eco),
    ("disinfect", build_query_disinfect),
    ("unit_para", build_query_unit_para),
]

# Queries that actually work with this device
WORKING_QUERIES = [
    ("status", build_query_status),
    ("version", build_query_version),
]
