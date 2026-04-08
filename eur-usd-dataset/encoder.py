#!/usr/bin/env python3
"""
Market Language Encoder
Converts OHLC data to symbolic patterns and analyzes 'linguistic' structure
"""

import pandas as pd
import argparse
from collections import Counter
from pathlib import Path
import re
from math import log2


def classify_candlestick(row, body_threshold=0.0001, wick_threshold=0.00015):
    """Classify candle into 7-symbol alphabet."""
    o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
    
    body = c - o
    body_size = abs(body)
    range_ = h - l
    
    if range_ == 0:
        return 'I'
    
    if body_size <= 0.00005 or (body_size / range_ < 0.1):
        return 'I'
    
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    
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


def analyze_linguistic_structure(patterns):
    """LLM-style 'language' analysis of the sequence."""
    analysis = {
        'alphabet': sorted(set(patterns)),
        'entropy': -sum((c/len(patterns)) * log2(c/len(patterns)) 
                   for c in Counter(patterns).values()),
        'resync_markers': [m.start() for m in re.finditer(r'I{10,}', patterns)],
        'ud_clusters': len(re.findall(r'[UD]{2,}', patterns)),
        'ix_framework': patterns.count('IX') + patterns.count('XI'),
        'mechanical_score': 1 - (patterns.count('I') / len(patterns))  # Low I = bot-like
    }
    return analysis


def cross_day_analysis(patterns_by_day):
    """Find patterns that persist across days (the 'grammar')."""
    ngrams_by_day = []
    for day in patterns_by_day:
        day_ngrams = set([day[i:i+3] for i in range(len(day)-2)])
        ngrams_by_day.append(day_ngrams)
    
    # Universal patterns (appear in all days)
    universal = set.intersection(*ngrams_by_day) if len(ngrams_by_day) > 1 else set()
    
    return {
        'universal_trigrams': list(universal)[:20],
        'universal_count': len(universal)
    }


def main():
    parser = argparse.ArgumentParser(description='Encode market data to symbolic language')
    parser.add_argument('files', nargs='+', help='OHLC CSV files (multiple days)')
    parser.add_argument('-o', '--output', default='./market_language', help='Output dir')
    parser.add_argument('--body', type=float, default=0.0001)
    parser.add_argument('--wick', type=float, default=0.00015)
    
    args = parser.parse_args()
    
    all_patterns = []
    
    print(f"Processing {len(args.files)} days...")
    
    for file in args.files:
        df = pd.read_csv(file)
        df['Pattern'] = df.apply(lambda r: classify_candlestick(r, args.body, args.wick), axis=1)
        patterns = ''.join(df['Pattern'])
        all_patterns.append(patterns)
        print(f"  {file}: {len(patterns)} candles")
    
    # Individual analysis
    for i, patterns in enumerate(all_patterns):
        analysis = analyze_linguistic_structure(patterns)
        print(f"\nDay {i+1} Linguistic Profile:")
        print(f"  Entropy: {analysis['entropy']:.2f} bits")
        print(f"  Mechanical Score: {analysis['mechanical_score']:.1%}")
        print(f"  Resync Markers: {len(analysis['resync_markers'])}")
    
    # Cross-day analysis
    if len(all_patterns) > 1:
        cross = cross_day_analysis(all_patterns)
        print(f"\nCross-Day Grammar:")
        print(f"  Universal trigrams: {cross['universal_count']}")
        print(f"  Examples: {cross['universal_trigrams'][:5]}")
    
    # Save
    out = Path(args.output)
    out.mkdir(exist_ok=True)
    
    with open(out / 'combined_sequence.txt', 'w') as f:
        f.write('\n'.join(all_patterns))
    
    print(f"\nSaved to {out}/combined_sequence.txt")
    print(f"Ready for LLM pattern analysis!")


if __name__ == '__main__':
    main()