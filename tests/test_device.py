"""Tests for MideaATWDevice and PacketBuilder."""

import socket
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from custom_components.midea_heatpump.midea.device import MideaATWDevice, PacketBuilder
from custom_components.midea_heatpump.midea.security import LocalSecurity
from custom_components.midea_heatpump.midea.message import (
    build_frame,
    DEVICE_TYPE_C3,
    MessageType,
    _encode_temp_target,
    _encode_temp_xc0,
    _encode_temp_heat,
)


FAKE_TOKEN = "aa" * 32
FAKE_KEY = "bb" * 16
FAKE_DEVICE_ID = 12345


def make_device(**kwargs):
    defaults = dict(
        ip="192.168.1.100",
        port=6444,
        device_id=FAKE_DEVICE_ID,
        token=FAKE_TOKEN,
        key=FAKE_KEY,
    )
    defaults.update(kwargs)
    return MideaATWDevice(**defaults)


# -- PacketBuilder --

class TestPacketBuilder:
    def test_build_structure(self):
        command = build_frame(DEVICE_TYPE_C3, MessageType.SET, bytes([0x01]))
        packet = PacketBuilder.build(12345, command)
        assert packet[:2] == b"\x5a\x5a"
        length = int.from_bytes(packet[4:6], "little")
        assert length == len(packet)

    def test_build_device_id(self):
        device_id = 0x123456
        command = build_frame(DEVICE_TYPE_C3, MessageType.SET, bytes([0x01]))
        packet = PacketBuilder.build(device_id, command)
        stored_id = int.from_bytes(packet[20:28], "little")
        assert stored_id == device_id

    def test_build_unpack_roundtrip(self):
        command = build_frame(DEVICE_TYPE_C3, MessageType.SET, bytes([0x01]))
        packet = PacketBuilder.build(12345, command)
        unpacked = PacketBuilder.unpack(packet)
        assert unpacked is not None
        assert unpacked == command

    def test_unpack_too_short(self):
        assert PacketBuilder.unpack(b"\x5a\x5a\x00") is None

    def test_unpack_wrong_magic(self):
        assert PacketBuilder.unpack(b"\x00\x00" + b"\x00" * 60) is None

    def test_unpack_bad_encrypted_length(self):
        # Build a packet where encrypted portion has wrong alignment
        data = b"\x5a\x5a" + b"\x00" * 38 + b"\x01" * 15 + b"\x00" * 16
        assert PacketBuilder.unpack(data) is None


# -- MideaATWDevice --

class TestDeviceConnect:
    @patch("custom_components.midea_heatpump.midea.device.socket.socket")
    def test_connect_success(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        # Build a valid handshake response (32-byte encrypted + 32-byte SHA256 = 64 bytes)
        import hashlib
        key = bytes.fromhex(FAKE_KEY)
        plain = b"\x00" * 32
        sign = hashlib.sha256(plain).digest()
        encrypted = LocalSecurity.aes_cbc_encrypt(plain, key)
        mock_sock.recv.return_value = encrypted + sign

        device = make_device()
        device.connect()

        mock_sock.connect.assert_called_once_with(("192.168.1.100", 6444))
        mock_sock.send.assert_called_once()
        assert device._sock is mock_sock

    @patch("custom_components.midea_heatpump.midea.device.socket.socket")
    def test_connect_failure_leaves_sock_none(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.connect.side_effect = OSError("Connection refused")

        device = make_device()
        with pytest.raises(OSError):
            device.connect()

        assert device._sock is None
        mock_sock.close.assert_called_once()

    @patch("custom_components.midea_heatpump.midea.device.socket.socket")
    def test_connect_handshake_failure_leaves_sock_none(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.recv.return_value = b""  # empty handshake response

        device = make_device()
        with pytest.raises(ConnectionError):
            device.connect()

        assert device._sock is None

    @patch("custom_components.midea_heatpump.midea.device.socket.socket")
    def test_connect_closes_old_socket(self, mock_socket_cls):
        old_sock = MagicMock()
        new_sock = MagicMock()
        mock_socket_cls.return_value = new_sock
        new_sock.connect.side_effect = OSError("fail")

        device = make_device()
        device._sock = old_sock

        with pytest.raises(OSError):
            device.connect()

        old_sock.close.assert_called_once()


class TestDeviceClose:
    def test_close(self):
        device = make_device()
        mock_sock = MagicMock()
        device._sock = mock_sock
        device.close()
        mock_sock.close.assert_called_once()
        assert device._sock is None

    def test_close_no_socket(self):
        device = make_device()
        device.close()  # should not raise


class TestDeviceQueryStatus:
    def _setup_connected_device(self, mock_socket_cls):
        """Set up a device that appears connected."""
        device = make_device()
        mock_sock = MagicMock()
        device._sock = mock_sock
        device._security = LocalSecurity()
        device._security._tcp_key = b"\x00" * 16
        return device, mock_sock

    @patch("custom_components.midea_heatpump.midea.device.socket.socket")
    def test_query_returns_c0_data(self, mock_socket_cls):
        device, mock_sock = self._setup_connected_device(mock_socket_cls)

        # Build a C0 response
        c0_body = bytearray(25)
        c0_body[0] = 0xC0
        c0_body[1] = 0x01
        c0_body[2] = _encode_temp_target(47)
        c0_body[11] = _encode_temp_xc0(35.0)
        c0_body[12] = _encode_temp_xc0(45.0)
        c0_body[18] = _encode_temp_heat(39.0)
        aa_frame = build_frame(DEVICE_TYPE_C3, MessageType.SET, bytes(c0_body))
        packet = PacketBuilder.build(FAKE_DEVICE_ID, aa_frame)

        # Wrap in 8370
        encrypted = device._security.encode_8370(packet, 0x3)  # encrypted response
        mock_sock.recv.return_value = encrypted

        result = device.query_status()
        assert result["body_type"] == 0xC0
        assert result["dhw_target_temp"] == 47
        assert result["t1_dhw_tank"] == 45.0
        assert result["heat_target_temp"] == 39.0

    @patch("custom_components.midea_heatpump.midea.device.socket.socket")
    def test_query_reconnects_on_failure(self, mock_socket_cls):
        """Test that _send_with_retry calls _do_connect on failure."""
        device = make_device()
        device._sock = MagicMock()
        device._security = LocalSecurity()
        device._security._tcp_key = b"\x00" * 16

        # Patch _do_connect and _send_and_receive to verify retry behavior
        connect_called = False
        original_send = device._send_and_receive

        call_count = 0

        def fake_send_and_receive(cmd):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("broken pipe")
            # Second call succeeds - return empty (no parsed results)
            return []

        def fake_do_connect():
            nonlocal connect_called
            connect_called = True
            device._sock = MagicMock()
            device._security = LocalSecurity()
            device._security._tcp_key = b"\x00" * 16

        device._send_and_receive = fake_send_and_receive
        device._do_connect = fake_do_connect

        result = device.query_status()
        assert connect_called


class TestDeviceSetAttribute:
    def _setup_connected_device(self):
        device = make_device()
        mock_sock = MagicMock()
        device._sock = mock_sock
        device._security = LocalSecurity()
        device._security._tcp_key = b"\x00" * 16
        return device, mock_sock

    def _make_c0_response(self, device, dhw_target=47, heat_target=39.0):
        c0_body = bytearray(25)
        c0_body[0] = 0xC0
        c0_body[1] = 0x01
        c0_body[2] = _encode_temp_target(dhw_target)
        c0_body[18] = _encode_temp_heat(heat_target)
        aa_frame = build_frame(DEVICE_TYPE_C3, MessageType.SET, bytes(c0_body))
        packet = PacketBuilder.build(FAKE_DEVICE_ID, aa_frame)
        return device._security.encode_8370(packet, 0x3)

    def test_set_unsupported_attribute(self):
        device, _ = self._setup_connected_device()
        with pytest.raises(ValueError, match="Unsupported"):
            device.set_attribute("nonexistent", 42)

    def test_set_eco_mode(self):
        device, mock_sock = self._setup_connected_device()
        encrypted = self._make_c0_response(device)
        mock_sock.recv.return_value = encrypted
        result = device.set_attribute("eco_mode", True)
        assert mock_sock.send.called

    def test_set_silent_mode(self):
        device, mock_sock = self._setup_connected_device()
        encrypted = self._make_c0_response(device)
        mock_sock.recv.return_value = encrypted
        result = device.set_attribute("silent_mode", True)
        assert mock_sock.send.called

    def test_set_disinfect(self):
        device, mock_sock = self._setup_connected_device()
        encrypted = self._make_c0_response(device)
        mock_sock.recv.return_value = encrypted
        result = device.set_attribute("disinfect", True)
        assert mock_sock.send.called

    def test_set_dhw_target_queries_current_state(self):
        """Setting dhw_target should query current state first to echo heat_target."""
        device, mock_sock = self._setup_connected_device()
        # Two recv calls: one for _query_current_state, one for the SET
        encrypted = self._make_c0_response(device)
        mock_sock.recv.side_effect = [encrypted, encrypted]
        device.set_attribute("dhw_target_temp", 50)
        # Should have sent twice: query + set
        assert mock_sock.send.call_count == 2

    def test_set_heat_target_queries_current_state(self):
        device, mock_sock = self._setup_connected_device()
        encrypted = self._make_c0_response(device)
        mock_sock.recv.side_effect = [encrypted, encrypted]
        device.set_attribute("heat_target_temp", 42.0)
        assert mock_sock.send.call_count == 2


class TestDeviceMsgId:
    def test_msg_id_increments(self):
        device = make_device()
        assert device._next_msg_id() == 1
        assert device._next_msg_id() == 2

    def test_msg_id_wraps(self):
        device = make_device()
        device._msg_id = 0xFFFF
        assert device._next_msg_id() == 0
