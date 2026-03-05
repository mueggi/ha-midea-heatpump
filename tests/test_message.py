"""Tests for midea message building and parsing."""

import pytest

from custom_components.midea_heatpump.midea.message import (
    DEVICE_TYPE_C3,
    MessageType,
    checksum,
    build_frame,
    parse_frame,
    build_query_basic,
    build_query_silence,
    build_query_eco,
    build_query_disinfect,
    build_query_unit_para,
    build_query_appliance,
    build_query_status,
    build_query_status_v3,
    build_query_version,
    build_set_command,
    build_set_silent,
    build_set_eco,
    build_set_disinfect,
    parse_response,
    parse_basic_body,
    parse_energy_body,
    parse_silence_body,
    parse_eco_body,
    parse_disinfect_body,
    parse_unit_para_body,
    parse_c0_status_body,
    parse_b5_version_body,
    _encode_temp_heat,
    _decode_temp_heat,
    _decode_temp_xc0,
    _encode_temp_xc0,
    _decode_temp_target,
    _encode_temp_target,
    _signed_temp,
    _temp_with_half,
)


# -- Checksum --

class TestChecksum:
    def test_basic(self):
        data = bytes([0xAA, 0x01, 0x02, 0x03])
        cs = checksum(data)
        assert cs == (~(0x01 + 0x02 + 0x03) + 1) & 0xFF

    def test_zero_body(self):
        data = bytes([0xAA, 0x00])
        assert checksum(data) == 0x00


# -- Temperature encoding/decoding --

class TestTempEncodings:
    """Test the various temperature encoding schemes."""

    def test_xc0_roundtrip(self):
        for temp in [20.0, 25.5, 0.0, -5.0, 50.0]:
            raw = _encode_temp_xc0(temp)
            decoded = _decode_temp_xc0(raw)
            assert decoded == temp

    def test_xc0_sentinel_values(self):
        assert _decode_temp_xc0(0xFF) is None
        assert _decode_temp_xc0(0x00) is None

    def test_target_roundtrip(self):
        for temp in [30, 45, 50, 65]:
            raw = _encode_temp_target(temp)
            decoded = _decode_temp_target(raw)
            assert decoded == temp

    def test_target_sentinel_values(self):
        assert _decode_temp_target(0xFF) is None
        assert _decode_temp_target(0x00) is None

    def test_heat_encode_known_values(self):
        """Verified values from docstring."""
        assert _encode_temp_heat(39.0) == 60
        assert _encode_temp_heat(42.0) == 66
        assert _encode_temp_heat(47.0) == 76

    def test_heat_decode_known_values(self):
        assert _decode_temp_heat(60) == 39.0
        assert _decode_temp_heat(66) == 42.0
        assert _decode_temp_heat(76) == 47.0

    def test_heat_roundtrip(self):
        for temp in [25.0, 30.0, 39.0, 47.0, 55.0]:
            raw = _encode_temp_heat(temp)
            decoded = _decode_temp_heat(raw)
            assert decoded == temp

    def test_heat_sentinel_values(self):
        assert _decode_temp_heat(0xFF) is None
        assert _decode_temp_heat(0x00) is None

    def test_signed_temp(self):
        assert _signed_temp(25) == 25.0
        assert _signed_temp(0) == 0.0
        assert _signed_temp(127) == 127.0
        assert _signed_temp(128) == -128.0
        assert _signed_temp(255) == -1.0
        assert _signed_temp(200) == -56.0

    def test_temp_with_half(self):
        assert _temp_with_half(25, False) == 25.0
        assert _temp_with_half(25, True) == 25.5
        assert _temp_with_half(200, False) == -56.0  # signed
        assert _temp_with_half(200, True) == -56.5  # signed negative + half


# -- Frame building/parsing --

class TestFrame:
    def test_build_frame_structure(self):
        body = bytes([0x01])
        frame = build_frame(DEVICE_TYPE_C3, MessageType.QUERY, body)
        assert frame[0] == 0xAA
        assert frame[2] == DEVICE_TYPE_C3
        assert frame[9] == MessageType.QUERY
        assert frame[1] == len(frame) - 1  # length excludes checksum byte

    def test_parse_frame_roundtrip(self):
        body = bytes([0x01, 0x02, 0x03])
        frame = build_frame(DEVICE_TYPE_C3, MessageType.SET, body)
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed["device_type"] == DEVICE_TYPE_C3
        assert parsed["msg_type"] == MessageType.SET
        assert parsed["body"] == body

    def test_parse_frame_too_short(self):
        assert parse_frame(bytes([0xAA, 0x05])) is None

    def test_parse_frame_wrong_magic(self):
        assert parse_frame(bytes([0xBB] + [0] * 15)) is None

    def test_parse_frame_truncated(self):
        frame = build_frame(DEVICE_TYPE_C3, MessageType.QUERY, bytes([0x01]))
        truncated = frame[:5]
        assert parse_frame(truncated) is None


# -- Query builders --

class TestQueryBuilders:
    def test_query_basic(self):
        frame = build_query_basic()
        parsed = parse_frame(frame)
        assert parsed["msg_type"] == MessageType.QUERY
        assert parsed["body"] == bytes([0x01])

    def test_query_silence(self):
        frame = build_query_silence()
        parsed = parse_frame(frame)
        assert parsed["body"] == bytes([0x05])

    def test_query_eco(self):
        frame = build_query_eco()
        parsed = parse_frame(frame)
        assert parsed["body"] == bytes([0x07])

    def test_query_disinfect(self):
        frame = build_query_disinfect()
        parsed = parse_frame(frame)
        assert parsed["body"] == bytes([0x09])

    def test_query_unit_para(self):
        frame = build_query_unit_para()
        parsed = parse_frame(frame)
        assert parsed["body"] == bytes([0x10])

    def test_query_appliance(self):
        frame = build_query_appliance()
        parsed = parse_frame(frame)
        assert parsed["msg_type"] == MessageType.QUERY_APPLIANCE

    def test_query_status(self):
        frame = build_query_status()
        parsed = parse_frame(frame)
        assert parsed["msg_type"] == MessageType.SET
        assert parsed["body"] == bytes([0x01])

    def test_query_status_v3(self):
        frame = build_query_status_v3()
        parsed = parse_frame(frame)
        assert parsed["msg_type"] == MessageType.QUERY
        assert parsed["body"][0] == 0x41

    def test_query_version(self):
        frame = build_query_version()
        parsed = parse_frame(frame)
        assert parsed["body"] == bytes([0xB5])


# -- Set command builders --

class TestSetCommands:
    def test_set_dhw_target(self):
        frame = build_set_command(dhw_target_temp=47.0)
        parsed = parse_frame(frame)
        assert parsed["msg_type"] == MessageType.SET
        assert parsed["protocol_ver"] == 3
        body = parsed["body"]
        assert body[0] == 0x40
        assert body[2] == _encode_temp_target(47.0)

    def test_set_heat_target(self):
        frame = build_set_command(heat_target_temp=39.0)
        parsed = parse_frame(frame)
        body = parsed["body"]
        assert body[18] == _encode_temp_heat(39.0)

    def test_set_both_targets(self):
        frame = build_set_command(dhw_target_temp=50.0, heat_target_temp=42.0)
        parsed = parse_frame(frame)
        body = parsed["body"]
        assert body[2] == _encode_temp_target(50.0)
        assert body[18] == _encode_temp_heat(42.0)

    def test_set_none_targets_are_zero(self):
        frame = build_set_command()
        parsed = parse_frame(frame)
        body = parsed["body"]
        assert body[2] == 0x00
        assert body[18] == 0x00

    def test_set_silent(self):
        frame = build_set_silent(silent_mode=True, silent_level=2)
        parsed = parse_frame(frame)
        body = parsed["body"]
        assert body[0] == 0x05
        assert body[1] == 1
        assert body[2] == 2

    def test_set_eco(self):
        frame = build_set_eco(eco_mode=True)
        parsed = parse_frame(frame)
        body = parsed["body"]
        assert body[0] == 0x07
        assert body[1] == 1

    def test_set_disinfect(self):
        frame = build_set_disinfect(disinfect=True)
        parsed = parse_frame(frame)
        body = parsed["body"]
        assert body[0] == 0x09
        assert body[1] == 1


# -- Response body parsers --

class TestParseC0Status:
    def _make_c0_body(self, length=25, **overrides):
        body = bytearray(length)
        body[0] = 0xC0
        body[1] = 0x01  # power on
        body[2] = _encode_temp_target(47)  # DHW target
        body[11] = _encode_temp_xc0(35.0)  # t2 water circuit
        body[12] = _encode_temp_xc0(45.0)  # t1 DHW tank
        body[18] = _encode_temp_heat(39.0)  # heating target
        for k, v in overrides.items():
            body[int(k)] = v
        return bytes(body)

    def test_parse_c0_basic(self):
        body = self._make_c0_body()
        result = parse_c0_status_body(body)
        assert result["body_type"] == 0xC0
        assert result["power"] is True
        assert result["dhw_target_temp"] == 47
        assert result["t2_water_circuit"] == 35.0
        assert result["t1_dhw_tank"] == 45.0
        assert result["heat_target_temp"] == 39.0

    def test_parse_c0_power_off(self):
        body = self._make_c0_body()
        body = bytearray(body)
        body[1] = 0x00
        result = parse_c0_status_body(bytes(body))
        assert result["power"] is False

    def test_parse_c0_too_short(self):
        result = parse_c0_status_body(bytes([0xC0] * 5))
        assert "error" in result

    def test_parse_c0_nonzero_unknown_bytes(self):
        body = self._make_c0_body()
        body = bytearray(body)
        body[5] = 0x42
        result = parse_c0_status_body(bytes(body))
        assert result["byte_5"] == 0x42


class TestParseBasicBody:
    def _make_basic_body(self, length=21):
        body = bytearray(length)
        body[0] = 0x01
        body[1] = 0x07  # zone1 + zone2 + dhw power
        body[2] = 1     # heat mode
        body[3] = 40    # zone1 target
        body[5] = 50    # dhw target
        body[9] = 45    # tank actual
        return bytes(body)

    def test_parse_basic(self):
        body = self._make_basic_body()
        result = parse_basic_body(body)
        assert result["body_type"] == 0x01
        assert result["zone1_power"] is True
        assert result["zone2_power"] is True
        assert result["dhw_power"] is True
        assert result["mode_str"] == "heat"
        assert result["dhw_target_temp"] == 50.0
        assert result["tank_actual_temp"] == 45.0

    def test_parse_basic_too_short(self):
        result = parse_basic_body(bytes([0x01] * 5))
        assert "error" in result

    def test_parse_basic_extended(self):
        body = bytearray(self._make_basic_body(25))
        body[10] = 0x03  # zone1 + zone2 active
        body[14] = 10    # outdoor temp
        body[18] = 0x01  # compressor running
        result = parse_basic_body(bytes(body))
        assert result["zone1_active"] is True
        assert result["zone2_active"] is True
        assert result["outdoor_temp"] == 10.0
        assert result["compressor_running"] is True


class TestParseEnergyBody:
    def test_parse_energy(self):
        body = bytearray(14)
        body[0] = 0x04
        body[1] = 0x01  # heating
        body[2:6] = (12345).to_bytes(4, "big")  # total energy
        result = parse_energy_body(bytes(body))
        assert result["body_type"] == 0x04
        assert result["heating_status"] is True
        assert result["total_energy_kwh"] == 123.45

    def test_parse_energy_too_short(self):
        result = parse_energy_body(bytes([0x04] * 3))
        assert "error" in result


class TestParseSilenceBody:
    def test_parse_silence(self):
        body = bytes([0x05, 0x01, 0x02, 0x00, 10, 22])
        result = parse_silence_body(body)
        assert result["silent_mode"] is True
        assert result["silent_level"] == 2
        assert result["silent_timer_on"] == 10
        assert result["silent_timer_off"] == 22

    def test_parse_silence_too_short(self):
        result = parse_silence_body(bytes([0x05]))
        assert "error" in result


class TestParseEcoBody:
    def test_parse_eco(self):
        body = bytes([0x07, 0x01, 0x01, 0x04])
        result = parse_eco_body(body)
        assert result["eco_mode"] is True
        assert result["eco_timer"] is True
        assert result["eco_timer_hours"] == 4

    def test_parse_eco_too_short(self):
        result = parse_eco_body(bytes([0x07]))
        assert "error" in result


class TestParseDisinfectBody:
    def test_parse_disinfect(self):
        body = bytes([0x09, 0x03, 0x01, 0x05])
        result = parse_disinfect_body(body)
        assert result["disinfect_on"] is True
        assert result["disinfect_running"] is True
        assert result["disinfect_schedule"] is True
        assert result["disinfect_day"] == 5

    def test_parse_disinfect_too_short(self):
        result = parse_disinfect_body(bytes([0x09]))
        assert "error" in result


class TestParseUnitParaBody:
    def test_parse_unit_para(self):
        body = bytearray(30)
        body[0] = 0x10
        body[1] = 50   # compressor freq low byte
        body[2] = 0    # compressor freq high byte
        body[7] = 15   # outdoor ambient
        body[9] = 35   # tw_in
        body[10] = 40  # tw_out
        result = parse_unit_para_body(bytes(body))
        assert result["body_type"] == 0x10
        assert result["compressor_frequency"] == 50
        assert result["t4_outdoor_ambient"] == 15.0
        assert result["tw_in"] == 35.0
        assert result["tw_out"] == 40.0

    def test_parse_unit_para_too_short(self):
        result = parse_unit_para_body(bytes([0x10] * 5))
        assert "error" in result


class TestParseB5Version:
    def test_parse_b5(self):
        body = bytes([0xB5, 0x01, 0x14, 0x02, 0x01, 0x01, 0xC2])
        result = parse_b5_version_body(body)
        assert result["body_type"] == 0xB5
        assert result["protocol_version"] == 0x14
        assert result["capabilities_count"] == 0x02


# -- parse_response dispatch --

class TestParseResponse:
    def test_dispatches_to_c0(self):
        body = bytearray(25)
        body[0] = 0xC0
        body[1] = 0x01
        body[2] = _encode_temp_target(47)
        frame = build_frame(DEVICE_TYPE_C3, MessageType.SET, bytes(body))
        result = parse_response(frame)
        assert result is not None
        assert result["body_type"] == 0xC0
        assert result["dhw_target_temp"] == 47

    def test_dispatches_to_basic(self):
        body = bytearray(21)
        body[0] = 0x01
        body[1] = 0x01
        body[2] = 1
        frame = build_frame(DEVICE_TYPE_C3, MessageType.NOTIFY1, bytes(body))
        result = parse_response(frame)
        assert result["body_type"] == 0x01

    def test_unknown_body_type(self):
        body = bytes([0xFE, 0x01, 0x02])
        frame = build_frame(DEVICE_TYPE_C3, MessageType.QUERY, body)
        result = parse_response(frame)
        assert result is not None
        assert result["body_type"] == 0xFE
        assert "body_hex" in result

    def test_invalid_frame(self):
        result = parse_response(bytes([0x00, 0x01]))
        assert result is None

    def test_empty_body(self):
        frame = build_frame(DEVICE_TYPE_C3, MessageType.QUERY, bytes())
        result = parse_response(frame)
        assert result is not None
        assert "body" in result
