import os
import json
import hashlib
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

AUDIT_LOG_FILE = os.getenv("AUDIT_LOG_FILE", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data", "audit_trail.jsonl"))

class CryptographicAuditLogger:
    """
    Cryptographic Append-Only Audit Logger:
    Implements SHA-256 Hash Chaining (H_i = SHA256(H_{i-1} || Action_Payload))
    Guarantees tamper-evident security for all operator actions and anomaly resolutions.
    """
    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self, log_path: str = AUDIT_LOG_FILE):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self.last_hash = self._get_latest_hash()

    def _get_latest_hash(self) -> str:
        if not os.path.exists(self.log_path):
            return self.GENESIS_HASH
            
        last_line = None
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line.strip()
                    
        if last_line:
            try:
                entry = json.loads(last_line)
                return entry.get("current_hash", self.GENESIS_HASH)
            except Exception:
                return self.GENESIS_HASH
        return self.GENESIS_HASH

    def log_event(self, actor: str, action: str, details: Dict[str, Any], event_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a new chained audit entry and appends it to the immutable audit log file.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        prev_hash = self.last_hash
        
        payload = {
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "event_id": event_id,
            "details": details,
            "previous_hash": prev_hash
        }
        
        # Canonical JSON string for deterministic hashing
        canonical_str = json.dumps(payload, sort_keys=True)
        current_hash = hashlib.sha256(f"{prev_hash}:{canonical_str}".encode("utf-8")).hexdigest()
        
        entry = {
            **payload,
            "current_hash": current_hash
        }
        
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            
        self.last_hash = current_hash
        return entry

    def verify_integrity(self) -> Dict[str, Any]:
        """
        Verifies the cryptographic chain integrity of the entire audit log from Genesis.
        """
        if not os.path.exists(self.log_path):
            return {"status": "VALID", "total_records": 0, "message": "Audit log is empty."}
            
        expected_prev = self.GENESIS_HASH
        count = 0
        
        with open(self.log_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    prev_h = entry.get("previous_hash")
                    curr_h = entry.get("current_hash")
                    
                    if prev_h != expected_prev:
                        return {
                            "status": "CORRUPTED",
                            "corrupted_line": i,
                            "reason": f"Hash chain broken at record #{i}. Expected prev: {expected_prev}, found: {prev_h}"
                        }
                        
                    # Recompute hash
                    payload = {
                        "timestamp": entry["timestamp"],
                        "actor": entry["actor"],
                        "action": entry["action"],
                        "event_id": entry.get("event_id"),
                        "details": entry["details"],
                        "previous_hash": prev_h
                    }
                    canonical = json.dumps(payload, sort_keys=True)
                    recomputed = hashlib.sha256(f"{prev_h}:{canonical}".encode("utf-8")).hexdigest()
                    
                    if recomputed != curr_h:
                        return {
                            "status": "CORRUPTED",
                            "corrupted_line": i,
                            "reason": f"Payload signature mismatch at record #{i}. Data was modified!"
                        }
                        
                    expected_prev = curr_h
                    count += 1
                except Exception as e:
                    return {"status": "ERROR", "corrupted_line": i, "reason": str(e)}
                    
        return {
            "status": "VERIFIED_VALID",
            "total_records": count,
            "latest_hash": expected_prev,
            "message": "Cryptographic hash chain is 100% intact and verified."
        }

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the most recent N audit log records"""
        if not os.path.exists(self.log_path):
            return []
            
        logs = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        logs.append(json.loads(line))
                    except Exception:
                        pass
        return list(reversed(logs[-limit:]))

# Global Singleton Audit Logger
audit_logger = CryptographicAuditLogger()
