import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from .api import MempoolAPI

class UTXOGraph:
    def __init__(self, max_depth=10, sleep_time=0.2):
        self.api = MempoolAPI(sleep_time=sleep_time)
        self.graph = nx.DiGraph()
        self.visited = set()
        self.depths = {}
        self.max_depth = max_depth

    def trace_utxo(self, txid, vout, depth=0):
        if depth > self.max_depth or (txid, vout) in self.visited:
            return

        self.visited.add((txid, vout))

        script_type = self.api.get_scripttype(txid, vout)
        current_utxo = f"{txid[:8]}... ({script_type})"
        self.depths[current_utxo] = depth

        spending_info = self.api.get_spending_transactions(txid)
        if not spending_info:
            print(f"[INFO] UTXO {txid}:{vout} is not spent or unavailable.")
            return

        seen_txids = set()
        for vout_index, spending_txid in spending_info.items():
            if spending_txid is None or spending_txid in seen_txids:
                continue
            seen_txids.add(spending_txid)

            outputs = self.api.get_outputs(spending_txid)
            for new_vout, value in outputs:
                new_type = self.api.get_scripttype(spending_txid, new_vout)
                new_utxo = f"{spending_txid[:8]}... ({new_type})"
                edge_label = f"{value / 1e8:.8f} BTC"

                self.graph.add_edge(current_utxo, new_utxo, value=edge_label)
                self.depths[new_utxo] = depth + 1
                self.trace_utxo(spending_txid, new_vout, depth + 1)

    def visualize(self):
        if not self.graph.nodes:
            print("[INFO] Nothing to visualize.")
            return

        plt.figure(figsize=(16, 12))
        try:
            pos = nx.nx_pydot.graphviz_layout(self.graph, prog='dot')
        except:
            pos = nx.spring_layout(self.graph, k=0.5)

        edge_labels = nx.get_edge_attributes(self.graph, 'value')
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels, font_size=8)

        max_depth = max(self.depths.values(), default=1)
        colors = [self.depths.get(n, 0) / max_depth for n in self.graph.nodes]
        cmap = cm.get_cmap('plasma')
        node_colors = [cmap(c) for c in colors]

        nx.draw(self.graph, pos, with_labels=True, node_color=node_colors,
                node_size=220, font_size=9, font_weight='bold', edge_color='gray',
                arrows=True, arrowstyle='-|>', arrowsize=16)

        plt.title(f"UTXO Spending Graph (Max Depth = {self.max_depth})")
        plt.tight_layout()
        plt.axis("off")
        plt.show()
