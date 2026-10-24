#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

typedef struct 
{
    long long timestamp;
    double open, high, low, close, volume;
} PriceData;

typedef struct
{
    double total_pnl, win_rate, max_drawdown;
    int total_trades, winning_trades;
} BacktestResult;

typedef struct
{
    double best_pnl, best_win_rate, best_max_drawdown;
    int best_short, best_long, best_trades;
} OptimizerResult;

double calculate_sma(PriceData* data, int current_index, int period)
{
    if (current_index < period - 1) return 0.0;
    double sum = 0.0;
    for (int i = 0; i < period; i++) sum += data[current_index - i].close;
    return sum / period;
}

double calculate_rsi(PriceData* data, int current_index, int period)
{
    if (current_index < period) return 50.0;
    
    double gain = 0.0, loss = 0.0;
    for (int i = current_index - period + 1; i <= current_index; i++)
    {
        double change = data[i].close - data[i-1].close;
        if (change > 0) gain += change;
        else loss -= change;
    }
    
    if (loss == 0) return 100.0;
    
    double rs = gain / loss;
    return 100.0 - (100.0 / (1.0 + rs));
}

BacktestResult run_sma_crossover(PriceData* data, int data_size, int short_window, int long_window, double commission_pct, int* signals)
{
    bool in_position = false;
    double entry_price = 0.0, profit_total = 0.0;
    int trans_nr = 0, winning_trades = 0;
    
    double init_capital = 10000.0, curr_capital = init_capital, peak_capital = init_capital, max_drawdown = 0.0;
    BacktestResult results = {0.0, 0.0, 0.0, 0, 0}; 

    if (signals != NULL)
    {
        for (int i = 0; i < data_size; i++) signals[i] = 0;
    }

    for (int i = long_window; i < data_size; i++)
    {
        double curr_short = calculate_sma(data, i, short_window);
        double curr_long = calculate_sma(data, i , long_window);
        double prev_short = calculate_sma(data, i - 1, short_window);
        double prev_long = calculate_sma(data, i - 1, long_window);
        
        double current_rsi = calculate_rsi(data, i, 14);

        if (!in_position && (prev_short <= prev_long) && (curr_short > curr_long) && (current_rsi < 70.0))
        {
            entry_price = data[i].close;
            in_position = true;
            if (signals != NULL) signals[i] = 1;
        }
        else if (in_position && (prev_short >= prev_long) && (curr_short < curr_long))
        {
            double exit_price = data[i].close;
            double fee_buy = entry_price * (commission_pct / 100.0);
            double fee_sell = exit_price * (commission_pct / 100.0);
            double trade_profit = exit_price - entry_price - fee_buy - fee_sell;

            profit_total += trade_profit;
            curr_capital += trade_profit;
            trans_nr++;
            
            if (signals != NULL) signals[i] = -1;
            if (trade_profit > 0) winning_trades++;
            
            in_position = false;

            if (curr_capital > peak_capital) peak_capital = curr_capital;
            double drawdown = (peak_capital - curr_capital) / peak_capital * 100.0;
            if (drawdown > max_drawdown) max_drawdown = drawdown;
        }
    }

    results.total_trades = trans_nr;
    results.total_pnl = profit_total;
    results.winning_trades = winning_trades;
    results.max_drawdown = max_drawdown;
    if (trans_nr > 0) results.win_rate = ((double) winning_trades / trans_nr) * 100.0;

    return results;
}

OptimizerResult optimize_strategy(PriceData* data, int data_size, double commission_pct)
{
    OptimizerResult best = {-9999999.0, 0.0, 0.0, 0, 0, 0};
    for (int s = 2; s <= 50; s++)
    {
        for (int l = 10; l <= 200; l++)
        {
            if (s >= l) continue;
            BacktestResult res = run_sma_crossover(data, data_size, s, l, commission_pct, NULL);
            if (res.total_pnl > best.best_pnl)
            {
                best.best_pnl = res.total_pnl;
                best.best_short = s;
                best.best_long = l;
                best.best_win_rate = res.win_rate;
                best.best_max_drawdown = res.max_drawdown;
                best.best_trades = res.total_trades;
            }
        }
    }
    return best;
}