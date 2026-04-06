#!/usr/bin/env python3
"""
Candlestick Pattern Encoder
Converts OHLC CSV data to symbolic patterns for LLM analysis
"""

import pandas as pd
import argparse
from collections import Counter
from pathlib import Path


def classify_candlestick(row, body_threshold=0.0001, wick_threshold=0.00015):
    """
    Classify a single candlestick into symbolic pattern.
    
    U = bullish small      B = bullish strong
    D = bearish small      X = bearish strong  
    I = indecision/doji    W = long wick up     w = long wick down
    """
    open_p, high, low, close = row['Open'], row['High'], row['Low'], row['Close']
    
    body = close - open_p
    body_size = abs(body)
    total_range = high - low
    
    if total_range == 0:
        return 'I'
    
    # Doji detection: very small body relative to range
    if body_size <= 0.00005 or (body_size / total_range < 0.1):
        return 'I'
    
    # Calculate wicks
    upper_wick = high - max(open_p, close)
    lower_wick = min(open_p, close) - low
    
    # Long wick detection (prominent relative to body)
    has_long_upper = upper_wick > wick_threshold and upper_wick > body_size * 1.5
    has_long_lower = lower_wick > wick_threshold and lower_wick > body_size * 1.5
    
    if has_long_upper and not has_long_lower:
        return 'W'
    if has_long_lower and not has_long_upper:
        return 'w'
    
    # Body-based classification
    is_strong = body_size > body_threshold
    
    if body > 0:
        return 'B' if is_strong else 'U'
    elif body < 0:
        return 'X' if is_strong else 'D'
    
    return 'I'


def generate_sliding_windows(pattern_string, window_size=10, lookahead=1):
    """Generate sliding windows for LLM training."""
    windows = []
    
    for i in range(len(pattern_string) - window_size - lookahead + 1):
        windows.append({
            'position': i,
            'input': pattern_string[i:i + window_size],
            'target': pattern_string[i + window_size:i + window_size + lookahead]
        })
    
    return windows


def process_csv(input_file, output_dir=None, window_size=10, lookahead=1, 
                body_threshold=0.0001, wick_threshold=0.00015):
    """
    Process OHLC CSV and generate symbolic outputs.
    """
    # Read data
    df = pd.read_csv(input_file)
    
    # Validate columns
    required = ['Open', 'High', 'Low', 'Close']
    if not all(col in df.columns for col in required):
        raise ValueError(f"CSV must contain columns: {required}")
    
    # Classify candles
    df['Pattern'] = df.apply(
        lambda row: classify_candlestick(row, body_threshold, wick_threshold), 
        axis=1
    )
    
    # Generate pattern string
    pattern_string = ''.join(df['Pattern'].tolist())
    
    # Generate sliding windows
    windows = generate_sliding_windows(pattern_string, window_size, lookahead)
    
    # Prepare outputs
    results = {
        'dataframe': df,
        'pattern_string': pattern_string,
        'windows': windows,
        'stats': {
            'total_candles': len(df),
            'pattern_distribution': dict(Counter(pattern_string)),
            'training_examples': len(windows)
        }
    }
    
    # Save outputs if directory provided
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        # Save annotated CSV
        df.to_csv(out_path / 'annotated_candles.csv', index=False)
        
        # Save pattern string
        with open(out_path / 'pattern_sequence.txt', 'w') as f:
            f.write(pattern_string)
        
        # Save training data
        train_df = pd.DataFrame(windows)
        train_df.to_csv(out_path / 'training_data.csv', index=False)
        
        # Save summary
        with open(out_path / 'summary.txt', 'w') as f:
            f.write(f"Pattern Sequence: {pattern_string}\n\n")
            f.write(f"Statistics:\n")
            for key, val in results['stats'].items():
                f.write(f"  {key}: {val}\n")
        
        print(f"Saved outputs to: {out_path}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Convert OHLC candlestick data to symbolic patterns'
    )
    parser.add_argument('input', help='Input CSV file with OHLC data')
    parser.add_argument('-o', '--output', help='Output directory', default='./output')
    parser.add_argument('-w', '--window', type=int, default=10, 
                       help='Sliding window size (default: 10)')
    parser.add_argument('-l', '--lookahead', type=int, default=1,
                       help='Lookahead candles to predict (default: 1)')
    parser.add_argument('--body-threshold', type=float, default=0.0001,
                       help='Body size threshold for strong candles')
    parser.add_argument('--wick-threshold', type=float, default=0.00015,
                       help='Wick size threshold for long wick detection')
    
    args = parser.parse_args()
    
    # Process
    results = process_csv(
        args.input,
        args.output,
        args.window,
        args.lookahead,
        args.body_threshold,
        args.wick_threshold
    )
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"PATTERN ENCODING COMPLETE")
    print(f"{'='*60}")
    print(f"Sequence ({len(results['pattern_string'])} candles):")
    print(results['pattern_string'])
    print(f"\nPattern distribution: {results['stats']['pattern_distribution']}")
    print(f"Training examples: {results['stats']['training_examples']}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()