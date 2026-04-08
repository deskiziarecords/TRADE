import re
import pandas as pd
from pathlib import Path

def parse_signal_logs(file_path):
    patterns = []
    
    # Regex to capture the Pattern and the Dark/Lit volume
    # Adjusting for your specific log format
    pattern_regex = r"Pattern:\s*([A-Za-z])"
    route_regex = r"Dark=(\d+),\s*Lit=(\d+)"
    
    with open(file_path, 'r') as f:
        for line in f:
            p_match = re.search(pattern_regex, line)
            r_match = re.search(route_regex, line)
            
            if p_match:
                pattern_char = p_match.group(1)
                dark_vol = int(r_match.group(1)) if r_match else 0
                lit_vol = int(r_match.group(2)) if r_match else 0
                
                patterns.append({
                    'symbol': pattern_char,
                    'dark_lit_ratio': dark_vol / lit_vol if lit_vol > 0 else 0
                })
    
    return patterns

# Quick execution
file_input = 'today.csv' # or .txt
data = parse_signal_logs(file_input)
full_sequence = "".join([d['symbol'] for d in data])

print(f"✅ Extracted Sequence: {full_sequence}")
# Result based on your snippet: UUDDUU