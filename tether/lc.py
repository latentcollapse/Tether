"""LC-B binary encoding/decoding."""

import struct
from typing import Any, Union, List, Dict
from .exceptions import E_LC_BINARY_DECODE, E_FIELD_ORDER, E_CONTRACT_STRUCTURE


def encode_varint(value: int) -> bytes:
    """Encode integer as unsigned LEB128."""
    if value < 0:
        raise E_LC_BINARY_DECODE("Signed LEB128 not implemented")
    result = []
    while True:
        byte = value & 0x7F
        value >>= 7
        if value == 0:
            result.append(byte)
            break
        result.append(byte | 0x80)
    return bytes(result)


def decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    """Decode unsigned LEB128. Returns (value, new_pos)."""
    result = 0
    shift = 0
    original_pos = pos
    
    while True:
        if pos >= len(data):
            raise E_LC_BINARY_DECODE(f"Truncated varint at position {original_pos}")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
        if shift > 63:
            raise E_LC_BINARY_DECODE(f"Overlong varint at position {original_pos}")
    
    return result, pos


def encode_value(value: Any) -> bytes:
    """Encode a Python value to LC-B format."""
    if value is None:
        return b""
    elif isinstance(value, bool):
        return bytes([0x0A, 0x01 if value else 0x00])
    elif isinstance(value, int):
        return bytes([0x01]) + encode_varint(value)
    elif isinstance(value, float):
        return bytes([0x02]) + struct.pack(">d", value)
    elif isinstance(value, str):
        encoded = value.encode("utf-8")
        return bytes([0x03]) + encode_varint(len(encoded)) + encoded
    elif isinstance(value, bytes):
        return bytes([0x04]) + encode_varint(len(value)) + value
    elif isinstance(value, list):
        parts = [bytes([0x05])]
        for item in value:
            parts.append(encode_value(item))
        parts.append(bytes([0x06]))
        return b"".join(parts)
    elif isinstance(value, dict):
        if "HANDLE_REF" in value:
            handle = value["HANDLE_REF"]
            handle_bytes = handle.encode("ascii")
            return bytes([0x09]) + encode_varint(len(handle_bytes)) + handle_bytes
        
        if len(value) == 1:
            for contract_id_str, fields in value.items():
                contract_id = int(contract_id_str)
                parts = [bytes([0x07]), encode_varint(contract_id)]
                if fields:
                    if not isinstance(fields, dict):
                        raise E_CONTRACT_STRUCTURE(f"Fields must be dict, got {type(fields)}")
                    sorted_fields = sorted(fields.items(), key=lambda x: int(x[0].lstrip("@")))
                    for field_key, field_value in sorted_fields:
                        field_idx = int(field_key.lstrip("@"))
                        parts.append(encode_varint(field_idx))
                        parts.append(encode_value(field_value))
                parts.append(bytes([0x08]))
                return b"".join(parts)
        
        raise E_CONTRACT_STRUCTURE("Object must have exactly one contract key")
    else:
        raise E_LC_BINARY_DECODE(f"Unsupported type: {type(value)}")


def decode_value(data: bytes, pos: int = 0) -> tuple[Any, int]:
    """Decode LC-B value. Returns (value, new_pos)."""
    if pos >= len(data):
        raise E_LC_BINARY_DECODE("Unexpected end of data")
    
    tag = data[pos]
    pos += 1
    
    if tag == 0x01:
        value, pos = decode_varint(data, pos)
        return value, pos
    elif tag == 0x0A:
        if pos >= len(data):
            raise E_LC_BINARY_DECODE("Truncated bool")
        value = data[pos] != 0
        return value, pos + 1
    elif tag == 0x02:
        if pos + 8 > len(data):
            raise E_LC_BINARY_DECODE("Truncated float")
        value = struct.unpack(">d", data[pos:pos + 8])[0]
        return value, pos + 8
    elif tag == 0x03:
        length, pos = decode_varint(data, pos)
        if pos + length > len(data):
            raise E_LC_BINARY_DECODE("Truncated string")
        value = data[pos:pos + length].decode("utf-8")
        return value, pos + length
    elif tag == 0x04:
        length, pos = decode_varint(data, pos)
        if pos + length > len(data):
            raise E_LC_BINARY_DECODE("Truncated bytes")
        value = data[pos:pos + length]
        return value, pos + length
    elif tag == 0x05:
        result = []
        while pos < len(data) and data[pos] != 0x06:
            value, pos = decode_value(data, pos)
            result.append(value)
        if pos >= len(data):
            raise E_LC_BINARY_DECODE("Unterminated array")
        pos += 1
        return result, pos
    elif tag == 0x07:
        contract_id, pos = decode_varint(data, pos)
        fields = {}
        while pos < len(data) and data[pos] != 0x08:
            field_idx, pos = decode_varint(data, pos)
            field_value, pos = decode_value(data, pos)
            fields[f"@{field_idx}"] = field_value
        if pos >= len(data):
            raise E_LC_BINARY_DECODE("Unterminated object")
        pos += 1
        return {str(contract_id): fields}, pos
    elif tag == 0x09:
        length, pos = decode_varint(data, pos)
        if pos + length > len(data):
            raise E_LC_BINARY_DECODE("Truncated handle ref")
        handle = data[pos:pos + length].decode("ascii")
        return {"HANDLE_REF": handle}, pos + length
    else:
        raise E_LC_BINARY_DECODE(f"Unknown tag: 0x{tag:02X}")


def encode_lc_b(value: Any) -> bytes:
    """Encode Python value to LC-B binary."""
    return encode_value(value)


def decode_lc_b(data: Union[bytes, str]) -> Any:
    """Decode LC-B binary to Python value."""
    if isinstance(data, str):
        data = bytes.fromhex(data.replace(" ", ""))
    return decode_value(data)[0]
