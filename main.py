from utxo_tracer.graph import UTXOGraph

def main():
    # Sample transaction and output index
    txid = "9996f5ad442be27bdc8c05ba32c0837185a36626fd8bc1c9cd0a4a2576277ec2"
    vout = 0

    graph = UTXOGraph(max_depth=2)
    graph.trace_utxo(txid, vout)
    graph.visualize()

if __name__ == "__main__":
    main()
