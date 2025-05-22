import requests
import time

class MempoolAPI:
    def __init__(self, base_url="https://mempool.space/api", sleep_time=0.2):
        self.base_url = base_url
        self.sleep_time = sleep_time

    def get_spending_transactions(self, txid):
        """Get outspend info for all outputs of a transaction."""
        url = f"{self.base_url}/tx/{txid}/outspends"
        try:
            resp = requests.get(url)
            time.sleep(self.sleep_time)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    idx: out.get("txid") if out.get("spent") else None
                    for idx, out in enumerate(data)
                }
            print(f"[ERROR] Status {resp.status_code} for {url}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch outspends: {e}")
        return {}

    def get_outputs(self, txid):
        """Get list of (vout_index, value) for a transaction."""
        url = f"{self.base_url}/tx/{txid}"
        try:
            resp = requests.get(url)
            time.sleep(self.sleep_time)
            if resp.status_code == 200:
                data = resp.json()
                return [(i, out.get("value", 0)) for i, out in enumerate(data.get("vout", []))]
        except Exception as e:
            print(f"[ERROR] Failed to fetch outputs: {e}")
        return []

    def get_scripttype(self, txid, vout_index):
        """Get the scriptPubKey type of a specific output."""
        url = f"{self.base_url}/tx/{txid}"
        try:
            resp = requests.get(url)
            time.sleep(self.sleep_time)
            if resp.status_code == 200:
                vouts = resp.json().get("vout", [])
                if 0 <= vout_index < len(vouts):
                    return vouts[vout_index].get("scriptpubkey_type", "unknown")
                print(f"[WARN] Invalid vout {vout_index} for tx {txid}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch scripttype: {e}")
        return "unknown"
