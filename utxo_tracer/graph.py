import requests
import time

class MempoolAPI:
    def __init__(self, base_url="https://mempool.space/api", sleep_time=0.2):
        self.base_url = base_url
        self.sleep_time = sleep_time

    def get_transaction_details(self, txid):
        """Get full transaction details."""
        url = f"{self.base_url}/tx/{txid}"
        try:
            resp = requests.get(url)
            # Apply sleep after the request, regardless of success or failure, to rate limit
            time.sleep(self.sleep_time)
            if resp.status_code == 200:
                return resp.json()
            print(f"[ERROR] Status {resp.status_code} for {url} while fetching transaction details.")
        except Exception as e:
            print(f"[ERROR] Failed to fetch transaction details for {txid}: {e}")
        return None

    def get_spending_transactions(self, txid):
        """Get outspend info for all outputs of a transaction."""
        url = f"{self.base_url}/tx/{txid}/outspends"
        try:
            resp = requests.get(url)
            time.sleep(self.sleep_time) # Original sleep call
            if resp.status_code == 200:
                data = resp.json()
                return {
                    idx: out.get("txid") if out.get("spent") else None
                    for idx, out in enumerate(data)
                }
            print(f"[ERROR] Status {resp.status_code} for {url} while fetching outspends.")
        except Exception as e:
            print(f"[ERROR] Failed to fetch outspends for {txid}: {e}")
        return {}

    def get_outputs(self, txid, tx_details=None):
        """Get list of (vout_index, value) for a transaction.
        Optionally uses pre-fetched tx_details."""
        if tx_details is None:
            tx_details = self.get_transaction_details(txid)

        if tx_details:
            return [(i, out.get("value", 0)) for i, out in enumerate(tx_details.get("vout", []))]
        return []

    def get_scripttype(self, txid, vout_index, tx_details=None):
        """Get the scriptPubKey type of a specific output.
        Optionally uses pre-fetched tx_details."""
        if tx_details is None:
            tx_details = self.get_transaction_details(txid)

        if tx_details:
            vouts = tx_details.get("vout", [])
            if 0 <= vout_index < len(vouts):
                return vouts[vout_index].get("scriptpubkey_type", "unknown")
            print(f"[WARN] Invalid vout index {vout_index} for tx {txid} (total vouts: {len(vouts)})")
        return "unknown"
