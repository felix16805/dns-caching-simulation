"""JSON message format over UDP.
Not wire-compatible with real DNS (RFC 1035); simplified for transparency."""
import json


def encode_query(txid, qname, qtype="A"):
    return json.dumps({"txid": txid, "qname": qname, "qtype": qtype}).encode()


def decode_query(data):
    return json.loads(data.decode())


def encode_response(txid, qname, answer, ttl, rcode):
    return json.dumps({
        "txid": txid, "qname": qname,
        "answer": answer, "ttl": ttl, "rcode": rcode,
    }).encode()


def decode_response(data):
    return json.loads(data.decode())