"""
Midea M-Smart protocol security: AES encryption, 8370 framing, TCP key derivation.
"""

import hashlib
import os
import struct
from Crypto.Cipher import AES


# Fixed protocol constants
MSGTYPE_HANDSHAKE_REQUEST = 0x0
MSGTYPE_HANDSHAKE_RESPONSE = 0x1
MSGTYPE_ENCRYPTED_RESPONSE = 0x3
MSGTYPE_ENCRYPTED_REQUEST = 0x6


class LocalSecurity:
    # Fixed AES-128 key used for local LAN encryption (discovery, AA-frame body)
    BLOCK_SIZE = 16
    AES_KEY = int(141661095494369103254425781617665632877).to_bytes(16, "big")
    # Fixed salt for MD5 checksum in 5A5A packet
    SALT = int(
        233912452794221312800602098970898185176935770387238278451789080441632479840061417076563
    ).to_bytes(36, "big")

    def __init__(self):
        self._tcp_key = None
        self._request_count = 0
        self._response_count = 0

    # -- AES-ECB (local LAN encryption) --

    @staticmethod
    def _pkcs7_pad(data: bytes) -> bytes:
        pad_len = AES.block_size - (len(data) % AES.block_size)
        return data + bytes([pad_len] * pad_len)

    @staticmethod
    def _pkcs7_unpad(data: bytes) -> bytes:
        pad_len = data[-1]
        if pad_len < 1 or pad_len > AES.block_size:
            return data
        if data[-pad_len:] != bytes([pad_len] * pad_len):
            return data
        return data[:-pad_len]

    @classmethod
    def aes_ecb_encrypt(cls, data: bytes) -> bytes:
        cipher = AES.new(cls.AES_KEY, AES.MODE_ECB)
        return cipher.encrypt(cls._pkcs7_pad(data))

    @classmethod
    def aes_ecb_decrypt(cls, data: bytes) -> bytes:
        cipher = AES.new(cls.AES_KEY, AES.MODE_ECB)
        return cls._pkcs7_unpad(cipher.decrypt(data))

    # -- AES-CBC (8370 session encryption) --

    @staticmethod
    def aes_cbc_encrypt(data: bytes, key: bytes) -> bytes:
        """Raw AES-CBC encrypt (NO padding -- callers handle alignment)."""
        iv = b"\x00" * AES.block_size
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        return cipher.encrypt(data)

    @staticmethod
    def aes_cbc_decrypt(data: bytes, key: bytes) -> bytes:
        """Raw AES-CBC decrypt (NO unpadding -- callers handle alignment)."""
        iv = b"\x00" * AES.block_size
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        return cipher.decrypt(data)

    # -- MD5 checksum for 5A5A packet tail --

    @classmethod
    def encode32_data(cls, data: bytes) -> bytes:
        return hashlib.md5(data + cls.SALT).digest()

    # -- 8370 Protocol --

    def tcp_key(self, response: bytes, key: bytes) -> bytes:
        """Derive the TCP session key from the handshake response.

        Accepts either a raw 8370 frame or just the 64-byte payload.
        Payload: 32 bytes AES-CBC encrypted + 32 bytes SHA-256 signature.
        """
        # Strip 8370 header (6 bytes) if present
        if response[:2] == b"\x83\x70":
            # Header is 6 bytes, then 2 bytes request_count, then payload
            data = response[6:]
            # Skip request_count (2 bytes) from the handshake response payload
            if len(data) >= 66:
                data = data[2:]
        else:
            data = response

        if data == b"ERROR":
            raise ValueError("Device returned ERROR - token rejected")

        if len(data) != 64:
            raise ValueError(f"Handshake response wrong length: {len(data)} bytes (need 64)")

        payload = data[:32]
        sign = data[32:64]

        plain = self.aes_cbc_decrypt(payload, key)

        if hashlib.sha256(plain).digest() != sign:
            raise ValueError("Handshake signature verification failed")

        tcp_key = bytes(a ^ b for a, b in zip(plain, key))

        self._tcp_key = tcp_key
        self._request_count = 0
        self._response_count = 0
        return tcp_key

    def encode_8370(self, data: bytes, msgtype: int) -> bytes:
        """Build an 8370 frame.

        Header: [0x83, 0x70] + size(2) + [0x20] + [padding<<4 | msgtype]
        Then: request_count(2) + [padding_bytes] + data [+ encrypted + sha256(32)]
        """
        header = bytearray([0x83, 0x70])
        size = len(data)
        padding = 0

        if msgtype in (MSGTYPE_ENCRYPTED_REQUEST, MSGTYPE_ENCRYPTED_RESPONSE):
            if (size + 2) % 16 != 0:
                padding = 16 - ((size + 2) & 0xF)
                size += padding + 32
            data = data + os.urandom(padding) if padding else data

        header += size.to_bytes(2, "big")
        header.append(0x20)
        header.append(padding << 4 | msgtype)

        data = self._request_count.to_bytes(2, "big") + data
        self._request_count += 1
        if self._request_count >= 0xFFFF:
            self._request_count = 0

        if msgtype in (MSGTYPE_ENCRYPTED_REQUEST, MSGTYPE_ENCRYPTED_RESPONSE):
            sign = hashlib.sha256(header + data).digest()
            data = self.aes_cbc_encrypt(data, self._tcp_key) + sign

        return bytes(header) + data

    def decode_8370(self, data: bytes) -> list[bytes]:
        """Decode one or more 8370 frames from a TCP receive buffer.

        Returns a list of decrypted payloads.
        """
        results = []
        while len(data) >= 6:
            if data[0] != 0x83 or data[1] != 0x70:
                break

            header = data[:6]
            size = int.from_bytes(header[2:4], "big") + 8
            if len(data) < size:
                break

            padding = header[5] >> 4
            msgtype = header[5] & 0xF
            frame_data = data[6:size]

            if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
                sign = frame_data[-32:]
                frame_data = frame_data[:-32]
                frame_data = self.aes_cbc_decrypt(frame_data, self._tcp_key)
                if hashlib.sha256(header + frame_data).digest() != sign:
                    raise ValueError("8370 signature verification failed")
                if padding:
                    frame_data = frame_data[:-padding]

            self._response_count = int.from_bytes(frame_data[:2], "big")
            frame_data = frame_data[2:]
            results.append(frame_data)
            data = data[size:]

        return results
