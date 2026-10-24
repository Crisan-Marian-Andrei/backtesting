# Pro Quant Terminal 📈 

A high-performance algorithmic trading backtester and optimizer that combines the speed of **C** for heavy computations with the flexibility of **Python** and **PyQt6** for the graphical user interface.

## 🚀 Overview

**Pro Quant Terminal** is a hybrid desktop application designed to test and optimize Simple Moving Average (SMA) crossover strategies. By offloading the iterative backtesting and optimization loops to a pre-compiled C library via `ctypes`, the application achieves execution speeds significantly faster than pure Python implementations.

## ✨ Key Features

* **Hybrid Architecture:** Python handles the GUI, data fetching, and visualization, while a C backend (`libengine`) processes millions of calculations in milliseconds.
* **Smart Data Caching:** Automatically downloads historical data via `yfinance` and caches it locally in a `SQLite3` database to prevent redundant API calls.
* **Asynchronous Execution:** Uses `QThread` to ensure the UI remains fully responsive during heavy optimization tasks.
* **Interactive Visualizations:** Built with `pyqtgraph` for hardware-accelerated, interactive Candlestick charts, SMA overlays, and RSI indicators.
* **Strategy Optimizer:** Brute-forces optimal SMA short/long combinations based on historical data.
* **PDF Reporting:** Automatically generates and exports financial backtest reports.

## 🛠️ Tech Stack

* **Frontend:** PyQt6, pyqtgraph
* **Backend:** C (compiled as a shared library)
* **Data Processing:** Pandas, yfinance, SQLite3
* **Integration:** ctypes

## ⚙️ Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/Crisan-Marian-Andrei/backtesting.git
cd backtesting
```

### 2. Compile the C Engine
You need to compile the C logic into a shared library (`.so` for Linux/macOS or `.dll` for Windows). 

**Linux / macOS:**
```bash
gcc -shared -o libengine.so -fPIC engine.c -O3
```

**Windows (using MinGW or MSVC):**
```bash
gcc -shared -o libengine.dll engine.c -O3
```
*(Note: If using Windows, you may need to adjust the `ctypes.CDLL('./libengine.so')` path in the Python script to `.dll`)*

### 3. Install Python Dependencies
It is recommended to use a virtual environment.
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

*(If you don't have a `requirements.txt`, install manually: `pip install PyQt6 pyqtgraph pandas yfinance`)*

### 4. Run the Application
```bash
python main.py
```

## 📊 Usage Guide

1. **Enter Ticker:** Input a valid Yahoo Finance ticker (e.g., `AAPL`, `TSLA`, `SPY`).
2. **Set Parameters:** Adjust the trading fee (%), Short SMA, and Long SMA.
3. **Run Backtest:** Click **RUN** to simulate the strategy on historical data. The results (Win Rate, Max Drawdown, PnL) will update instantly.
4. **Optimize:** Click **Find Strategy** to let the C engine calculate the most profitable SMA combination for the selected asset.
5. **Export:** Save the results as a PDF report.

## 📁 Project Structure

```text
├── main.py              # Main application (PyQt6 UI & Python logic)
├── engine.c             # High-performance C backend for backtesting
├── market_data.db       # SQLite database for cached price data (generated on run)
├── requirements.txt     # Python dependencies
└── README.md            # This documentation
```
