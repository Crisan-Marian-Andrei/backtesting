import sys
import ctypes
import sqlite3
import yfinance as yf
import pandas as pd
import pyqtgraph as pg
from PyQt6 import QtGui, QtCore
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QFormLayout,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPdfWriter, QTextDocument


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.picture = QtGui.QPicture()
        self.generatePicture()

    def generatePicture(self):
        p = QtGui.QPainter(self.picture)
        p.setPen(pg.mkPen("black"))
        w = 0.3
        for t, open_p, close_p, low_p, high_p in self.data:
            p.drawLine(QtCore.QPointF(t, low_p), QtCore.QPointF(t, high_p))
            bottom = min(open_p, close_p)
            height = abs(open_p - close_p)
            if open_p > close_p:
                p.setBrush(pg.mkBrush("r"))
            else:
                p.setBrush(pg.mkBrush("g"))
            p.drawRect(QtCore.QRectF(t - w, bottom, w * 2, height))
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())


class PriceData(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_longlong),
        ("open", ctypes.c_double),
        ("high", ctypes.c_double),
        ("low", ctypes.c_double),
        ("close", ctypes.c_double),
        ("volume", ctypes.c_double),
    ]


class BacktestResult(ctypes.Structure):
    _fields_ = [
        ("total_pnl", ctypes.c_double),
        ("win_rate", ctypes.c_double),
        ("max_drawdown", ctypes.c_double),
        ("total_trades", ctypes.c_int),
        ("winning_trades", ctypes.c_int),
    ]


class OptimizerResult(ctypes.Structure):
    _fields_ = [
        ("best_pnl", ctypes.c_double),
        ("best_win_rate", ctypes.c_double),
        ("best_max_drawdown", ctypes.c_double),
        ("best_short", ctypes.c_int),
        ("best_long", ctypes.c_int),
        ("best_trades", ctypes.c_int),
    ]


engine = ctypes.CDLL("./libengine.so")
engine.run_sma_crossover.argtypes = [
    ctypes.POINTER(PriceData),
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_double,
    ctypes.POINTER(ctypes.c_int),
]
engine.run_sma_crossover.restype = BacktestResult

engine.optimize_strategy.argtypes = [
    ctypes.POINTER(PriceData),
    ctypes.c_int,
    ctypes.c_double,
]
engine.optimize_strategy.restype = OptimizerResult


class SimulationWorker(QThread):
    finished_sim = pyqtSignal(object, object, object)
    finished_opt = pyqtSignal(dict)
    status_update = pyqtSignal(str)

    def __init__(self, ticker, sma_s, sma_l, commission, last_ticker, mode="run"):
        super().__init__()
        self.ticker = ticker
        self.sma_s = sma_s
        self.sma_l = sma_l
        self.commission = commission
        self.last_ticker = last_ticker
        self.mode = mode

    def run(self):
        conn = sqlite3.connect("market_data.db")
        if self.ticker != self.last_ticker:
            self.status_update.emit(f"Downloading API for {self.ticker}...")
            actiune = yf.Ticker(self.ticker)
            df = actiune.history(start="2020-01-01", end="2026-10-01")
            if df.empty:
                self.status_update.emit("Symbol error!")
                return
            df.reset_index(inplace=True)
            df["Date"] = df["Date"].dt.tz_localize(None)
            df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
            df.to_sql(self.ticker, conn, if_exists="replace", index=False)
        else:
            self.status_update.emit(f"Using cache for {self.ticker}")

        df = pd.read_sql(f"SELECT * FROM {self.ticker} ORDER BY Date ASC", conn)
        conn.close()

        num_zile = len(df)
        date_financiare = (PriceData * num_zile)()
        semnale_arr = (ctypes.c_int * num_zile)()

        for i in range(num_zile):
            date_financiare[i].timestamp = i
            date_financiare[i].open = float(df["Open"].iloc[i])
            date_financiare[i].high = float(df["High"].iloc[i])
            date_financiare[i].low = float(df["Low"].iloc[i])
            date_financiare[i].close = float(df["Close"].iloc[i])
            date_financiare[i].volume = float(df["Volume"].iloc[i])

        if self.mode == "run":
            self.status_update.emit("Calculating....")
            rezultat = engine.run_sma_crossover(
                date_financiare,
                num_zile,
                self.sma_s,
                self.sma_l,
                self.commission,
                semnale_arr,
            )
            rez_sigur = {
                "total_trades": rezultat.total_trades,
                "win_rate": rezultat.win_rate,
                "total_pnl": rezultat.total_pnl,
                "max_drawdown": rezultat.max_drawdown,
            }
            self.finished_sim.emit(rez_sigur, df, list(semnale_arr))

        elif self.mode == "optimize":
            self.status_update.emit("Optimizing...")
            opt_rez = engine.optimize_strategy(
                date_financiare, num_zile, self.commission
            )
            opt_dict = {
                "best_short": opt_rez.best_short,
                "best_long": opt_rez.best_long,
                "best_pnl": opt_rez.best_pnl,
            }
            self.finished_opt.emit(opt_dict)


class TradingDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Backtesting")
        self.resize(1200, 800)
        self.last_ticker_loaded = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        control_panel = QWidget()
        control_panel.setFixedWidth(300)
        form_layout = QFormLayout(control_panel)

        self.input_ticker = QLineEdit("AAPL")
        self.spin_short = QSpinBox()
        self.spin_short.setRange(2, 50)
        self.spin_short.setValue(5)
        self.spin_long = QSpinBox()
        self.spin_long.setRange(10, 200)
        self.spin_long.setValue(20)

        self.spin_fee = QDoubleSpinBox()
        self.spin_fee.setRange(0.0, 5.0)
        self.spin_fee.setSingleStep(0.05)
        self.spin_fee.setValue(0.1)
        self.spin_fee.setSuffix(" %")

        self.btn_run = QPushButton("RUN")
        self.btn_run.setStyleSheet(
            "background-color: #2E86C1; color: white; font-weight: bold; padding: 10px;"
        )
        self.btn_run.clicked.connect(self.run_simulation)

        self.btn_opt = QPushButton("Find Strategy")
        self.btn_opt.setStyleSheet(
            "background-color: #D35400; color: white; font-weight: bold; padding: 10px;"
        )
        self.btn_opt.clicked.connect(self.start_optimization)

        self.btn_export = QPushButton("Export Raport (PDF)")
        self.btn_export.setStyleSheet(
            "background-color: #27AE60; color: white; font-weight: bold; padding: 10px;"
        )
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_pdf)

        self.lbl_trades = QLabel("0")
        self.lbl_winrate = QLabel("0.00 %")
        self.lbl_dd = QLabel("0.00 %")
        self.lbl_dd.setStyleSheet("color: red; font-weight: bold;")
        self.lbl_profit = QLabel("0.00 $")
        self.lbl_profit.setStyleSheet("font-size: 16px; font-weight: bold;")

        form_layout.addRow("Simbol:", self.input_ticker)
        form_layout.addRow("Comision/Trade:", self.spin_fee)
        form_layout.addRow("Zile SMA scurt:", self.spin_short)
        form_layout.addRow("Zile SMA lung:", self.spin_long)
        form_layout.addRow("", self.btn_run)
        form_layout.addRow("", self.btn_opt)
        form_layout.addRow("", self.btn_export)
        form_layout.addRow("----------------", QLabel(""))
        form_layout.addRow("Total Tranzactii:", self.lbl_trades)
        form_layout.addRow("Rata de succes:", self.lbl_winrate)
        form_layout.addRow("Risc (Max Drawdown):", self.lbl_dd)
        form_layout.addRow("Profit:", self.lbl_profit)

        main_layout.addWidget(control_panel)

        charts_layout = QVBoxLayout()

        self.plot_widget = pg.PlotWidget(title="Price & Moving Averages")
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()
        charts_layout.addWidget(self.plot_widget)

        self.rsi_plot = pg.PlotWidget(title="Relative Strength Index (RSI)")
        self.rsi_plot.setBackground("w")
        self.rsi_plot.showGrid(x=True, y=True)
        self.rsi_plot.setMaximumHeight(200)
        self.rsi_plot.setXLink(self.plot_widget)
        charts_layout.addWidget(self.rsi_plot)

        main_layout.addLayout(charts_layout)

    def update_btn_text(self, text):
        self.btn_run.setText(text)

    def run_simulation(self):
        self.btn_run.setEnabled(False)
        self.btn_opt.setEnabled(False)
        ticker = self.input_ticker.text().upper()

        self.sim_worker = SimulationWorker(
            ticker,
            self.spin_short.value(),
            self.spin_long.value(),
            self.spin_fee.value(),
            self.last_ticker_loaded,
            mode="run",
        )
        self.sim_worker.status_update.connect(self.update_btn_text)
        self.sim_worker.finished_sim.connect(self.on_simulation_finished)
        self.sim_worker.start()

    def start_optimization(self):
        self.btn_run.setEnabled(False)
        self.btn_opt.setEnabled(False)
        ticker = self.input_ticker.text().upper()

        self.opt_worker = SimulationWorker(
            ticker,
            0,
            0,
            self.spin_fee.value(),
            self.last_ticker_loaded,
            mode="optimize",
        )
        self.opt_worker.status_update.connect(lambda txt: self.btn_opt.setText(txt))
        self.opt_worker.finished_opt.connect(self.on_optimization_finished)
        self.opt_worker.start()

    def on_optimization_finished(self, opt_dict):
        self.btn_opt.setText("Find Strategy")
        self.btn_opt.setEnabled(True)
        self.btn_run.setEnabled(True)

        self.spin_short.setValue(opt_dict["best_short"])
        self.spin_long.setValue(opt_dict["best_long"])
        self.run_simulation()

    def on_simulation_finished(self, rezultat, df, semnale_arr):
        self.last_ticker_loaded = self.input_ticker.text().upper()
        self.btn_run.setText("RUN")
        self.btn_run.setEnabled(True)
        self.btn_opt.setEnabled(True)
        self.btn_export.setEnabled(True)

        self.lbl_trades.setText(str(rezultat["total_trades"]))
        self.lbl_winrate.setText(f"{rezultat['win_rate']:.2f} %")
        self.lbl_dd.setText(f"{rezultat['max_drawdown']:.2f} %")

        if rezultat["total_pnl"] > 0:
            self.lbl_profit.setStyleSheet(
                "color: green; font-size: 16px; font-weight: bold;"
            )
        else:
            self.lbl_profit.setStyleSheet(
                "color: red; font-size: 16px; font-weight: bold;"
            )
        self.lbl_profit.setText(f"{rezultat['total_pnl']:.2f} $")

        self.plot_widget.clear()
        num_zile = len(df)
        timp = list(range(num_zile))

        candlestick_data = []
        for i in range(num_zile):
            candlestick_data.append(
                (
                    i,
                    float(df["Open"].iloc[i]),
                    float(df["Close"].iloc[i]),
                    float(df["Low"].iloc[i]),
                    float(df["High"].iloc[i]),
                )
            )

        candlestick_item = CandlestickItem(candlestick_data)
        self.plot_widget.addItem(candlestick_item)

        preturi = df["Close"].astype(float).to_numpy()
        sma_scurt_valori = (
            df["Close"]
            .rolling(window=self.spin_short.value())
            .mean()
            .astype(float)
            .to_numpy()
        )
        sma_lung_valori = (
            df["Close"]
            .rolling(window=self.spin_long.value())
            .mean()
            .astype(float)
            .to_numpy()
        )

        self.plot_widget.plot(
            timp, sma_scurt_valori, pen=pg.mkPen("b", width=2), name="SMA Scurt"
        )
        self.plot_widget.plot(
            timp, sma_lung_valori, pen=pg.mkPen("black", width=2), name="SMA Lung"
        )

        buy_x, buy_y, sell_x, sell_y = [], [], [], []
        for i in range(num_zile):
            if semnale_arr[i] == 1:
                buy_x.append(i)
                buy_y.append(preturi[i] * 0.98)
            elif semnale_arr[i] == -1:
                sell_x.append(i)
                sell_y.append(preturi[i] * 1.02)

        if buy_x:
            self.plot_widget.plot(
                buy_x,
                buy_y,
                pen=None,
                symbol="t",
                symbolBrush="g",
                symbolPen="g",
                symbolSize=14,
                name="BUY",
            )
        if sell_x:
            self.plot_widget.plot(
                sell_x,
                sell_y,
                pen=None,
                symbol="t2",
                symbolBrush="r",
                symbolPen="r",
                symbolSize=14,
                name="SELL",
            )

        self.rsi_plot.clear()

        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi_values = 100 - (100 / (1 + rs))

        self.rsi_plot.plot(
            timp, rsi_values.to_numpy(), pen=pg.mkPen("purple", width=2), name="RSI"
        )
        self.rsi_plot.addLine(y=70, pen=pg.mkPen("r", style=Qt.PenStyle.DashLine))
        self.rsi_plot.addLine(y=30, pen=pg.mkPen("g", style=Qt.PenStyle.DashLine))
        self.rsi_plot.setYRange(0, 100)

    def export_pdf(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salveaza Raport", "Raport_Backtest.pdf", "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        html = f"""
        <html>
        <body>
            <h1 style="color: #2E86C1;">Raport Backtesting: {self.input_ticker.text().upper()}</h1>
            <hr>
            <h2>Parametri Strategie:</h2>
            <ul>
                <li>SMA Scurt: {self.spin_short.value()} zile</li>
                <li>SMA Lung: {self.spin_long.value()} zile</li>
                <li>Comision per Tranzactie: {self.spin_fee.value()} %</li>
            </ul>
            <h2>Rezultate Financiare:</h2>
            <table border="1" cellpadding="5" cellspacing="0" width="100%">
                <tr><td>Total Tranzactii</td><td>{self.lbl_trades.text()}</td></tr>
                <tr><td>Rata de Succes</td><td>{self.lbl_winrate.text()}</td></tr>
                <tr><td>Max Drawdown (Risc)</td><td>{self.lbl_dd.text()}</td></tr>
                <tr><td>Profit Net</td><td><b>{self.lbl_profit.text()}</b></td></tr>
            </table>
            <br>
        </body>
        </html>
        """

        writer = QPdfWriter(file_path)
        doc = QTextDocument()
        doc.setHtml(html)
        doc.print(writer)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TradingDashboard()
    window.show()
    sys.exit(app.exec())
