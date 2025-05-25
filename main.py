from utxo_tracer.graph import UTXOGraph
import time
import matplotlib.pyplot as plt

def main():
    txid = "9996f5ad442be27bdc8c05ba32c0837185a36626fd8bc1c9cd0a4a2576277ec2"
    vout = 0
    max_graph_depth = 10
    refresh_interval_seconds = 120
    max_workers_for_graph = 5 # Number of threads for processing branches

    graph_manager = UTXOGraph(max_depth=max_graph_depth, max_workers=max_workers_for_graph)

    plt.ion()
    fig, ax = plt.subplots(figsize=(17, 13))
    graph_manager.set_active_drawing_surface(fig, ax)

    try:
        while True:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting/Refreshing trace for UTXO {txid}:{vout}...")

            graph_manager.reset()

            ax.clear() # Initial clear by main thread
            initial_prep_message = f"Preparing to trace {txid[:8]}...:{vout}"
            ax.set_title(initial_prep_message)
            ax.axis("off")
            fig.canvas.draw_idle()
            plt.pause(0.01)

            graph_manager.is_tracing = True # Set overall tracing state
            graph_manager.status_message = "Trace in progress (multithreaded)..."
            graph_manager.queue_ui_update('status_message', {'message': graph_manager.status_message})


            graph_manager.trace_utxo(initial_txid=txid, initial_vout=vout) # Kicks off threaded tasks

            # Loop to process UI updates and wait for tasks to complete
            while graph_manager.is_tracing: # is_tracing will be set to False when tasks are done
                updated_ui = graph_manager.process_ui_updates()

                active_tasks = graph_manager.get_active_tasks_count()
                if active_tasks == 0:
                    graph_manager.is_tracing = False # All submitted tasks are done
                    print("All worker tasks seem complete.")
                    # Process any final updates that might have been queued just before tasks ended
                    while graph_manager.process_ui_updates(): plt.pause(0.05)
                    break

                if not updated_ui: # If no UI updates were processed, pause a bit longer
                    plt.pause(0.2) # Check for new UI updates or task completion less frequently
                else:
                    plt.pause(0.05) # Shorter pause if UI was just updated

                if not plt.fignum_exists(fig.number):
                    print("Plot window closed during trace. Attempting to stop.")
                    graph_manager.is_tracing = False # Signal to stop
                    # Consider telling executor to shutdown if this happens
                    # graph_manager.executor.shutdown(wait=False, cancel_futures=True) # Python 3.9+ for cancel_futures
                    break

            # --- Post-trace processing ---
            graph_manager.is_tracing = False # Ensure it's false

            # Display Unspent UTXOs found (remains the same)
            if graph_manager.unspent_utxos_found:
                print("\n--- Unspent UTXOs Found at Trace Limit ---")
                for i, utxo_info in enumerate(graph_manager.unspent_utxos_found):
                    print(f"  {i+1}. Label: {utxo_info['label']}") # ... (rest of print)
                graph_manager.status_message = f"Trace complete. Found {len(graph_manager.unspent_utxos_found)} unspent UTXO(s)."
            else:
                graph_manager.status_message = "Trace complete. No unspent UTXOs at trace limit."
            print(graph_manager.status_message + "\n")

            # Final visualization call
            graph_manager.visualize(ax=ax, is_incremental_update=False, current_process_message=graph_manager.status_message)
            fig.canvas.draw_idle()

            print(f"Refresh cycle complete. Waiting for {refresh_interval_seconds} seconds...")
            if not plt.fignum_exists(fig.number): break
            for i in range(refresh_interval_seconds):
                if not plt.fignum_exists(fig.number): break
                # Keep processing UI events during long wait, though unlikely any will come
                if i % 5 == 0 : graph_manager.process_ui_updates() # Occasionally process if needed
                plt.pause(1)

    except KeyboardInterrupt: # (remains the same)
        print("\nStopping real-time updates (Ctrl+C).")
        if graph_manager: graph_manager.is_tracing = False; graph_manager.executor.shutdown(wait=False) # Python 3.9+ for cancel_futures in executor.shutdown
    except Exception as e: # (remains the same)
        print(f"An unexpected error occurred in main loop: {e}"); import traceback; traceback.print_exc()
        if graph_manager: graph_manager.is_tracing = False; graph_manager.executor.shutdown(wait=False)
    finally: # (remains the same)
        plt.ioff()
        if graph_manager: graph_manager.executor.shutdown(wait=True) # Ensure threads are cleaned up
        if plt.fignum_exists(fig.number): plt.show()

if __name__ == "__main__":
    main()

