import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import random
from collections import deque
from .api import MempoolAPI

class UTXOGraph:
    def __init__(self, max_depth=10, sleep_time=0.2):
        self.api = MempoolAPI(sleep_time=sleep_time)
        self.graph = nx.DiGraph()
        self.visited = set()
        self.depths = {}
        self.max_depth = max_depth

        self.active_fig = None
        self.active_ax = None
        self._current_pos_cache = {}

        self._dragged_node = None
        self.node_artist_collection = None
        self._node_list_for_drawing = []

        self.is_tracing = False
        self.status_message = "Ready"
        # self.unspent_nodes = set() # No longer needed for black coloring

    def set_active_drawing_surface(self, fig, ax):
        self.active_fig = fig
        self.active_ax = ax
        self.connect_interactive_events()

    def connect_interactive_events(self):
        if self.active_fig:
            self.active_fig.canvas.mpl_connect('button_press_event', self.on_button_press)
            self.active_fig.canvas.mpl_connect('motion_notify_event', self.on_motion_notify)
            self.active_fig.canvas.mpl_connect('button_release_event', self.on_button_release)

    def reset(self):
        self.graph.clear()
        self.visited.clear()
        self.depths.clear()
        # self.unspent_nodes.clear() # No longer needed
        self._current_pos_cache = {}
        self._dragged_node = None
        self.node_artist_collection = None
        self._node_list_for_drawing = []
        self.status_message = "Ready"

    def on_button_press(self, event):
        # (This method remains the same)
        if event.inaxes != self.active_ax: return
        if self.is_tracing:
            if self.active_ax:
                self.visualize(ax=self.active_ax, is_incremental_update=True,
                               current_process_message="Wait till trace is completed to move nodes.")
            self._dragged_node = None
            return
        if not self.node_artist_collection:
            self._dragged_node = None
            return
        contains, info = self.node_artist_collection.contains(event)
        if contains:
            idx = info['ind'][0]
            if idx < len(self._node_list_for_drawing):
                self._dragged_node = self._node_list_for_drawing[idx]
                return
        self._dragged_node = None

    def on_motion_notify(self, event):
        # (This method remains the same)
        if self.is_tracing or not self._dragged_node: return
        if event.inaxes == self.active_ax and self._current_pos_cache:
            x, y = event.xdata, event.ydata
            if x is not None and y is not None:
                self._current_pos_cache[self._dragged_node] = (x, y)
                self.visualize(ax=self.active_ax, is_incremental_update=True,
                               current_process_message=f"Dragging {self._dragged_node[:15]}...")

    def on_button_release(self, event):
        # (This method remains the same)
        if self.is_tracing:
             self._dragged_node = None
             return
        if self._dragged_node:
            self.visualize(ax=self.active_ax, is_incremental_update=False,
                           current_process_message=f"Node {self._dragged_node[:15]} moved")
        self._dragged_node = None


    def trace_utxo(self, initial_txid, initial_vout): # BFS implementation
        if not self.active_ax:
            if hasattr(self, 'is_tracing'): self.is_tracing = False
            return

        queue = deque()
        initial_depth = 0

        if initial_depth > self.max_depth: return

        self.visualize(ax=self.active_ax, is_incremental_update=True, current_process_message=f"Init {initial_txid[:8]}:{initial_vout}")
        initial_tx_details = self.api.get_transaction_details(initial_txid)
        if not initial_tx_details:
            self.visualize(ax=self.active_ax, is_incremental_update=True, current_process_message=f"Error initial TX {initial_txid[:8]}")
            return

        initial_script_type = self.api.get_scripttype(initial_txid, initial_vout, tx_details=initial_tx_details)
        initial_utxo_label = f"{initial_txid[:8]}... ({initial_script_type})"
        initial_utxo_id_tuple = (initial_txid, initial_vout)

        if initial_utxo_id_tuple not in self.visited:
            if initial_utxo_label not in self.graph:
                self.graph.add_node(initial_utxo_label)
            self.depths[initial_utxo_label] = initial_depth
            self.visited.add(initial_utxo_id_tuple)
            queue.append({'txid': initial_txid, 'vout': initial_vout, 'depth': initial_depth, 'label': initial_utxo_label})
            self.visualize(ax=self.active_ax, is_incremental_update=True, current_process_message=f"Start: {initial_utxo_label[:20]} (D:{initial_depth})")
        else:
            return

        while queue:
            current_item = queue.popleft()
            txid, vout, depth, current_label = current_item['txid'], current_item['vout'], current_item['depth'], current_item['label']

            self.visualize(ax=self.active_ax, is_incremental_update=True, current_process_message=f"Processing {current_label[:15]} (D:{depth})")

            all_outspends_info = self.api.get_spending_transactions(txid)
            spending_txid = all_outspends_info.get(vout) if isinstance(all_outspends_info, dict) else None

            if not spending_txid:
                # This UTXO is unspent. Trigger notification.
                self.visualize(ax=self.active_ax, is_incremental_update=True,
                               current_process_message=f"Unspent: {current_label[:20]}",
                               unspent_notification_node=current_label) # Pass label for notification
                # self.unspent_nodes.add(current_label) # No longer needed for black color
                continue

            next_depth = depth + 1
            if next_depth > self.max_depth:
                self.visualize(ax=self.active_ax, is_incremental_update=True, current_process_message=f"Max depth for children of {current_label[:15]}")
                continue

            self.visualize(ax=self.active_ax, is_incremental_update=True, current_process_message=f"{current_label[:10]} spent by {spending_txid[:8]}...")
            spender_tx_details = self.api.get_transaction_details(spending_txid)
            if not spender_tx_details:
                self.visualize(ax=self.active_ax, is_incremental_update=True, current_process_message=f"Error spender {spending_txid[:8]}")
                continue

            outputs_of_spender = self.api.get_outputs(spending_txid, tx_details=spender_tx_details)
            if not outputs_of_spender:
                 self.visualize(ax=self.active_ax, is_incremental_update=True, current_process_message=f"{spending_txid[:8]} has no outputs")
                 continue

            for new_vout, value in outputs_of_spender:
                child_utxo_id_tuple = (spending_txid, new_vout)
                child_script_type = self.api.get_scripttype(spending_txid, new_vout, tx_details=spender_tx_details)
                child_label = f"{spending_txid[:8]}... ({child_script_type})"

                if child_label not in self.graph:
                    self.graph.add_node(child_label)

                edge_val_str = f"{value / 1e8:.8f} BTC"
                if not self.graph.has_edge(current_label, child_label):
                    self.graph.add_edge(current_label, child_label, value=edge_val_str)

                if child_utxo_id_tuple not in self.visited:
                    self.visited.add(child_utxo_id_tuple)
                    self.depths[child_label] = next_depth
                    queue.append({'txid': spending_txid, 'vout': new_vout, 'depth': next_depth, 'label': child_label})
                    self.visualize(ax=self.active_ax, is_incremental_update=True, current_process_message=f"Queued {child_label[:15]} (D:{next_depth})")
                else:
                    self.visualize(ax=self.active_ax, is_incremental_update=True, current_process_message=f"Path to {child_label[:15]} (D:{self.depths.get(child_label, '?')})")


    # Add 'unspent_notification_node' parameter to visualize method
    def visualize(self, ax=None, is_incremental_update=False, current_process_message="", unspent_notification_node=None):
        if ax is None: ax = self.active_ax
        if ax is None:
            print("[ERROR] Visualize called without an active Axes object.")
            return

        ax.clear() # This will clear previous "unspendddd!!" notifications too

        if not self.graph.nodes:
            ax.text(0.5, 0.5, "Graph is empty.", ha='center', va='center')
            if self.active_fig: self.active_fig.canvas.draw_idle()
            if is_incremental_update: plt.pause(0.01)
            return

        pos = None
        # (Position calculation logic remains the same)
        if self._current_pos_cache and all(node in self._current_pos_cache for node in self.graph.nodes()):
            pos = self._current_pos_cache
        else:
            try:
                pos = nx.nx_pydot.graphviz_layout(self.graph, prog='dot')
            except Exception:
                pos = nx.spring_layout(self.graph, pos=self._current_pos_cache if self._current_pos_cache else None, k=0.9, iterations=50, fixed=None)
            self._current_pos_cache = pos if pos else {}

        if not pos and self.graph.nodes(): pos = nx.spring_layout(self.graph, k=0.9, iterations=10)
        if pos:
            for node_label_iter in list(self.graph.nodes()): # Use list to avoid issues if graph changes during iteration (unlikely here)
                if node_label_iter not in pos:
                    # Simplified fallback for missing positions
                    pos[node_label_iter] = (random.random(), random.random())
            self._current_pos_cache.update(pos)
        elif self.graph.nodes():
            print("[ERROR] Could not determine node positions!")
            return

        self._node_list_for_drawing = list(self.graph.nodes())

        # Regular Node Coloring (depth-based)
        node_final_colors = []
        max_depth_val = max(self.depths.values(), default=0) if self.depths else 0
        try:
            cmap = cm.get_cmap('plasma')
        except ValueError:
            cmap = cm.get_cmap('viridis')

        for node_label in self._node_list_for_drawing:
            # Black color for unspent is removed, using standard depth coloring for all.
            depth_val = self.depths.get(node_label, 0)
            normalized_depth = depth_val / max_depth_val if max_depth_val > 0 else 0.0
            node_final_colors.append(cmap(normalized_depth))

        # --- Draw graph elements ---
        self.node_artist_collection = nx.draw_networkx_nodes(
            self.graph, pos, ax=ax, nodelist=self._node_list_for_drawing,
            node_color=node_final_colors,
            node_size=2000
        )
        nx.draw_networkx_edges(
            self.graph, pos, ax=ax, edge_color='gray',
            arrows=True, arrowstyle='-|>', arrowsize=15, width=1.5
        )
        nx.draw_networkx_labels(
            self.graph, pos, ax=ax, labels={n: n for n in self._node_list_for_drawing},
            font_size=8, font_weight='normal'
        )
        edge_labels = nx.get_edge_attributes(self.graph, 'value')
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels, font_size=7, ax=ax)

        # --- Draw "unspendddd!!" Notification ---
        if unspent_notification_node and pos and unspent_notification_node in pos:
            node_pos_x, node_pos_y = pos[unspent_notification_node]

            # Determine offset for the notification text to avoid overlapping the node too much
            # This might need adjustment based on your node size and graph scale
            text_offset_y = 0.05 # Adjust this value as needed based on your graph's coordinate system

            ax.text(node_pos_x, node_pos_y + text_offset_y,  # Position text slightly above the node
                    "unspendddd!!",
                    ha='center', va='bottom',  # Horizontal: center, Vertical: bottom of text aligns with y_pos + offset
                    fontsize=10, color='darkred', weight='bold',
                    bbox=dict(boxstyle="round,pad=0.4", fc="lightyellow", ec="orange", alpha=0.85, lw=1.5)
                   )
        # --- End Notification ---

        title_base = f"UTXO Graph (Max Depth: {self.max_depth})"
        display_info = current_process_message
        if not display_info:
            if self.is_tracing: display_info = self.status_message
            elif self.status_message: display_info = self.status_message
            else: display_info = "Ready"
        final_title_message = f"{title_base} - {display_info}"
        ax.set_title(final_title_message, fontsize=10)
        ax.axis("off")

        if self.active_fig:
            self.active_fig.canvas.draw_idle()

        if is_incremental_update:
            # Pause is important for the notification to be visible before being cleared
            plt.pause(0.1) # Adjusted pause for better notification visibility
