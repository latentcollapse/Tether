"""Tether Runtime - content-addressable storage with handles."""

import json
import hashlib
from pathlib import Path
from typing import Any, Dict
from .lc import encode_lc_b, decode_lc_b
from .exceptions import E_HANDLE_INVALID, E_HANDLE_UNRESOLVED
from .handles import (
    BLOB_PREFIX,
    INLINE_PREFIX,
    LEGACY_MESSAGES_PREFIX,
    TREE_PREFIX,
    canonical_json,
    digest12,
    kvfold_dir,
    suffix,
)

CONTRACT_JSON = 99
_MISSING = object()


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
        self._inline_table: Dict[str, Any] = {}
        self._kvfold_dir = kvfold_dir(Path("kvfold"))
    
    def _compute_handle_id(self, data: bytes) -> str:
        """Compute deterministic handle ID from content."""
        try:
            import blake3
            return blake3.blake3(data).hexdigest()[:12]
        except ImportError:
            import hashlib
            return hashlib.blake2b(data, digest_size=6).hexdigest()
    
    def collapse(self, table: str | Any, value: Any = _MISSING) -> str:
        """
        Collapse a value into a handle in the specified table.
        
        Args:
            table: Table name (e.g., "messages", "schemas", "context")
            value: Python value to collapse (JSON-compatible)
            
        Returns:
            Handle string in format &h_<table>_<id>
        """
        if value is _MISSING:
            return self.collapse_inline(table)

        table = str(table)
        if table not in self._tables:
            self._tables[table] = {}
        
        contract_value = json_to_contract(value)
        lc_bytes = encode_lc_b(contract_value)
        handle_id = self._compute_handle_id(lc_bytes)
        handle = f"h&l_{table}_{handle_id}"
        
        self._tables[table][handle] = lc_bytes
        self._content_table[handle] = value
        
        return handle

    def collapse_inline(self, value: str | dict[str, Any]) -> str:
        """Collapse a small JSON-serializable value into an inline handle."""
        data = canonical_json(value)
        handle = f"{INLINE_PREFIX}{digest12(data)}"
        self._inline_table[handle] = value
        return handle

    def collapse_blob(self, data: bytes, content_type: str) -> str:
        """Collapse binary data into KVFold and return a blob handle."""
        digest = digest12(data)
        handle = f"{BLOB_PREFIX}{digest}"
        (self._kvfold_dir / digest).write_bytes(data)
        (self._kvfold_dir / f"{digest}.toml").write_text(
            f"handle = {json.dumps(handle)}\ncontent_type = {json.dumps(content_type)}\n",
            encoding="utf-8",
        )
        return handle

    def collapse_tree(self, handles: list[str]) -> str:
        """Collapse an ordered list of handles into KVFold and return a tree handle."""
        data = canonical_json(handles)
        digest = digest12(data)
        handle = f"{TREE_PREFIX}{digest}"
        (self._kvfold_dir / digest).write_bytes(data)
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

        if handle.startswith(INLINE_PREFIX):
            try:
                return self._inline_table[handle]
            except KeyError as exc:
                raise E_HANDLE_UNRESOLVED(f"Handle not found: {handle}") from exc

        if handle.startswith(BLOB_PREFIX):
            return (self._kvfold_dir / suffix(handle, BLOB_PREFIX)).read_bytes()

        if handle.startswith(TREE_PREFIX):
            raw = (self._kvfold_dir / suffix(handle, TREE_PREFIX)).read_bytes()
            children = json.loads(raw.decode("utf-8"))
            if not isinstance(children, list):
                raise ValueError(f"tree handle does not contain a list: {handle}")
            return [self.resolve(str(child)) for child in children]

        if (
            not handle.startswith(LEGACY_MESSAGES_PREFIX)
            and handle not in self._content_table
            and not any(handle in table_data for table_data in self._tables.values())
        ):
            raise ValueError(f"unknown handle prefix: {handle}")
        
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
