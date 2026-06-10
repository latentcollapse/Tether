import re

# Delimiters and literals
COMMA = ','
PIPE = '|'
TAB = '\t'
DEFAULT_DELIMITER = COMMA

NUMERIC_LIKE_PATTERN = re.compile(r'^-?\d+(?:\.\d+)?(?:e[+-]?\d+)?$', re.IGNORECASE)
LEADING_ZERO_PATTERN = re.compile(r'^0\d+$')

def escape_string(val: str) -> str:
    res = []
    for c in val:
        if c == '\\':
            res.append('\\\\')
        elif c == '"':
            res.append('\\"')
        elif c == '\n':
            res.append('\\n')
        elif c == '\r':
            res.append('\\r')
        elif c == '\t':
            res.append('\\t')
        elif ord(c) < 32:
            res.append(f'\\u{ord(c):04x}')
        else:
            res.append(c)
    return "".join(res)

def unescape_string(s: str) -> str:
    res = []
    i = 0
    while i < len(s):
        if s[i] == '\\':
            if i + 1 >= len(s):
                raise ValueError("Trailing backslash in string")
            next_char = s[i+1]
            if next_char == 'n':
                res.append('\n')
                i += 2
            elif next_char == 't':
                res.append('\t')
                i += 2
            elif next_char == 'r':
                res.append('\r')
                i += 2
            elif next_char == '\\':
                res.append('\\')
                i += 2
            elif next_char == '"':
                res.append('"')
                i += 2
            elif next_char == 'u':
                if i + 6 > len(s):
                    raise ValueError(f"Truncated \\u escape: {s[i:i+6]}")
                hex_digits = s[i+2:i+6]
                if not re.match(r'^[0-9a-fA-F]{4}$', hex_digits):
                    raise ValueError(f"Invalid hex digits in \\u escape: {hex_digits}")
                code_point = int(hex_digits, 16)
                if 0xD800 <= code_point <= 0xDFFF:
                    raise ValueError("Lone surrogates are not allowed")
                res.append(chr(code_point))
                i += 6
            else:
                raise ValueError(f"Invalid escape sequence: \\{next_char}")
        else:
            res.append(s[i])
            i += 1
    return "".join(res)

def is_safe_unquoted(value: str, delimiter: str = ',') -> bool:
    if not value:
        return False
    if value != value.strip():
        return False
    if value in ("true", "false", "null"):
        return False
    if NUMERIC_LIKE_PATTERN.match(value):
        return False
    if LEADING_ZERO_PATTERN.match(value):
        return False
    if ':' in value:
        return False
    if '"' in value or '\\' in value:
        return False
    if any(c in value for c in ('[', ']', '{', '}')):
        return False
    if any(ord(c) < 32 for c in value):
        return False
    if delimiter in value:
        return False
    if value.startswith('-'):
        return False
    return True

def encode_key(key: str) -> str:
    if re.match(r'^[A-Za-z_][A-Za-z0-9_.]*$', key):
        return key
    return f'"{escape_string(key)}"'

def encode_primitive(value, delimiter: str = ',') -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value == -0.0:
            value = 0.0
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value)
    if isinstance(value, str):
        if is_safe_unquoted(value, delimiter):
            return value
        return f'"{escape_string(value)}"'
    return str(value)

def is_primitive(val) -> bool:
    return val is None or isinstance(val, (bool, int, float, str))

def is_array_of_primitives(lst) -> bool:
    return len(lst) == 0 or all(is_primitive(item) for item in lst)

def is_array_of_arrays(lst) -> bool:
    return len(lst) == 0 or all(isinstance(item, (list, tuple)) for item in lst)

def is_array_of_objects(lst) -> bool:
    return len(lst) == 0 or all(isinstance(item, dict) for item in lst)

def extract_tabular_header(rows) -> list[str] | None:
    if not rows:
        return None
    first_row = rows[0]
    if not isinstance(first_row, dict) or not first_row:
        return None
    first_keys = sorted(first_row.keys())
    for row in rows:
        if not isinstance(row, dict):
            return None
        if len(row) != len(first_keys):
            return None
        if sorted(row.keys()) != first_keys:
            return None
        if not all(is_primitive(row[k]) for k in first_keys):
            return None
    return first_keys

def format_header(length: int, key=None, fields=None, delimiter=','):
    header = ""
    if key is not None:
        header += encode_key(key)
    header += f"[{length}{delimiter if delimiter != ',' else ''}]"
    if fields is not None:
        quoted_fields = [encode_key(f) for f in fields]
        header += f"{{{delimiter.join(quoted_fields)}}}"
    header += ":"
    return header

def encode_and_join_primitives(values, delimiter=','):
    return delimiter.join(encode_primitive(v, delimiter) for v in values)

def encode_object_lines(val, depth, indent_size=2, delimiter=','):
    lines = []
    for key in sorted(val.keys()):
        item = val[key]
        lines.extend(encode_key_value_pair_lines(key, item, depth, indent_size, delimiter))
    return lines

def encode_key_value_pair_lines(key, val, depth, indent_size=2, delimiter=','):
    indentation = ' ' * (indent_size * depth)
    encoded_key = encode_key(key)
    
    if is_primitive(val):
        return [f"{indentation}{encoded_key}: {encode_primitive(val, delimiter)}"]
    elif isinstance(val, (list, tuple)):
        return encode_array_lines(key, val, depth, indent_size, delimiter)
    elif isinstance(val, dict):
        if not val:
            return [f"{indentation}{encoded_key}:"]
        lines = [f"{indentation}{encoded_key}:"]
        lines.extend(encode_object_lines(val, depth + 1, indent_size, delimiter))
        return lines
    else:
        return [f"{indentation}{encoded_key}: {encode_primitive(val, delimiter)}"]

def encode_array_lines(key, val, depth, indent_size=2, delimiter=','):
    indentation = ' ' * (indent_size * depth)
    if not val:
        line = f"{encode_key(key)}: []" if key is not None else "[]"
        return [f"{indentation}{line}"]
        
    if is_array_of_primitives(val):
        header = format_header(len(val), key=key, delimiter=delimiter)
        joined = encode_and_join_primitives(val, delimiter)
        return [f"{indentation}{header} {joined}"]
        
    if is_array_of_arrays(val):
        if all(is_array_of_primitives(arr) for arr in val):
            lines = []
            header = format_header(len(val), key=key, delimiter=delimiter)
            lines.append(f"{indentation}{header}")
            for arr in val:
                line_header = format_header(len(arr), delimiter=delimiter)
                joined = encode_and_join_primitives(arr, delimiter)
                lines.append(f"{' ' * (indent_size * (depth + 1))}- {line_header} {joined}")
            return lines
            
    if is_array_of_objects(val):
        header_keys = extract_tabular_header(val)
        if header_keys is not None:
            header = format_header(len(val), key=key, fields=header_keys, delimiter=delimiter)
            lines = [f"{indentation}{header}"]
            for row in val:
                row_vals = [row[k] for k in header_keys]
                joined = encode_and_join_primitives(row_vals, delimiter)
                lines.append(f"{' ' * (indent_size * (depth + 1))}{joined}")
            return lines
            
    header = format_header(len(val), key=key, delimiter=delimiter)
    lines = [f"{indentation}{header}"]
    for item in val:
        lines.extend(encode_list_item_lines(item, depth + 1, indent_size, delimiter))
    return lines

def encode_list_item_lines(item, depth, indent_size=2, delimiter=','):
    indentation = ' ' * (indent_size * depth)
    if is_primitive(item):
        return [f"{indentation}- {encode_primitive(item, delimiter)}"]
    elif isinstance(item, (list, tuple)):
        if is_array_of_primitives(item):
            header = format_header(len(item), delimiter=delimiter)
            joined = encode_and_join_primitives(item, delimiter)
            return [f"{indentation}- {header} {joined}"]
        else:
            lines = []
            header = format_header(len(item), delimiter=delimiter)
            lines.append(f"{indentation}- {header}")
            for sub in item:
                lines.extend(encode_list_item_lines(sub, depth + 1, indent_size, delimiter))
            return lines
    elif isinstance(item, dict):
        if not item:
            return [f"{indentation}-"]
            
        entries = sorted(item.items(), key=lambda x: x[0])
        first_key, first_val = entries[0]
        rest_entries = entries[1:]
        
        lines = []
        if isinstance(first_val, (list, tuple)) and is_array_of_objects(first_val):
            header_keys = extract_tabular_header(first_val)
            if header_keys is not None:
                formatted_header = format_header(len(first_val), key=first_key, fields=header_keys, delimiter=delimiter)
                lines.append(f"{indentation}- {formatted_header}")
                for row in first_val:
                    row_vals = [row[k] for k in header_keys]
                    joined = encode_and_join_primitives(row_vals, delimiter)
                    lines.append(f"{' ' * (indent_size * (depth + 2))}{joined}")
                if rest_entries:
                    lines.extend(encode_object_lines(dict(rest_entries), depth + 1, indent_size, delimiter))
                return lines
                
        encoded_first_key = encode_key(first_key)
        if is_primitive(first_val):
            lines.append(f"{indentation}- {encoded_first_key}: {encode_primitive(first_val, delimiter)}")
        elif isinstance(first_val, (list, tuple)):
            if not first_val:
                lines.append(f"{indentation}- {encoded_first_key}: []")
            elif is_array_of_primitives(first_val):
                header = format_header(len(first_val), delimiter=delimiter)
                joined = encode_and_join_primitives(first_val, delimiter)
                lines.append(f"{indentation}- {encoded_first_key}{header} {joined}")
            else:
                header = format_header(len(first_val), delimiter=delimiter)
                lines.append(f"{indentation}- {encoded_first_key}{header}")
                for sub in first_val:
                    lines.extend(encode_list_item_lines(sub, depth + 2, indent_size, delimiter))
        elif isinstance(first_val, dict):
            lines.append(f"{indentation}- {encoded_first_key}:")
            if first_val:
                lines.extend(encode_object_lines(first_val, depth + 2, indent_size, delimiter))
                
        if rest_entries:
            lines.extend(encode_object_lines(dict(rest_entries), depth + 1, indent_size, delimiter))
        return lines
    return [f"{indentation}- {encode_primitive(item, delimiter)}"]

def encode(input_val, indent_size=2, delimiter=',') -> str:
    if is_primitive(input_val):
        encoded = encode_primitive(input_val, delimiter)
        return encoded
    if isinstance(input_val, (list, tuple)):
        return "\n".join(encode_array_lines(None, input_val, 0, indent_size, delimiter))
    if isinstance(input_val, dict):
        return "\n".join(encode_object_lines(input_val, 0, indent_size, delimiter))
    return encode_primitive(input_val, delimiter)

# Decoder implementation
def find_closing_quote(content: str, start: int) -> int:
    i = start + 1
    while i < len(content):
        if content[i] == '\\' and i + 1 < len(content):
            i += 2
            continue
        if content[i] == '"':
            return i
        i += 1
    return -1

def find_unquoted_char(content: str, char: str, start: int = 0) -> int:
    in_quotes = False
    i = start
    while i < len(content):
        if content[i] == '\\' and i + 1 < len(content) and in_quotes:
            i += 2
            continue
        if content[i] == '"':
            in_quotes = not in_quotes
            i += 1
            continue
        if content[i] == char and not in_quotes:
            return i
        i += 1
    return -1

def is_key_value_content(content: str) -> bool:
    return find_unquoted_char(content, ':') != -1

def parse_delimited_values(s: str, delimiter: str = ',') -> list[str]:
    values = []
    value_buffer = []
    in_quotes = False
    i = 0
    while i < len(s):
        char = s[i]
        if char == '\\' and i + 1 < len(s) and in_quotes:
            value_buffer.append(char)
            value_buffer.append(s[i+1])
            i += 2
            continue
        if char == '"':
            in_quotes = not in_quotes
            value_buffer.append(char)
            i += 1
            continue
        if char == delimiter and not in_quotes:
            values.append("".join(value_buffer).strip())
            value_buffer = []
            i += 1
            continue
        value_buffer.append(char)
        i += 1
    if value_buffer or values:
        values.append("".join(value_buffer).strip())
    return values

def parse_string_literal(token: str) -> str:
    trimmedToken = token.strip()
    if trimmedToken.startswith('"'):
        closingQuoteIndex = find_closing_quote(trimmedToken, 0)
        if closingQuoteIndex == -1:
            raise ValueError(f"Unterminated string: {trimmedToken}")
        if closingQuoteIndex != len(trimmedToken) - 1:
            raise ValueError(f"Unexpected characters after closing quote in: {trimmedToken}")
        content = trimmedToken[1:-1]
        return unescape_string(content)
    return trimmedToken

def parse_primitive_token(token: str) -> any:
    trimmedToken = token.strip()
    if not trimmedToken:
        return ""
    if trimmedToken == "[]":
        return []
    if trimmedToken == "{}":
        return {}
    if trimmedToken.startswith('"'):
        return parse_string_literal(trimmedToken)
    if trimmedToken == "true":
        return True
    if trimmedToken == "false":
        return False
    if trimmedToken == "null":
        return None
    if NUMERIC_LIKE_PATTERN.match(trimmedToken):
        try:
            val = float(trimmedToken)
            if val.is_integer():
                return int(val)
            return val
        except ValueError:
            pass
    return trimmedToken

def parse_array_header_line(content: str, default_delimiter: str = ',') -> dict | None:
    trimmed = content.lstrip(' ')
    if not trimmed:
        return None
    
    bracket_start = -1
    if trimmed.startswith('"'):
        closing_quote = find_closing_quote(trimmed, 0)
        if closing_quote == -1:
            return None
        after_quote = trimmed[closing_quote+1:]
        if not after_quote.startswith('['):
            return None
        bracket_start = content.find('[', len(content) - len(trimmed) + closing_quote + 1)
    else:
        bracket_start = content.find('[')
    
    if bracket_start == -1:
        return None
    
    bracket_end = content.find(']', bracket_start)
    if bracket_end == -1:
        return None
    
    brace_start = content.find('{', bracket_end)
    brace_end = bracket_end + 1
    colon_search_start = bracket_end + 1
    
    fields = None
    fields_content = None
    if brace_start != -1:
        first_colon = content.find(':', bracket_end)
        if first_colon == -1 or brace_start < first_colon:
            found_brace_end = content.find('}', brace_start)
            if found_brace_end != -1:
                brace_end = found_brace_end + 1
                colon_search_start = brace_end
                fields_content = content[brace_start+1:found_brace_end]
    
    colon_index = content.find(':', colon_search_start)
    if colon_index == -1:
        return None
    
    key_part = content[:bracket_start].strip()
    key = None
    if key_part:
        if key_part.startswith('"'):
            key = parse_string_literal(key_part)
        else:
            key = key_part
            
    bracket_content = content[bracket_start+1:bracket_end]
    length_str = bracket_content
    delimiter = default_delimiter
    if length_str.endswith('|'):
        delimiter = '|'
        length_str = length_str[:-1]
    elif length_str.endswith('\t') or length_str.endswith('\\t'):
        delimiter = '\t'
        length_str = length_str[:-1]
    elif length_str.endswith(','):
        delimiter = ','
        length_str = length_str[:-1]
        
    try:
        length = int(length_str)
    except ValueError:
        return None
        
    if fields_content is not None:
        fields = [parse_string_literal(f.strip()) for f in parse_delimited_values(fields_content, delimiter)]
        
    inline_values = content[colon_index+1:].strip()
    
    return {
        "key": key,
        "length": length,
        "delimiter": delimiter,
        "fields": fields,
        "inline_values": inline_values if inline_values else None
    }

class ToonParser:
    def __init__(self, text: str, indent_size: int = 2):
        self.lines = []
        for line in text.splitlines():
            # Keep original trailing whitespace but strip carriage returns
            line_val = line.replace('\r', '').rstrip()
            if line_val.strip():
                self.lines.append(line_val)
        self.indent_size = indent_size
        self.index = 0

    def peek_line(self):
        if self.index < len(self.lines):
            return self.lines[self.index]
        return None

    def get_line_info(self, line):
        if line is None:
            return None, None
        lstripped = line.lstrip(' ')
        indent = len(line) - len(lstripped)
        depth = indent // self.indent_size
        return lstripped, depth

    def consume_line(self):
        line = self.peek_line()
        if line is not None:
            self.index += 1
        return line

    def parse(self):
        line = self.peek_line()
        if line is None:
            return {}
        content, depth = self.get_line_info(line)
        array_header = parse_array_header_line(content)
        if array_header is not None and array_header["key"] is None:
            self.consume_line()
            return self.parse_array_content(array_header, 0)
        return self.parse_value_at_depth(0)

    def parse_value_at_depth(self, current_depth: int):
        line = self.peek_line()
        if line is None:
            return None
        content, depth = self.get_line_info(line)
        if depth != current_depth:
            return None

        if content.startswith('-'):
            return self.parse_list_at_depth(current_depth)

        array_header = parse_array_header_line(content)
        if array_header is not None:
            self.consume_line()
            return self.parse_array_content(array_header, current_depth)

        if is_key_value_content(content):
            return self.parse_object_at_depth(current_depth)

        self.consume_line()
        return parse_primitive_token(content)

    def parse_array_content(self, header: dict, current_depth: int):
        length = header["length"]
        delimiter = header["delimiter"]
        fields = header["fields"]
        inline_values = header["inline_values"]
        
        if inline_values is not None:
            val_strings = parse_delimited_values(inline_values, delimiter)
            return [parse_primitive_token(v) for v in val_strings]
        
        if length == 0:
            return []
            
        if fields is not None:
            rows = []
            for _ in range(length):
                row_line = self.consume_line()
                if row_line is None:
                    break
                row_content, row_depth = self.get_line_info(row_line)
                val_strings = parse_delimited_values(row_content, delimiter)
                row_obj = {}
                for f, val_str in zip(fields, val_strings):
                    row_obj[f] = parse_primitive_token(val_str)
                rows.append(row_obj)
            return rows
        else:
            return self.parse_list_at_depth(current_depth + 1)

    def parse_list_at_depth(self, current_depth: int) -> list:
        items = []
        while True:
            line = self.peek_line()
            if line is None:
                break
            content, depth = self.get_line_info(line)
            if depth != current_depth:
                break
            if not content.startswith('-'):
                break
                
            self.consume_line()
            item_content = content[1:]
            if item_content.startswith(' '):
                item_content = item_content[1:]
                
            if item_content:
                if is_key_value_content(item_content):
                    array_header = parse_array_header_line(item_content)
                    if array_header is not None and array_header["key"] is None:
                        items.append(self.parse_array_content(array_header, current_depth))
                    else:
                        colon_idx = find_unquoted_char(item_content, ':')
                        key_part = item_content[:colon_idx].strip()
                        if array_header is not None and array_header["key"] is not None:
                            key = array_header["key"]
                        else:
                            key = parse_string_literal(key_part) if key_part.startswith('"') else key_part
                        val_part = item_content[colon_idx+1:].strip()
                        
                        obj = {}
                        if array_header is not None:
                            obj[key] = self.parse_array_content(array_header, current_depth)
                        else:
                            if val_part:
                                if val_part == '[]':
                                    obj[key] = []
                                else:
                                    obj[key] = parse_primitive_token(val_part)
                            else:
                                next_line = self.peek_line()
                                if next_line is not None:
                                    _, next_depth = self.get_line_info(next_line)
                                    if next_depth == current_depth + 1:
                                        obj[key] = self.parse_value_at_depth(current_depth + 1)
                                    else:
                                        obj[key] = ""
                                else:
                                    obj[key] = ""
                                    
                        rest_obj = self.parse_object_at_depth(current_depth + 1)
                        obj.update(rest_obj)
                        items.append(obj)
                else:
                    items.append(parse_primitive_token(item_content))
            else:
                next_line = self.peek_line()
                if next_line is not None:
                    _, next_depth = self.get_line_info(next_line)
                    if next_depth == current_depth + 1:
                        items.append(self.parse_value_at_depth(current_depth + 1))
                    else:
                        items.append(None)
                else:
                    items.append(None)
        return items

    def parse_object_at_depth(self, current_depth: int) -> dict:
        obj = {}
        while True:
            line = self.peek_line()
            if line is None:
                break
            content, depth = self.get_line_info(line)
            if depth != current_depth:
                break
            
            if content.startswith('-'):
                break
                
            array_header = parse_array_header_line(content)
            if array_header is not None and array_header["key"] is None:
                break
                
            if not is_key_value_content(content):
                break
                
            colon_idx = find_unquoted_char(content, ':')
            if colon_idx == -1:
                break
                
            key_part = content[:colon_idx].strip()
            if array_header is not None and array_header["key"] is not None:
                key = array_header["key"]
            else:
                key = parse_string_literal(key_part) if key_part.startswith('"') else key_part
            
            self.consume_line()
            inline_part = content[colon_idx+1:].strip()
            
            if array_header is not None:
                obj[key] = self.parse_array_content(array_header, current_depth)
            else:
                if inline_part:
                    if inline_part == '[]':
                        obj[key] = []
                    else:
                        obj[key] = parse_primitive_token(inline_part)
                else:
                    next_line = self.peek_line()
                    if next_line is not None:
                        _, next_depth = self.get_line_info(next_line)
                        if next_depth == current_depth + 1:
                            obj[key] = self.parse_value_at_depth(current_depth + 1)
                        else:
                            obj[key] = ""
                    else:
                        obj[key] = ""
        return obj

def decode(toon_str: str, indent_size: int = 2) -> any:
    parser = ToonParser(toon_str, indent_size)
    return parser.parse()
