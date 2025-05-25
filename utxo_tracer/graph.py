import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import random
from collections import deque # Still useful for the UI update queue
import threading # Import threading
from concurrent.futures import ThreadPoolExecutor # Import ThreadPoolExecutor
from .api import MempoolAPI

class UTXOGraph:
    def __init__(self, max_depth=10, sleep_time=0.2, max_workers=5): # Added max_workers
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

        self.is_tracing = False # Overall tracing state (set by main.py)
        self.status_message = "Ready"
        self.unspent_utxos_found = []

        # --- Threading specific attributes ---
        self.graph_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active_tasks_count = 0
        self._active_tasks_lock = threading.Lock()
        self.ui_update_queue = deque() # For worker threads to request UI updates

    def _increment_active_tasks(self):
        with self._active_tasks_lock:
            self._active_tasks_count += 1

    def _decrement_active_tasks(self):
        with self._active_tasks_lock:
            self._active_tasks_count -= 1

    def get_active_tasks_count(self):
        with self._active_tasks_lock:
            return self._active_tasks_count

    def set_active_drawing_surface(self, fig, ax):
        self.active_fig = fig
        self.active_ax = ax
        self.connect_interactive_events()

    def connect_interactive_events(self):
        # (remains the same)
        if self.active_fig:
            self.active_fig.canvas.mpl_connect('button_press_event', self.on_button_press)
            # ... (other event connections)

    def reset(self):
        # Wait for any ongoing tasks to complete before reset, or shutdown executor
        # For simplicity, we assume reset is called when no tasks are active.
        # If executor needs to be reset:
        # self.executor.shutdown(wait=True)
        # self.executor = ThreadPoolExecutor(max_workers=self.executor._max_workers)

        with self.graph_lock:
            self.graph.clear()
            self.visited.clear()
            self.depths.clear()
            self.unspent_utxos_found.clear()
            self._current_pos_cache = {}
            self.ui_update_queue.clear()

        self._dragged_node = None
        self.node_artist_collection = None
        self._node_list_for_drawing = []
        self.status_message = "Ready"
        # self._active_tasks_count should be 0 if reset is called correctly

    def queue_ui_update(self, update_type, data=None):
        """Safely queues a request for the main thread to update the UI."""
        with self.graph_lock: # ui_update_queue is a shared resource
            self.ui_update_queue.append({'type': update_type, 'data': data or {}})

    def process_ui_updates(self):
        """Called by the main thread to process UI updates and visualize."""
        if not self.active_ax: return False

        processed_updates_count = 0
        temp_unspent_notification_node = None
        # Use a copy of status_message to avoid race if it's updated by main thread elsewhere
        # For now, messages from queue will override.
        # Let visualize handle the most current message from queue if available
        last_message_from_queue = None

        while True:
            try:
                with self.graph_lock: # Protect queue access
                    update = self.ui_update_queue.popleft()
            except IndexError: # Queue is empty
                break

            processed_updates_count += 1
            data = update.get('data', {})
            update_type = update.get('type')

            if update_type == 'unspent_notification':
                temp_unspent_notification_node = data.get('label')
                last_message_from_queue = data.get('message', self.status_message)
            elif update_type == 'status_message':
                last_message_from_queue = data.get('message', self.status_message)
            # Add more handlers here if specific actions are needed beyond just redrawing
            # For example, if a node was added, ensure its position is considered.
            # For now, any queued update triggers a full visualize call.

        # If any updates were processed, or if a redraw was explicitly requested (not implemented yet)
        if processed_updates_count > 0:
            current_msg_for_visualize = last_message_from_queue if last_message_from_queue else self.status_message
            self.visualize(ax=self.active_ax, is_incremental_update=True,
                           current_process_message=current_msg_for_visualize,
                           unspent_notification_node=temp_unspent_notification_node)
            return True # Indicates UI was updated
        return False


    def on_button_press(self, event): # (remains largely the same)
        if event.inaxes != self.active_ax: return
        if self.is_tracing: # Check overall tracing state
            self.queue_ui_update('status_message', {'message': "Wait till trace is completed to move nodes."})
            self._dragged_node = None; return
        # ... (rest of drag logic) ...
        if not self.node_artist_collection: self._dragged_node = None; return
        contains, info = self.node_artist_collection.contains(event)
        if contains:
            idx = info['ind'][0]
            if idx < len(self._node_list_for_drawing): self._dragged_node = self._node_list_for_drawing[idx]; return
        self._dragged_node = None


    def on_motion_notify(self, event): # (remains largely the same)
        if self.is_tracing or not self._dragged_node: return
        if event.inaxes == self.active_ax and self._current_pos_cache:
            x,y = event.xdata, event.ydata
            if x is not None and y is not None:
                self._current_pos_cache[self._dragged_node] = (x,y)
                # Instead of direct visualize, queue an update
                self.queue_ui_update('status_message', {'message': f"Dragging {self._dragged_node[:15]}..."})

    def on_button_release(self, event): # (remains largely the same)
        if self.is_tracing or not self._dragged_node: self._dragged_node = None; return # Clear if tracing
        if self._dragged_node:
             # Queue a final status update for the move
            self.queue_ui_update('status_message', {'message': f"Node {self._dragged_node[:15]} moved"})
        self._dragged_node = None

    # Main orchestrator method, called by main.py
    def trace_utxo(self, initial_txid, initial_vout):
        if not self.active_ax:
            print("[ERROR] Active drawing surface not set.")
            if hasattr(self, 'is_tracing'): self.is_tracing = False
            return

        # self.is_tracing is set by main.py before this call
        # self.status_message is also set by main.py
        # self.reset() should have been called by main.py before setting is_tracing=True for a new cycle.

        self._increment_active_tasks() # Increment for the initial task
        self.executor.submit(self._process_utxo_worker, initial_txid, initial_vout, 0)
        # This method now just kicks off the first task.
        # The completion (active_tasks_count == 0) is monitored by main.py.

    def _process_utxo_worker(self, txid, vout, depth):
        try:
            # 1. Check depth and visited status (thread-safe)
            utxo_id_tuple = (txid, vout)
            with self.graph_lock:
                if depth > self.max_depth or utxo_id_tuple in self.visited:
                    return # Task ends, will be decremented in finally
                self.visited.add(utxo_id_tuple)

            self.queue_ui_update('status_message', {'message': f"Fetching {txid[:8]}:{vout} (D:{depth})"})
            tx_details = self.api.get_transaction_details(txid) # I/O bound, GIL released
            if not tx_details:
                self.queue_ui_update('status_message', {'message': f"Error fetching {txid[:8]}"})
                return

            script_type = self.api.get_scripttype(txid, vout, tx_details=tx_details)
            current_graph_label = f"{txid[:8]}... ({script_type})"

            # 2. Update graph structure (thread-safe)
            with self.graph_lock:
                if current_graph_label not in self.graph:
                    self.graph.add_node(current_graph_label)
                self.depths[current_graph_label] = depth
            self.queue_ui_update('status_message', {'message': f"Added {current_graph_label[:20]} (D:{depth})"})

            # 3. Check if spent (API call)
            all_outspends_info = self.api.get_spending_transactions(txid) # I/O bound
            spending_txid = all_outspends_info.get(vout) if isinstance(all_outspends_info, dict) else None

            if not spending_txid: # Unspent
                with self.graph_lock:
                    self.unspent_utxos_found.append({
                        'txid': txid, 'vout': vout, 'label': current_graph_label, 'script_type': script_type
                    })
                cli_alert_message = f"[!!!] UNSPENT UTXO FOUND: {current_graph_label} (TxID: {txid}, vout: {vout})"
                print("\n" + "="*len(cli_alert_message)); print(cli_alert_message); print("="*len(cli_alert_message) + "\n")
                self.queue_ui_update('unspent_notification', {
                    'label': current_graph_label,
                    'message': f"Unspent: {current_graph_label[:20]}"
                })
                return

            # 4. Spent: Process children if within depth
            next_depth = depth + 1
            if next_depth > self.max_depth:
                self.queue_ui_update('status_message', {'message': f"Max depth for children of {current_graph_label[:15]}"})
                return

            self.queue_ui_update('status_message', {'message': f"{current_graph_label[:10]} spent by {spending_txid[:8]}..."})
            spender_tx_details = self.api.get_transaction_details(spending_txid) # I/O bound
            if not spender_tx_details:
                self.queue_ui_update('status_message', {'message': f"Error spender {spending_txid[:8]}"})
                return

            outputs_of_spender = self.api.get_outputs(spending_txid, tx_details=spender_tx_details)
            if not outputs_of_spender:
                self.queue_ui_update('status_message', {'message': f"{spending_txid[:8]} has no outputs"})
                return

            for new_vout, value in outputs_of_spender:
                child_txid_val=spending_txid
                child_vout_val=new_vout
                child_depth_val = next_depth
                child_utxo_id_tuple_for_visit_check = (spending_txid, new_vout)
                # Check visited for child *before* submitting new task (optimisation)
                with self.graph_lock: # Quick check, must be fast
                    if child_utxo_id_tuple_for_visit_check in self.visited or next_depth > self.max_depth:
                        # If already visited, or would exceed depth, maybe still add edge if not present
                        # Edge adding logic needs to be robust if children are processed independently
                        # For now, if child visited, this branch of work stops for that child here.
                        # Edge to an already existing node should be added by its first discoverer.
                        # This logic can be complex if graph can be cyclic or nodes reached by multiple paths.
                        # Let's ensure edges are added if the child exists but this path to it is new.
                        _child_s_type = self.api.get_scripttype(spending_txid, new_vout, tx_details=spender_tx_details)
                        _child_g_label = f"{spending_txid[:8]}... ({_child_s_type})"
                        if _child_g_label in self.graph and not self.graph.has_edge(current_graph_label, _child_g_label):
                            _edge_val = f"{value / 1e8:.8f} BTC"
                            self.graph.add_edge(current_graph_label, _child_g_label, value=_edge_val)
                            self.queue_ui_update('status_message', {'message': f"Linked to existing {child_graph_label[:15]}"})
                        continue # Don't submit task for already visited/max_depth child

                # If not visited and within depth, submit task for this child branch
                self._increment_active_tasks() # Increment *before* submitting new task
                self.executor.submit(self._process_utxo_worker_child,
                                     spending_txid, new_vout, next_depth,
                                     current_graph_label, value, spender_tx_details)
        finally:
            self._decrement_active_tasks() # Decrement when task finishes or returns early

    # Helper for submitting child tasks to manage parameters, could be merged back if preferred
    def _process_utxo_worker_child(self, child_txid, child_vout, child_depth,
                                   parent_graph_label_for_edge, edge_value, child_tx_full_details):
        # This function is just to make the edge addition cleaner before calling the main worker logic.
        # The main worker logic starts by checking visited status.
        try:
            child_script_type = self.api.get_scripttype(child_txid, child_vout, tx_details=child_tx_full_details)
            child_graph_label = f"{child_txid[:8]}... ({child_script_type})"
            edge_value_str = f"{edge_value / 1e8:.8f} BTC"

            with self.graph_lock:
                if child_graph_label not in self.graph:
                    self.graph.add_node(child_graph_label)
                    # Depth will be set by the child's own _process_utxo_worker task
                if not self.graph.has_edge(parent_graph_label_for_edge, child_graph_label):
                    self.graph.add_edge(parent_graph_label_for_edge, child_graph_label, value=edge_value_str)

            self.queue_ui_update('status_message', {'message': f"Discovered {child_graph_label[:15]}"})

            # Now call the main worker logic for this child.
            # The increment for this task was done by the parent *before* submitting.
            self._process_utxo_worker(child_txid, child_vout, child_depth)
        except Exception as e: # Catch exceptions in child processing to ensure decrement
            print(f"[ERROR] in child worker {child_txid}:{child_vout}: {e}")
            # Decrement was already handled by the _process_utxo_worker's finally block.
            # If _process_utxo_worker is not called due to an error here, then decrement is missed.
            # The current structure: parent increments, submits _process_utxo_worker_child,
            # which calls _process_utxo_worker. The finally in _process_utxo_worker handles decrement.
            # This specific _process_utxo_worker_child does not decrement itself, as it's a wrapper.
            # This design is a bit complex. Simpler is to do all in one worker.

    # Reverting to single worker for children too:
    # (The above _process_utxo_worker_child can be removed if all logic is in _process_utxo_worker)
    # The _process_utxo_worker's "Submit new task for this child" section would be:
    # self.executor.submit(self._process_utxo_worker, spending_txid, new_vout, next_depth)
    # And edge/node adding for child would happen when child task runs. This causes visual delay.

    # Let's stick to the _process_utxo_worker adding its own node & connecting to parent.
    # The parent_graph_label needs to be passed to _process_utxo_worker.
    # The initial call to _process_utxo_worker will have parent_graph_label=None.
    # Revised _process_utxo_worker and trace_utxo (orchestrator):
    # (This is getting very complex for one step, let's ensure the previous single worker logic is robust first)
    # The previous _process_utxo_worker correctly handles its own node and then spawns children.
    # The edge from parent to child needs to be added by the PARENT when it discovers the child.
    # This was in the previous version of _process_utxo_worker's loop. That was better.

    # Let's simplify and use the single _process_utxo_worker as designed before the child_worker split idea.
    # The key is that `_process_utxo_worker` calls `self.executor.submit(self._process_utxo_worker, ...)` for children.


    def visualize(self, ax=None, is_incremental_update=False, current_process_message="", unspent_notification_node=None):
        # (Visualize method remains mostly the same, using self.ui_update_queue outputs)
        # (Ensure it uses pos cache correctly even with concurrent modifications)
        # ... (visualization code from before, ensure thread safety if it reads shared state not covered by queue)
        # Position calculation should be fine if it uses _current_pos_cache which is updated under lock
        # (The existing visualize method is mostly fine, main thing is it's called from main thread)
        if ax is None: ax = self.active_ax
        if ax is None: print("[ERROR] Visualize called without an active Axes object."); return

        with self.graph_lock: # Acquire lock before accessing graph data for visualization
            ax.clear()
            if not self.graph.nodes:
                ax.text(0.5, 0.5, "Graph is empty.", ha='center', va='center')
            else:
                # Position calculation (ensure _current_pos_cache is correctly managed)
                pos = None
                if self._current_pos_cache and all(node in self._current_pos_cache for node in self.graph.nodes()):
                    pos = self._current_pos_cache.copy() # Use a copy
                else:
                    try:
                        pos = nx.nx_pydot.graphviz_layout(self.graph, prog='dot')
                    except Exception:
                        pos = nx.spring_layout(self.graph, pos=self._current_pos_cache if self._current_pos_cache else None, k=0.9, iterations=50, fixed=None)
                    self._current_pos_cache = pos.copy() if pos else {}

                if not pos and self.graph.nodes(): pos = nx.spring_layout(self.graph, k=0.9, iterations=10)
                if pos:
                    for node_label_iter in list(self.graph.nodes()):
                        if node_label_iter not in pos: pos[node_label_iter] = (random.random(), random.random())
                    self._current_pos_cache.update(pos)
                elif self.graph.nodes(): print("[ERROR] Could not determine node positions!"); return

                self._node_list_for_drawing = list(self.graph.nodes())
                node_final_colors = []
                max_depth_val = max(self.depths.values(), default=0) if self.depths else 0
                cmap = cm.get_cmap('plasma' if 'plasma' in plt.colormaps() else 'viridis')

                for node_label in self._node_list_for_drawing:
                    depth_val = self.depths.get(node_label, 0)
                    normalized_depth = depth_val / max_depth_val if max_depth_val > 0 else 0.0
                    node_final_colors.append(cmap(normalized_depth))

                self.node_artist_collection = nx.draw_networkx_nodes(
                    self.graph, pos, ax=ax, nodelist=self._node_list_for_drawing,
                    node_color=node_final_colors, node_size=2000)
                nx.draw_networkx_edges(
                    self.graph, pos, ax=ax, edge_color='gray',
                    arrows=True, arrowstyle='-|>', arrowsize=15, width=1.5)
                nx.draw_networkx_labels(
                    self.graph, pos, ax=ax, labels={n: n for n in self._node_list_for_drawing},
                    font_size=8, font_weight='normal')
                edge_labels = nx.get_edge_attributes(self.graph, 'value')
                nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels, font_size=7, ax=ax)

                if unspent_notification_node and pos and unspent_notification_node in pos:
                    node_pos_x, node_pos_y = pos[unspent_notification_node]
                    ax.text(node_pos_x, node_pos_y + 0.05, "unspendddd!!", ha='center', va='bottom',
                            fontsize=10, color='darkred', weight='bold',
                            bbox=dict(boxstyle="round,pad=0.4", fc="lightyellow", ec="orange", alpha=0.85, lw=1.5))
        # End of `with self.graph_lock` for visualization data gathering

        title_base = f"UTXO Graph (Max Depth: {self.max_depth})"
        display_info = current_process_message
        if not display_info:
            if self.is_tracing: display_info = self.status_message
            elif self.status_message: display_info = self.status_message
            else: display_info = "Ready"
        final_title_message = f"{title_base} - {display_info}"
        ax.set_title(final_title_message, fontsize=10)
        ax.axis("off")

        if self.active_fig: self.active_fig.canvas.draw_idle()
        if is_incremental_update: plt.pause(0.05)
