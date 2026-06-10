import unittest
from tether.toon import encode, decode

class TestToon(unittest.TestCase):
    def test_primitives(self):
        self.assertEqual(encode(None), "null")
        self.assertEqual(encode(True), "true")
        self.assertEqual(encode(False), "false")
        self.assertEqual(encode(123), "123")
        self.assertEqual(encode(-0.0), "0")
        self.assertEqual(encode(12.34), "12.34")
        self.assertEqual(encode("hello"), "hello")
        self.assertEqual(encode("hello world"), 'hello world')
        self.assertEqual(encode("with:colon"), '"with:colon"')
        self.assertEqual(encode(""), '""')
        
    def test_arrays_primitives(self):
        arr = [1, 2, "three", "four five"]
        encoded = encode(arr)
        # Should be formatted inline with [N]: header
        self.assertEqual(encoded, '[4]: 1,2,three,four five')
        self.assertEqual(decode(encoded), arr)

    def test_empty(self):
        self.assertEqual(encode([]), "[]")
        self.assertEqual(encode({}), "")
        self.assertEqual(decode("[]"), [])
        self.assertEqual(decode(""), {})

    def test_objects(self):
        obj = {"b": 2, "a": 1, "c": {"d": "nested"}}
        encoded = encode(obj)
        # Check alphabetical sorting
        expected = "a: 1\nb: 2\nc:\n  d: nested"
        self.assertEqual(encoded, expected)
        self.assertEqual(decode(encoded), obj)

    def test_tabular(self):
        rows = [
            {"id": 1, "name": "Alice", "active": True},
            {"id": 2, "name": "Bob", "active": False}
        ]
        # Should be encoded as tabular
        encoded = encode(rows)
        # fields sorted alphabetically: active, id, name
        expected = "[2]{active,id,name}:\n  true,1,Alice\n  false,2,Bob"
        self.assertEqual(encoded, expected)
        self.assertEqual(decode(encoded), rows)

    def test_list_items(self):
        # Non-uniform array of objects/mixed
        lst = [
            {"id": 1, "name": "Alice"},
            "primitive_item",
            [1, 2]
        ]
        encoded = encode(lst)
        # Since it's mixed:
        self.assertEqual(decode(encoded), lst)

if __name__ == "__main__":
    unittest.main()
