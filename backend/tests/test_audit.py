import pytest
import json
import hashlib
from app.api.endpoints import generate_audit_hash

def test_audit_hash_chaining():
    event_A = {"file": "a.jpg"}
    event_B = {"confidence": 0.95}
    event_C = {"passed": True}

    # Generate A
    hash_A = generate_audit_hash("EVENT_A", event_A, None)
    
    # Generate B using A's hash
    hash_B = generate_audit_hash("EVENT_B", event_B, hash_A)
    
    # Generate C using B's hash
    hash_C = generate_audit_hash("EVENT_C", event_C, hash_B)

    # Prove Tamper Evident
    # If someone tampers with Event B in the database
    tampered_event_B = {"confidence": 0.99}
    tampered_hash_B = generate_audit_hash("EVENT_B", tampered_event_B, hash_A)
    
    assert tampered_hash_B != hash_B
    
    # Recomputing C with the tampered B hash breaks the chain
    tampered_hash_C = generate_audit_hash("EVENT_C", event_C, tampered_hash_B)
    assert tampered_hash_C != hash_C
