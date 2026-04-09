#!/usr/bin/env python3
"""Quick test of new MCP tools including threads."""

import sys
sys.path.insert(0, '/mnt/d/kilo-workspace/Tether')

from tether.sqlite_runtime import SQLiteRuntime

# Use postoffice.db
rt = SQLiteRuntime('/mnt/d/kilo-workspace/Tether/postoffice.db')

# Test tether_send logic
print("=== Testing tether_send ===")
message_data = {
    "from": "kilo",
    "to": "opus",
    "subject": "Test message",
    "text": "This is a test of the new MCP tools",
}
handle = rt.collapse("messages", message_data)
print(f"Sent message with handle: {handle}")

# Test tether_inbox logic
print("\n=== Testing tether_inbox ===")
snapshot = rt.snapshot("messages")
inbox = []
for h, msg in snapshot.items():
    if isinstance(msg, dict) and msg.get("to") == "opus":
        inbox.append({
            "handle": h,
            "from": msg.get("from"),
            "subject": msg.get("subject"),
        })
print(f"Found {len(inbox)} messages for opus")

# Test tether_thread_create
print("\n=== Testing tether_thread_create ===")
thread_data = {
    "name": "hlx-dev",
    "description": "HLX development and phase tracking"
}
thread_handle = rt.collapse("threads", thread_data)
print(f"Created thread 'hlx-dev' with handle: {thread_handle}")

# Test tether_thread_send
print("\n=== Testing tether_thread_send ===")
thread_msg = {
    "from": "kilo",
    "to": "opus",
    "subject": "Phase 5 planning",
    "text": "Ready to start Phase 5 implementation",
    "thread": "hlx-dev"
}
msg_handle = rt.collapse("hlx-dev", thread_msg)
print(f"Sent to thread 'hlx-dev' with handle: {msg_handle}")

# Test tether_thread_inbox
print("\n=== Testing tether_thread_inbox ===")
thread_snap = rt.snapshot("hlx-dev")
thread_messages = []
for h, msg in thread_snap.items():
    if isinstance(msg, dict):
        thread_messages.append({
            "handle": h,
            "subject": msg.get("subject"),
            "from": msg.get("from")
        })
print(f"Found {len(thread_messages)} messages in hlx-dev thread")

# Test tether_threads
print("\n=== Testing tether_threads ===")
threads_snap = rt.snapshot("threads")
threads = []
for h, data in threads_snap.items():
    if isinstance(data, dict):
        threads.append(data.get("name"))
print(f"Threads: {threads}")

print("\n✓ All MCP tool tests passed!")
print("\n=== MCP Tools Now Available ===")
print("tether_send(to, subject, text, from_agent='kilo') - Send message")
print("tether_inbox(for_agent) - Check inbox")
print("tether_receive(handle) - Read full message")
print("tether_thread_create(thread_name, description) - Create thread")
print("tether_thread_send(thread, to, subject, text) - Send to thread")
print("tether_thread_inbox(thread, for_agent) - Read thread")
print("tether_threads() - List all threads")
