## Numerical Example
```
| Input              | Value                                                                           |
| ------------------ | ------------------------------------------------------------------------------- |
| $Q_t$              | \$52,100 (from previous sizing)                                                 |
| Venues             | 3: Oanda, Interactive Brokers, LMAX                                             |
| Liquidity $\gamma$ | \[0.1, 0.05, 0.08]                                                              |
| Latency (ms)       | \[20, 50, 15]                                                                   |
| OFI correlation    | $\begin{bmatrix} 1 & 0.3 & 0.5 \\ 0.3 & 1 & 0.4 \\ 0.5 & 0.4 & 1 \end{bmatrix}$ |

```
### Result:
```
| Venue | Weight | Quantity | Slippage |
| ----- | ------ | -------- | -------- |
| Oanda | 0.15   | \$7,815  | 0.12%    |
| IB    | 0.60   | \$31,260 | 0.08%    |
| LMAX  | 0.25   | \$13,025 | 0.10%    |
