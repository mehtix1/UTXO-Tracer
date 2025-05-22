## Features

- Traces UTXO spending chains up to a configurable depth.
- Visualizes UTXO relationships with color-coded nodes.
- Integrates with the mempool.space public API.

## Installation

```bash

git clone https://github.com/yourusername/utxo-tracer.git
cd utxo-tracer
pip install -r requirements.txt
```
## 🚀 Usage

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/utxo-tracer.git
cd utxo-tracer
pip install -r requirements.txt
```
### 2. Configure Target Transaction
Open main.py and set the transaction ID and output index of the UTXO to trace:

```bash
txid = "your_txid_here"
vout = 0

```
### 3. Run the Tracer
```bash
python main.py
```
