"""Tether Runtime - content-addressable storage with handles."""

import json
import hashlib
from typing import Any, Dict, Optional, Union
from .lc import encode_lc_b, decode_lc_b
from .exceptions import E_HANDLE_INVALID, E_HANDLE_UNRESOLVED

CONTRACT_JSON = 99


def json_to_contract(value: Any) -> Any:
    """Convert JSON-compatible Python value to Tether contract format.
    
    Plain dicts/lists are wrapped in CONTRACT_JSON (99) with JSON as TEXT.
    This preserves exact JSON structure with sorted keys for determinism.
    """
    if isinstance(value, dict):
        if len(value) == 1 and "HANDLE_REF" in value:
            return value
        json_str = json.dumps(value, separators=(",", ":"), sort_keys=True)
        return {CONTRACT_JSON: {"@0": json_str}}
    elif isinstance(value, list):
        json_str = json.dumps(value, separators=(",", ":"), sort_keys=False)
        return {CONTRACT_JSON: {"@0": json_str}}
    else:
        return value


def contract_to_json(value: Any) -> Any:
    """Convert Tether contract format back to JSON.
    
    If contract 99 contains a JSON string, parse it back.
    """
    if isinstance(value, dict):
        # Check for contract 99 (int or string key)
        contract_key = value.get(CONTRACT_JSON) or value.get(str(CONTRACT_JSON))
        if contract_key is not None:
            if isinstance(contract_key, dict) and "@0" in contract_key:
                json_str = contract_key["@0"]
                if isinstance(json_str, str):
                    return json.loads(json_str)
        return {k: contract_to_json(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [contract_to_json(item) for item in value]
    else:
        return value


class Runtime:
    """
    Tether Runtime - manages latent tables and handle resolution.
    
    Example:
        rt = Runtime()
        handle = rt.collapse("messages", {"role": "system", "content": "..."})
        # handle = "&h_messages_abc123"
        
        resolved = rt.resolve(handle)
        # resolved = {"role": "system", "content": "..."}
    """
    
    def __init__(self):
        self._tables: Dict[str, Dict[str, bytes]] = {}
        self._content_table: Dict[str, Any] = {}
    
    def _compute_handle_id(self, data: bytes) -> str:
        """Compute deterministic handle ID from content."""
        try:
            import blake3
            return blake3.blake3(data).hexdigest()[:12]
        except ImportError:
            import hashlib
            return hashlib.blake2b(data, digest_size=6).hexdigest()
    
    def collapse(self, table: str, value: Any) -> str:
        """
        Collapse a value into a handle in the specified table.
        
        Args:
            table: Table name (e.g., "messages", "schemas", "context")
            value: Python value to collapse (JSON-compatible)
            
        Returns:
            Handle string in format &h_<table>_<id>
        """
        if table not in self._tables:
            self._tables[table] = {}
        
        contract_value = json_to_contract(value)
        lc_bytes = encode_lc_b(contract_value)
        handle_id = self._compute_handle_id(lc_bytes)
        handle = f"h&l_{table}_{handle_id}"
        
        self._tables[table][handle] = lc_bytes
        self._content_table[handle] = value
        
        return handle
    
    def resolve(self, handle: str) -> Any:
        """
        Resolve a handle back to its original value.
        
        Args:
            handle: Handle string (e.g., "&h_messages_abc123")
            
        Returns:
            Original Python value
            
        Raises:
            E_HANDLE_UNRESOLVED: Handle not found in any table
        """
        if not handle.startswith("h&l_"):
            raise E_HANDLE_INVALID(f"Invalid handle format: {handle}")
        
        if handle in self._content_table:
            return self._content_table[handle]
        
        for table_data in self._tables.values():
            if handle in table_data:
                lc_bytes = table_data[handle]
                contract_value = decode_lc_b(lc_bytes)
                return contract_to_json(contract_value)
        
        raise E_HANDLE_UNRESOLVED(f"Handle not found: {handle}")
    
    def get(self, handle: str, default: Any = None) -> Any:
        """Resolve with default if not found."""
        try:
            return self.resolve(handle)
        except E_HANDLE_UNRESOLVED:
            return default
    
    def snapshot(self, table: str) -> Dict[str, Any]:
        """Get all handles and values in a table."""
        result = {}
        for handle in self._tables.get(table, {}).keys():
            result[handle] = self.resolve(handle)
        return result
    
    def export_table(self, table: str) -> Dict[str, bytes]:
        """Export table as LC-B bytes (for persistence)."""
        return dict(self._tables.get(table, {}))
    
    def import_table(self, table: str, data: Dict[str, bytes]):
        """Import table from LC-B bytes."""
        self._tables[table] = dict(data)
        for handle, lc_bytes in data.items():
            contract_value = decode_lc_b(lc_bytes)
            self._content_table[handle] = contract_to_json(contract_value)
    
    def merge(self, other: "Runtime"):
        """Merge another runtime's tables into this one."""
        for table, data in other._tables.items():
            if table not in self._tables:
                self._tables[table] = {}
            self._tables[table].update(data)
        self._content_table.update(other._content_table)
    
    def tables(self) -> list[str]:
        """List all table names."""
        return list(self._tables.keys())
    
    def handles(self, table: str) -> list[str]:
        """List all handles in a table."""
        return list(self._tables.get(table, {}).keys())
