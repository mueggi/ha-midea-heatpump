"""Tests for midea security module."""

import os
import pytest

from custom_components.midea_heatpump.midea.security import (
    LocalSecurity,
    MSGTYPE_HANDSHAKE_REQUEST,
    MSGTYPE_ENCRYPTED_REQUEST,
    MSGTYPE_ENCRYPTED_RESPONSE,
)


class TestAesEcb:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = b"Hello Midea ATW!"
        encrypted = LocalSecurity.aes_ecb_encrypt(plaintext)
        decrypted = LocalSecurity.aes_ecb_decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_various_lengths(self):
        for length in [1, 15, 16, 17, 31, 32, 100]:
            data = os.urandom(length)
            encrypted = LocalSecurity.aes_ecb_encrypt(data)
            assert len(encrypted) % 16 == 0
            decrypted = LocalSecurity.aes_ecb_decrypt(encrypted)
            assert decrypted == data

    def test_encrypt_deterministic(self):
        data = b"same input every time"
        assert LocalSecurity.aes_ecb_encrypt(data) == LocalSecurity.aes_ecb_encrypt(data)


class TestAesCbc:
    def test_encrypt_decrypt_roundtrip(self):
        key = os.urandom(16)
        data = os.urandom(32)  # must be block-aligned (no padding)
        encrypted = LocalSecurity.aes_cbc_encrypt(data, key)
        decrypted = LocalSecurity.aes_cbc_decrypt(encrypted, key)
        assert decrypted == data


class TestEncode32:
    def test_returns_16_bytes(self):
        result = LocalSecurity.encode32_data(b"test data")
        assert len(result) == 16

    def test_deterministic(self):
        data = b"packet content"
        assert LocalSecurity.encode32_data(data) == LocalSecurity.encode32_data(data)

    def test_different_input_different_output(self):
        assert LocalSecurity.encode32_data(b"a") != LocalSecurity.encode32_data(b"b")


class TestPkcs7:
    def test_pad_unpad_roundtrip(self):
        for length in [1, 5, 15, 16, 17, 31, 32]:
            data = os.urandom(length)
            padded = LocalSecurity._pkcs7_pad(data)
            assert len(padded) % 16 == 0
            unpadded = LocalSecurity._pkcs7_unpad(padded)
            assert unpadded == data

    def test_pad_exact_block(self):
        data = os.urandom(16)
        padded = LocalSecurity._pkcs7_pad(data)
        assert len(padded) == 32  # full block of padding added


class Test8370Protocol:
    def _make_session(self):
        """Create a paired request/response security instance with a shared key."""
        key = os.urandom(16)
        sender = LocalSecurity()
        sender._tcp_key = key
        sender._request_count = 0
        sender._response_count = 0
        receiver = LocalSecurity()
        receiver._tcp_key = key
        receiver._request_count = 0
        receiver._response_count = 0
        return sender, receiver

    def test_handshake_frame_structure(self):
        sec = LocalSecurity()
        token = os.urandom(64)
        frame = sec.encode_8370(token, MSGTYPE_HANDSHAKE_REQUEST)
        assert frame[:2] == b"\x83\x70"
        assert frame[4] == 0x20
        assert frame[5] & 0xF == MSGTYPE_HANDSHAKE_REQUEST

    def test_encrypted_roundtrip(self):
        sender, receiver = self._make_session()
        payload = b"test payload data for heat pump"
        encoded = sender.encode_8370(payload, MSGTYPE_ENCRYPTED_REQUEST)
        assert encoded[:2] == b"\x83\x70"
        decoded = receiver.decode_8370(encoded)
        assert len(decoded) == 1
        assert decoded[0] == payload

    def test_multiple_messages(self):
        sender, receiver = self._make_session()
        payloads = [b"msg1_data", b"second_message_here", b"third"]
        combined = b""
        for p in payloads:
            combined += sender.encode_8370(p, MSGTYPE_ENCRYPTED_REQUEST)
        decoded = receiver.decode_8370(combined)
        assert len(decoded) == len(payloads)
        for i, p in enumerate(payloads):
            assert decoded[i] == p

    def test_request_count_increments(self):
        sender, _ = self._make_session()
        assert sender._request_count == 0
        sender.encode_8370(b"a", MSGTYPE_ENCRYPTED_REQUEST)
        assert sender._request_count == 1
        sender.encode_8370(b"b", MSGTYPE_ENCRYPTED_REQUEST)
        assert sender._request_count == 2

    def test_request_count_wraps(self):
        sender, _ = self._make_session()
        sender._request_count = 0xFFFE
        sender.encode_8370(b"a", MSGTYPE_ENCRYPTED_REQUEST)
        # 0xFFFE + 1 = 0xFFFF, which is >= 0xFFFF, so it wraps to 0
        assert sender._request_count == 0
        sender.encode_8370(b"b", MSGTYPE_ENCRYPTED_REQUEST)
        assert sender._request_count == 1

    def test_decode_truncated_frame(self):
        sender, receiver = self._make_session()
        encoded = sender.encode_8370(b"data", MSGTYPE_ENCRYPTED_REQUEST)
        truncated = encoded[:10]
        decoded = receiver.decode_8370(truncated)
        assert decoded == []

    def test_decode_bad_magic(self):
        decoded = LocalSecurity().decode_8370(b"\x00\x00\x00\x00\x00\x00")
        assert decoded == []

    def test_tcp_key_derivation(self):
        """Test tcp_key with a synthetic handshake response."""
        import hashlib

        key = os.urandom(16)
        # Plain must be 32 bytes (2 AES blocks) to produce 32-byte encrypted + 32-byte sign = 64 bytes
        plain = os.urandom(32)
        sign = hashlib.sha256(plain).digest()
        encrypted = LocalSecurity.aes_cbc_encrypt(plain, key)
        response = encrypted + sign

        sec = LocalSecurity()
        tcp_key = sec.tcp_key(response, key)
        expected = bytes(a ^ b for a, b in zip(plain[:16], key))
        assert tcp_key == expected
        assert sec._tcp_key == expected

    def test_tcp_key_with_8370_header(self):
        """Test tcp_key strips 8370 header correctly."""
        import hashlib

        key = os.urandom(16)
        plain = os.urandom(32)
        sign = hashlib.sha256(plain).digest()
        encrypted = LocalSecurity.aes_cbc_encrypt(plain, key)
        payload = encrypted + sign

        # Build an 8370 frame: header(6) + request_count(2) + payload(64)
        header = b"\x83\x70" + (len(payload) + 2).to_bytes(2, "big") + b"\x20\x01"
        request_count = b"\x00\x00"
        response = header + request_count + payload

        sec = LocalSecurity()
        tcp_key = sec.tcp_key(response, key)
        expected = bytes(a ^ b for a, b in zip(plain[:16], key))
        assert tcp_key == expected

    def test_tcp_key_rejects_error(self):
        sec = LocalSecurity()
        with pytest.raises(ValueError, match="ERROR"):
            sec.tcp_key(b"ERROR", os.urandom(16))

    def test_tcp_key_rejects_wrong_length(self):
        sec = LocalSecurity()
        with pytest.raises(ValueError, match="wrong length"):
            sec.tcp_key(os.urandom(32), os.urandom(16))

    def test_tcp_key_rejects_bad_signature(self):
        key = os.urandom(16)
        plain = os.urandom(32)
        encrypted = LocalSecurity.aes_cbc_encrypt(plain, key)
        bad_sign = os.urandom(32)
        response = encrypted + bad_sign

        sec = LocalSecurity()
        with pytest.raises(ValueError, match="signature"):
            sec.tcp_key(response, key)
