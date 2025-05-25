from utxo_tracer.graph import UTXOGraph
import time
import matplotlib.pyplot as plt

def main():
    txid = "9996f5ad442be27bdc8c05ba32c0837185a36626fd8bc1c9cd0a4a2576277ec2"
    vout = 0
    max_graph_depth = 10
    refresh_interval_seconds = 120 # Increased for less frequent full resets if dragging

    graph_manager = UTXOGraph(max_depth=max_graph_depth)

    plt.ion()
    fig, ax = plt.subplots(figsize=(17, 13))
    # Pass the fig and ax to the graph manager to enable interactivity
    graph_manager.set_active_drawing_surface(fig, ax)

    try:
        while True:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting/Refreshing trace for UTXO {txid}:{vout}...")

            # Reset clears graph data. If you want dragged positions to persist across
            # full refreshes, the _current_pos_cache clearing in reset() needs adjustment.
            # For now, positions reset on full refresh.
            graph_manager.reset()

            ax.clear()
            ax.set_title(f"Preparing to trace {txid[:8]}...:{vout}")
            ax.axis("off")
            fig.canvas.draw_idle()
            plt.pause(0.01) # Brief pause

            graph_manager.trace_utxo(txid, vout)

            final_message = "Trace complete."
            if not graph_manager.graph.nodes:
                final_message = "Trace complete: Graph is empty."

            # Final draw after tracing for this cycle
            graph_manager.visualize(ax=ax, is_incremental_update=False, current_process_message=final_message)
            fig.canvas.draw_idle()

            print(f"Trace cycle complete. Waiting for {refresh_interval_seconds} seconds...")
            if not plt.fignum_exists(fig.number):
                print("Plot window closed. Exiting.")
                break
            # Use a loop with shorter sleeps to keep UI responsive if plt.sleep blocks events
            for _ in range(refresh_interval_seconds):
                if not plt.fignum_exists(fig.number): break
                plt.pause(1) # Pause for 1 second, allows events to process

    except KeyboardInterrupt:
        print("\nStopping real-time updates (Ctrl+C).")
    except Exception as e:
        print(f"An unexpected error occurred in main loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        plt.ioff()
        if plt.fignum_exists(fig.number):
            print("Displaying final graph. Close plot to exit.")
            ax.set_title(f"Final UTXO Graph for {txid[:8]}...:{vout} (Max Depth: {max_graph_depth})")
            fig.canvas.draw_idle()
            plt.show()
        else:
            print("Plot window was closed during execution.")

if __name__ == "__main__":
    main()
