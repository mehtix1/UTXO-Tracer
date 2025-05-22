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
### 4. 💡 Future Improvements (Planned)
# TODO: Future improvements if time allows:
# - Enhance GUI using interactive libraries like Plotly or PyQt for better UX.
# - Add tooltips or hover-info showing full txid, vout, BTC value, timestamp.
# - Real-time graph updates as new data is fetched.
# - Option to export graph as image or JSON for analysis/sharing.
# - Add filters for depth, BTC amount, or script types to customize views.
