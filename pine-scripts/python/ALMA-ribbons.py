# ALMA Ribbons in Python

# Import necessary libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Define ALMA function
def alma(data, length, offset, sigma):
    m = offset * (length - 1) / 2.0
    weights = np.exp(-0.5 * ((np.arange(length) - m) / sigma) ** 2)
    weights /= weights.sum()
    return np.convolve(data, weights, mode='valid')

# Input parameters
A1Length = 12
A2Length = 36
A3Length = 89
A4Length = 200
A5Length = 633
Offset = 0.85
Sigma = 6

# Assuming 'close' is a pandas Series containing the closing prices
src = close  # Replace with actual data

# Calculate ALMA values
ALMA1 = alma(src, A1Length, Offset, Sigma)
ALMA1_2inc1 = alma(src, A1Length + ((A2Length - A1Length) / 5), Offset, Sigma)
ALMA1_2inc2 = alma(src, A1Length + (((A2Length - A1Length) / 5) * 2), Offset, Sigma)
ALMA1_2inc3 = alma(src, A1Length + (((A2Length - A1Length) / 5) * 3), Offset, Sigma)
ALMA1_2inc4 = alma(src, A1Length + (((A2Length - A1Length) / 5) * 4), Offset, Sigma)

ALMA2 = alma(src, A2Length, Offset, Sigma)
ALMA2_3inc1 = alma(src, A2Length + ((A3Length - A2Length) / 7), Offset, Sigma)
ALMA2_3inc2 = alma(src, A2Length + (((A3Length - A2Length) / 7) * 2), Offset, Sigma)
ALMA2_3inc3 = alma(src, A2Length + (((A3Length - A2Length) / 7) * 3), Offset, Sigma)
ALMA2_3inc4 = alma(src, A2Length + (((A3Length - A2Length) / 7) * 4), Offset, Sigma)
ALMA2_3inc5 = alma(src, A2Length + (((A3Length - A2Length) / 7) * 5), Offset, Sigma)
ALMA2_3inc6 = alma(src, A2Length + (((A3Length - A2Length) / 7) * 6), Offset, Sigma)

ALMA3 = alma(src, A3Length, Offset, Sigma)
ALMA3_4inc1 = alma(src, A3Length + ((A4Length - A3Length) / 7), Offset, Sigma)
ALMA3_4inc2 = alma(src, A3Length + (((A4Length - A3Length) / 7) * 2), Offset, Sigma)
ALMA3_4inc3 = alma(src, A3Length + (((A4Length - A3Length) / 7) * 3), Offset, Sigma)
ALMA3_4inc4 = alma(src, A3Length + (((A4Length - A3Length) / 7) * 4), Offset, Sigma)
ALMA3_4inc5 = alma(src, A3Length + (((A4Length - A3Length) / 7) * 5), Offset, Sigma)
ALMA3_4inc6 = alma(src, A3Length + (((A4Length - A3Length) / 7) * 6), Offset, Sigma)

ALMA4 = alma(src, A4Length, Offset, Sigma)
ALMA4_5inc1 = alma(src, A4Length + ((A5Length - A4Length) / 7), Offset, Sigma)
ALMA4_5inc2 = alma(src, A4Length + (((A5Length - A4Length) / 7) * 2), Offset, Sigma)
ALMA4_5inc3 = alma(src, A4Length + (((A5Length - A4Length) / 7) * 3), Offset, Sigma)
ALMA4_5inc4 = alma(src, A4Length + (((A5Length - A4Length) / 7) * 4), Offset, Sigma)
ALMA4_5inc5 = alma(src, A4Length + (((A5Length - A4Length) / 7) * 5), Offset, Sigma)
ALMA4_5inc6 = alma(src, A4Length + (((A5Length - A4Length) / 7) * 6), Offset, Sigma)

ALMA5 = alma(src, A5Length, Offset, Sigma)
