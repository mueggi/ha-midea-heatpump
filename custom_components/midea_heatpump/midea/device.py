"""Thread-safe Midea ATW heat pump device wrapper for Home Assistant."""

import logging
import socket
import threading
import time
from datetime import datetime, timezone

from .security import (
    LocalSecurity,
    MSGTYPE_HANDSHAKE_REQUEST,
    MSGTYPE_ENCRYPTED_REQUEST,
)
from .message import (
    build_query_basic,
    build_query_status,
    build_set_command,
    build_set_eco,
    build_set_silent,
    build_set_disinfect,
    parse_response,
)

_LOGGER = logging.getLogger(__name__)


class PacketBuilder:
    """Builds the 5A5A outer packet that wraps an encrypted AA-frame."""

    @staticmethod
    def build(device_id: int, command: bytes, msg_id: int = 0) -> bytes:
        """Build a 5A5A packet containing an AES-ECB encrypted command.

        40-byte header + encrypted body + 16-byte MD5 tail.
        """
        encrypted = LocalSecurity.aes_ecb_encrypt(command)

        header = bytearray([
            0x5A, 0x5A, 0x01, 0x11,  # magic + msg_type
            0x00, 0x00,               # packet length (filled below)
            0x20, 0x00,               # reserved
            0x00, 0x00, 0x00, 0x00,   # message ID
            0x00, 0x00, 0x00, 0x00,   # timestamp (8 bytes)
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,   # device ID (8 bytes LE)
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,   # padding
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
        ])

        # Device ID: 8 bytes LE at offset 20
        header[20:28] = device_id.to_bytes(8, "little")

        # Timestamp: reversed BCD date/time (8 bytes at offset 12)
        t = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S%f")[:16]
        ts_bytes = bytearray()
        for i in range(0, len(t), 2):
            ts_bytes.insert(0, int(t[i:i + 2]))
        header[12:20] = ts_bytes

        # Packet length at offset 4 (total = header + encrypted + 16-byte tail)
        total_length = len(header) + len(encrypted) + 16
        header[4:6] = total_length.to_bytes(2, "little")

        packet = bytes(header) + encrypted

        # 16-byte MD5 checksum tail
        tail = LocalSecurity.encode32_data(packet)
        return packet + tail

    @staticmethod
    def unpack(data: bytes) -> bytes | None:
        """Extract and decrypt the AA-frame from a 5A5A packet."""
        if len(data) < 56 or data[:2] != b"\x5a\x5a":
            return None

        encrypted = data[40:-16]
        if len(encrypted) < 16 or len(encrypted) % 16 != 0:
            return None

        return LocalSecurity.aes_ecb_decrypt(encrypted)


class MideaATWDevice:
    """Thread-safe Midea ATW heat pump device connection."""

    def __init__(
        self,
        ip: str,
        port: int,
        device_id: int,
        token: str,
        key: str,
    ) -> None:
        self._ip = ip
        self._port = port
        self._device_id = int(device_id)
        self._token = bytes.fromhex(token)
        self._key = bytes.fromhex(key)
        self._sock: socket.socket | None = None
        self._security = LocalSecurity()
        self._lock = threading.Lock()
        self._msg_id = 0

    def connect(self) -> None:
        """Connect and perform 8370 handshake. Thread-safe."""
        with self._lock:
            self._do_connect()

    def _do_connect(self) -> None:
        """Internal connect. Caller must hold lock."""
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

        self._security = LocalSecurity()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(10.0)
        self._sock.connect((self._ip, self._port))

        request = self._security.encode_8370(self._token, MSGTYPE_HANDSHAKE_REQUEST)
        self._sock.send(request)

        response = self._sock.recv(1024)
        if not response:
            raise ConnectionError("No handshake response received")

        self._security.tcp_key(response, self._key)
        _LOGGER.debug("Connected to %s:%s", self._ip, self._port)

    def close(self) -> None:
        """Close the TCP connection. Thread-safe."""
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None

    def _next_msg_id(self) -> int:
        self._msg_id = (self._msg_id + 1) & 0xFFFF
        return self._msg_id

    def _send_and_receive(self, command: bytes) -> list[dict]:
        """Send command and receive response. Caller must hold lock."""
        if not self._sock:
            raise ConnectionError("Not connected")

        packet = PacketBuilder.build(self._device_id, command, self._next_msg_id())
        encrypted = self._security.encode_8370(packet, MSGTYPE_ENCRYPTED_REQUEST)
        self._sock.send(encrypted)
        time.sleep(0.3)

        self._sock.settimeout(5.0)
        data = self._sock.recv(4096)
        if not data:
            return []

        results = []
        payloads = self._security.decode_8370(data)
        for payload in payloads:
            if payload[:2] == b"\x5a\x5a":
                aa_frame = PacketBuilder.unpack(payload)
                if aa_frame:
                    parsed = parse_response(aa_frame)
                    if parsed:
                        results.append(parsed)
            else:
                parsed = parse_response(payload)
                if parsed:
                    results.append(parsed)
        return results

    def _send_with_retry(self, command: bytes) -> list[dict]:
        """Send with auto-reconnect on failure. Caller must hold lock."""
        try:
            return self._send_and_receive(command)
        except (ConnectionError, OSError) as err:
            _LOGGER.debug("Connection error, reconnecting: %s", err)
            self._do_connect()
            return self._send_and_receive(command)

    def _query_current_state(self) -> dict:
        """Query current state for echoing fields in SET. Caller must hold lock."""
        try:
            responses = self._send_and_receive(build_query_status())
            for r in responses:
                if r.get("body_type") == 0xC0:
                    return r
        except (ConnectionError, OSError):
            pass
        return {}

    def query_status(self) -> dict:
        """Query device status. Merges C0 + basic body data. Thread-safe."""
        with self._lock:
            state = {}

            # C0 status (sensor temps, always works)
            responses = self._send_with_retry(build_query_status())
            for r in responses:
                if r.get("body_type") == 0xC0:
                    state.update(r)
                    break

            # Basic status (target temps with accurate encoding)
            try:
                responses = self._send_and_receive(build_query_basic())
                for r in responses:
                    if r.get("body_type") == 0x01:
                        state.update(r)
                        break
            except (ConnectionError, OSError):
                _LOGGER.debug("Basic query failed, using C0 data only")

            return state

    def set_attribute(self, name: str, value) -> dict:
        """Set a device attribute. Returns response dict. Thread-safe.

        IMPORTANT: 0x7F is NOT a safe "no change" sentinel for this device.
        It gets interpreted as a temperature value and overwrites DHW target.
        We always echo the current DHW target when setting other fields.
        """
        with self._lock:
            if name in ("dhw_target_temp", "zone1_target_temp"):
                # Query current state to echo DHW + outdoor temp
                current = self._query_current_state()
                kwargs = {name: float(value)}
                # Always echo current DHW to prevent overwrite
                if name != "dhw_target_temp":
                    dhw = current.get("dhw_target_temp")
                    if dhw is not None:
                        kwargs["dhw_target_temp"] = dhw
                outdoor = current.get("t3_outdoor")
                if outdoor is not None:
                    kwargs["outdoor_temp"] = outdoor
                cmd = build_set_command(**kwargs)

            elif name == "eco_mode":
                cmd = build_set_eco(eco_mode=bool(value))

            elif name == "silent_mode":
                cmd = build_set_silent(silent_mode=bool(value))

            elif name == "disinfect":
                cmd = build_set_disinfect(disinfect=bool(value))

            else:
                raise ValueError(f"Unsupported attribute: {name}")

            responses = self._send_with_retry(cmd)
            for r in responses:
                if r.get("body_type") == 0xC0:
                    return r
            return responses[0] if responses else {}
