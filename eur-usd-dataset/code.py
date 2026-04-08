#!/usr/bin/env python3
"""
Candlestick Pattern Encoder (Batch + Merge Mode)
Converts OHLC CSV data to symbolic patterns for LLM analysis
"""

import pandas as pd
import argparse
from collections import Counter
from pathlib import Path


def classify_candlestick(row, body_threshold=0.0001, wick_threshold=0.00015):
    open_p, high, low, close = row['Open'], row['High'], row['Low'], row['Close']
    body = close - open_p
    body_size = abs(body)
    total_range = high - low
    
    if total_range == 0:
        return 'I'
    if body_size <= 0.00005 or (body_size / total_range < 0.1):
        return 'I'
    
    upper_wick = high - max(open_p, close)
    lower_wick = min(open_p, close) - low
    
    has_long_upper = upper_wick > wick_threshold and upper_wick > body_size * 1.5
    has_long_lower = lower_wick > wick_threshold and lower_wick > body_size * 1.5
    
    if has_long_upper and not has_long_lower:
        return 'W'
    if has_long_lower and not has_long_upper:
        return 'w'
    
    is_strong = body_size > body_threshold
    if body > 0:
        return 'B' if is_strong else 'U'
    elif body < 0:
        return 'X' if is_strong else 'D'
    return 'I'


def generate_sliding_windows(pattern_string, window_size=10, lookahead=1):
    windows = []
    for i in range(len(pattern_string) - window_size - lookahead + 1):
        windows.append({
            'position': i,
            'input': pattern_string[i:i + window_size],
            'target': pattern_string[i + window_size:i + window_size + lookahead]
        })
    return windows


def process_dataframe(df, output_dir=None, window_size=10, lookahead=1, 
                      body_threshold=0.0001, wick_threshold=0.00015):
    required = ['Open', 'High', 'Low', 'Close']
    if not all(col in df.columns for col in required):
        raise ValueError(f"DataFrame must contain columns: {required}")
    
    df['Pattern'] = df.apply(
        lambda row: classify_candlestick(row, body_threshold, wick_threshold), axis=1
    )
    
    pattern_string = ''.join(df['Pattern'].tolist())
    windows = generate_sliding_windows(pattern_string, window_size, lookahead)
    
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
    
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(out_path / 'annotated_candles.csv', index=False)
        with open(out_path / 'pattern_sequence.txt', 'w') as f:
            f.write(pattern_string)
        pd.DataFrame(windows).to_csv(out_path / 'training_data.csv', index=False)
        with open(out_path / 'summary.txt', 'w') as f:
            f.write(f"Pattern Sequence: {pattern_string[:200]}{'...' if len(pattern_string)>200 else ''}\n\n")
            f.write("Statistics:\n")
            for key, val in results['stats'].items():
                f.write(f"  {key}: {val}\n")
        print(f"📁 Saved outputs to: {out_path}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Convert OHLC candlestick data to symbolic patterns. Supports batch & merged modes.'
    )
    parser.add_argument('input_path', help='Input CSV file OR directory containing CSV files')
    parser.add_argument('-o', '--output', help='Output directory', default='./output')
    parser.add_argument('-w', '--window', type=int, default=10, help='Sliding window size')
    parser.add_argument('-l', '--lookahead', type=int, default=1, help='Lookahead candles')
    parser.add_argument('--body-threshold', type=float, default=0.0001)
    parser.add_argument('--wick-threshold', type=float, default=0.00015)
    parser.add_argument('--merge', action='store_true', 
                        help='Merge all CSVs into one continuous sequence before processing')
    
    args = parser.parse_args()
    input_path = Path(args.input_path)
    
    # Resolve CSV files
    if input_path.is_file() and input_path.suffix.lower() == '.csv':
        csv_files = [input_path]
    elif input_path.is_dir():
        csv_files = sorted(input_path.glob('*.csv'))
        if not csv_files:
            print(f"❌ No CSV files found in: {input_path}")
            return
    else:
        print(f"❌ Invalid input: {input_path}")
        return

    print(f"🔍 Found {len(csv_files)} CSV file(s).")
    
    if args.merge and len(csv_files) > 1:
        print(f"🔄 Merging files into a single continuous sequence...")
        dfs = []
        for f in csv_files:
            try:
                dfs.append(pd.read_csv(f))
            except Exception as e:
                print(f"⚠️ Skipping {f.name}: {e}")
                
        if not dfs:
            print("❌ No valid data to merge.")
            return
            
        combined_df = pd.concat(dfs, ignore_index=True)
        
        # Attempt chronological sorting
        time_cols = [c for c in combined_df.columns if any(k in c.lower() for k in ['date', 'time', 'timestamp', 'datetime'])]
        if time_cols:
            try:
                combined_df[time_cols[0]] = pd.to_datetime(combined_df[time_cols[0]])
                combined_df = combined_df.sort_values(time_cols[0]).reset_index(drop=True)
                print(f"📅 Sorted by column: '{time_cols[0]}'")
            except Exception:
                print("⚠️ Could not parse dates. Using file concatenation order.")
        else:
            print("⚠️ No datetime column found. Using file concatenation order.")
            
        print(f"📊 Combined dataset: {len(combined_df)} candles total.\n")
        results = process_dataframe(
            combined_df, args.output, args.window, args.lookahead,
            args.body_threshold, args.wick_threshold
        )
        
    else:
        # Process separately (original behavior)
        out_base = Path(args.output)
        out_base.mkdir(parents=True, exist_ok=True)
        success = 0
        for csv_file in csv_files:
            print(f"\n📊 Processing: {csv_file.name}")
            try:
                df = pd.read_csv(csv_file)
                res = process_dataframe(
                    df, out_base / csv_file.stem, args.window, args.lookahead,
                    args.body_threshold, args.wick_threshold
                )
                print(f"✅ Done: {res['stats']['total_candles']} candles")
                success += 1
            except Exception as e:
                print(f"❌ Failed: {e}")
        print(f"\n🏁 Batch complete. {success}/{len(csv_files)} processed.")
        return

    # Print merged summary
    seq = results['pattern_string']
    print(f"\n{'='*60}")
    print(f"📦 MERGED PATTERN ENCODING COMPLETE")
    print(f"{'='*60}")
    print(f"Total candles: {results['stats']['total_candles']}")
    print(f"Training windows: {results['stats']['training_examples']}")
    print(f"Distribution: {results['stats']['pattern_distribution']}")
    if len(seq) > 200:
        print(f"Sequence Preview: {seq[:100]}...{seq[-100:]}")
    else:
        print(f"Sequence: {seq}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()