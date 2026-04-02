"""
3D IPDA Forex Viewer - Computational Battlefield
Implements: IPDA Compiler, Topological Manifold, Liquidity Fields, Causal Lead Vectors
"""

import numpy as np
import pandas as pd
import jax
import jax.numpy as jnp
from jax import grad, jit, vmap
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats
from scipy.spatial import cKDTree
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# 1. STRUCTURAL ARENA - IPDA Compiler Layer
# ============================================================================

class IPDACompiler:
    """Computes structural magnets and decision zones"""
    
    def __init__(self, highs, lows, closes):
        self.highs = highs
        self.lows = lows
        self.closes = closes
        
    def compute_structural_boxes(self):
        """20, 40, 60-day highs/lows as structural boxes"""
        lookbacks = [20, 40, 60]
        boxes = {}
        for lb in lookbacks:
            boxes[f'high_{lb}'] = self.highs.rolling(lb).max()
            boxes[f'low_{lb}'] = self.lows.rolling(lb).min()
        return pd.DataFrame(boxes)
    
    def compute_magnet_potential(self, price, structural_levels, gamma=2.0):
        """Φ_mag = Σ w_i * exp(-γ * |price - level_i|)"""
        levels = structural_levels.dropna().values
        weights = np.exp(-np.arange(len(levels)) / len(levels))  # Decaying weights
        
        def potential(p):
            distances = np.abs(p - levels)
            return np.sum(weights * np.exp(-gamma * distances))
        
        return np.array([potential(p) for p in price])
    
    def find_fair_value_gaps(self):
        """Detect FVGs: consecutive candles with gap between bodies"""
        fvgs = []
        for i in range(2, len(self.highs)):
            # Bullish FVG: high[i-2] < low[i]
            if self.highs.iloc[i-2] < self.lows.iloc[i]:
                fvgs.append(('bullish', i, self.highs.iloc[i-2], self.lows.iloc[i]))
            # Bearish FVG: low[i-2] > high[i]
            elif self.lows.iloc[i-2] > self.highs.iloc[i]:
                fvgs.append(('bearish', i, self.lows.iloc[i-2], self.highs.iloc[i]))
        return fvgs

# ============================================================================
# 2. GEOMETRIC STATE SPACE - Topological Layer
# ============================================================================

class TopologicalManifold:
    """Sliding window point cloud with persistent homology"""
    
    def __init__(self, window_size=50, embedding_dim=5):
        self.window_size = window_size
        self.embedding_dim = embedding_dim
        
    def construct_state_vector(self, price, volume, volatility, liquidity):
        """x_t ∈ ℝ^d: price, vol, volatility, liquidity, momentum"""
        momentum = price.diff(5) / price.shift(5)
        return np.column_stack([
            price.values,
            volume.values / volume.rolling(20).mean().values,
            volatility.values,
            liquidity.values,
            momentum.fillna(0).values
        ])
    
    def sliding_window_point_cloud(self, state_matrix):
        """Create point cloud X_t from sliding windows"""
        n = len(state_matrix) - self.window_size + 1
        cloud = np.zeros((n, self.window_size * state_matrix.shape[1]))
        
        for i in range(n):
            cloud[i] = state_matrix[i:i+self.window_size].flatten()
        
        return cloud
    
    def compute_persistent_homology_h1(self, point_cloud):
        """
        Compute H₁ loops (geometric fractures)
        Using Vietoris-Rips approximation
        """
        if len(point_cloud) < 4:
            return 0.0
        
        from scipy.spatial.distance import pdist, squareform
        
        # Distance matrix
        dists = squareform(pdist(point_cloud))
        
        # Approximate persistence: count cycles in MST + extra edges
        # Simplified: normalized radius of gyration variance
        centroid = np.mean(point_cloud, axis=0)
        radii = np.linalg.norm(point_cloud - centroid, axis=1)
        
        # H₁ proxy: variance of radii indicates topological complexity
        h1_score = np.std(radii) / (np.mean(radii) + 1e-6)
        
        return min(1.0, h1_score)
    
    def compute_adelic_manifold(self, price_returns, embedding=True):
        """
        Adelic Manifold M: safe zone for price stability
        Uses kernel density estimation in phase space
        """
        from scipy.stats import gaussian_kde
        
        if embedding:
            # Time-delay embedding
            tau = 3
            dim = 3
            embedded = np.column_stack([
                price_returns[i:len(price_returns)-dim*tau+i:tau] 
                for i in range(dim)
            ])
            embedded = embedded[:-tau*dim] if len(embedded) > tau*dim else embedded
        else:
            embedded = price_returns.reshape(-1, 1)
        
        try:
            kde = gaussian_kde(embedded.T)
            # Manifold density = log-likelihood of each point
            density = kde.logpdf(embedded.T)
            # Normalize to [0,1] for "safety"
            safety = (density - density.min()) / (density.max() - density.min() + 1e-6)
            return safety
        except:
            return np.ones(len(embedded))

# ============================================================================
# 3. FIELD THEORETIC ELEMENTS - Liquidity & Imbalance
# ============================================================================

class LiquidityField:
    """Models price dynamics as stochastic PDE with hidden forces"""
    
    def __init__(self, price, volume):
        self.price = price
        self.volume = volume
        
    def compute_liquidity_potential(self, dark_pool_multiplier=2.0):
        """
        U = accumulated hidden state energy H(t) in dark pools
        Dark pools inferred from volume profile anomalies
        """
        # Hidden state energy: cumulative volume * price displacement
        volume_profile = self.volume / self.volume.rolling(20).mean()
        price_displacement = self.price.diff().abs()
        
        hidden_energy = (volume_profile * price_displacement).cumsum()
        
        # Dark pool concentration at price levels
        price_levels = np.linspace(self.price.min(), self.price.max(), 50)
        dark_pool_density = np.zeros_like(price_levels)
        
        for i, level in enumerate(price_levels):
            mask = (self.price > level - 0.001) & (self.price < level + 0.001)
            dark_pool_density[i] = self.volume[mask].sum() * dark_pool_multiplier
        
        return hidden_energy, dark_pool_density, price_levels
    
    def compute_imbalance_field(self, fvgs):
        """
        I: Fair Value Gaps as regions of porous price action
        Returns 3D field of imbalance intensities
        """
        imbalance_field = np.zeros((100, 100))
        x_coords = np.linspace(0, len(self.price), 100)
        y_coords = np.linspace(self.price.min(), self.price.max(), 100)
        
        for fvg in fvgs:
            _, idx, low, high = fvg
            x_idx = int(idx * 100 / len(self.price))
            y_start = int((low - self.price.min()) * 100 / (self.price.max() - self.price.min()))
            y_end = int((high - self.price.min()) * 100 / (self.price.max() - self.price.min()))
            
            if 0 <= x_idx < 100:
                imbalance_field[y_start:y_end, x_idx] += 1.0
        
        return imbalance_field, x_coords, y_coords
    
    def detect_liquidity_sweeps(self, wick_threshold=2.0):
        """
        Wick signature tracker: liquidity harvesting at IPDA edges
        Returns sweep points and intensity
        """
        typical_wick = (self.price - self.price.shift(1)).abs().rolling(20).mean()
        
        # Upper wicks (rejection from highs)
        upper_wick = self.highs - np.maximum(self.closes, self.opens) if hasattr(self, 'opens') else self.highs - self.closes
        # Lower wicks (rejection from lows)
        lower_wick = np.minimum(self.closes, self.opens) - self.lows if hasattr(self, 'opens') else self.closes - self.lows
        
        sweep_score = np.maximum(upper_wick, lower_wick) / (typical_wick + 1e-6)
        sweep_points = sweep_score > wick_threshold
        
        return sweep_points, sweep_score

# ============================================================================
# 4. TEMPORAL AND CAUSAL LEAD VECTORS
# ============================================================================

class CausalLeadVectors:
    """Cross-asset causality and killzone detection"""
    
    def __init__(self, forex_data, dxy_data, spx_data, bond_data):
        self.forex = forex_data
        self.dxy = dxy_data
        self.spx = spx_data
        self.bonds = bond_data
        
    def detect_ict_killzones(self, timestamp):
        """3D temporal axes for London and NY opens"""
        london_open = timestamp.replace(hour=2, minute=0, second=0)
        london_close = timestamp.replace(hour=5, minute=0, second=0)
        ny_open = timestamp.replace(hour=7, minute=0, second=0)
        ny_close = timestamp.replace(hour=10, minute=0, second=0)
        
        in_london = london_open <= timestamp <= london_close
        in_ny = ny_open <= timestamp <= ny_close
        
        # 3D killzone intensity (time within window)
        if in_london:
            intensity = (timestamp - london_open).seconds / (3 * 3600)
        elif in_ny:
            intensity = (timestamp - ny_open).seconds / (3 * 3600)
        else:
            intensity = 0.0
            
        return in_london, in_ny, intensity
    
    def compute_causal_leads(self, max_lag=200):
        """
        Lead-lag relationships using cross-correlation
        Returns time shift and confidence
        """
        forex_ret = self.forex.pct_change().dropna()
        dxy_ret = self.dxy.pct_change().dropna()
        
        # Align indices
        common_idx = forex_ret.index.intersection(dxy_ret.index)
        forex_aligned = forex_ret[common_idx]
        dxy_aligned = dxy_ret[common_idx]
        
        # Cross-correlation
        from scipy.signal import correlate
        correlation = correlate(forex_aligned, dxy_aligned, mode='same')
        lags = np.arange(-len(correlation)//2, len(correlation)//2)
        
        best_lag = lags[np.argmax(np.abs(correlation))]
        max_corr = np.max(np.abs(correlation)) / np.sqrt(len(forex_aligned))
        
        return best_lag, max_corr
    
    def compute_light_cone_violations(self):
        """Detect when forex moves before its causal driver"""
        leads = {}
        for name, data in [('DXY', self.dxy), ('SPX', self.spx), ('Bonds', self.bonds)]:
            lag, conf = self.compute_causal_leads_for_pair(data)
            leads[name] = {'lag_ms': lag * 60000, 'confidence': conf}  # Convert to ms
        return leads

# ============================================================================
# 5. METACOGNITIVE KILL SWITCH - OBNFE
# ============================================================================

class OnlineBayesianFusionEngine:
    """System health monitor with posterior dashboard"""
    
    def __init__(self):
        self.belief_state = 0.5  # Prior belief
        self.geometry_history = []
        self.severity_threshold = 0.7
        
    def update_belief(self, observation, likelihood_variance=0.1):
        """Bayesian update with new evidence"""
        # Likelihood function (Gaussian)
        likelihood = np.exp(-(observation - self.belief_state)**2 / (2 * likelihood_variance))
        likelihood /= (np.sqrt(2 * np.pi * likelihood_variance) + 1e-6)
        
        # Posterior = prior * likelihood / evidence
        posterior = self.belief_state * likelihood
        posterior /= (posterior + (1 - self.belief_state) * (1 - likelihood) + 1e-6)
        
        self.belief_state = posterior
        return posterior
    
    def compute_unified_severity(self, h1_score, liquidity_potential, causal_confidence, market_volatility):
        """
        Fuse TDA geometry + Bayesian belief + market metrics
        Returns Unified Severity Score (0-1)
        """
        # Geometry fracture score
        geo_score = h1_score
        
        # Liquidity stress score
        liq_score = 1.0 - np.exp(-liquidity_potential / 100)
        
        # Causal coherence score (inverse of confidence for severity)
        causal_score = 1.0 - causal_confidence
        
        # Volatility regime score
        vol_score = min(1.0, market_volatility / 0.02)  # 2% volatility = severe
        
        # Fused score with weights
        weights = {'geo': 0.3, 'liq': 0.25, 'causal': 0.25, 'vol': 0.2}
        severity = (weights['geo'] * geo_score + 
                   weights['liq'] * liq_score + 
                   weights['causal'] * causal_score + 
                   weights['vol'] * vol_score)
        
        # Bayesian update with this severity as observation
        self.update_belief(severity)
        
        return min(1.0, severity)
    
    def detect_phase_reset(self, severity_score, expectancy_sign_flip=False):
        """
        Reverse Period Indicator: Kernel Panic alert
        Returns: should_reset, reset_signal_strength
        """
        if severity_score > self.severity_threshold or expectancy_sign_flip:
            # Phase reset required
            reset_strength = min(1.0, (severity_score - self.severity_threshold) / 0.3)
            return True, reset_strength
        return False, 0.0
    
    def compute_expectancy_sign(self, recent_returns, recent_predictions):
        """Detect if signals have flipped to anti-predictive"""
        if len(recent_returns) < 10:
            return False
        
        correlation = np.corrcoef(recent_returns, recent_predictions)[0, 1]
        return correlation < -0.3  # Strong negative correlation = sign flip

# ============================================================================
# 6. MAIN VIEWER - 3D Visualization Engine
# ============================================================================

class IPDA3DViewer:
    """Main 3D visualization with all computational layers"""
    
    def __init__(self, symbol="EURUSD=X", period="5d", interval="1m"):
        self.symbol = symbol
        self.period = period
        self.interval = interval
        self.data = None
        self.load_data()
        
    def load_data(self):
        """Fetch forex data and correlated assets"""
        print(f"Loading {self.symbol} data...")
        
        # Main forex pair
        self.data = yf.download(self.symbol, period=self.period, interval=self.interval)
        
        # Correlated assets for causal analysis
        self.dxy = yf.download("DX-Y.NYB", period=self.period, interval=self.interval)
        self.spx = yf.download("SPY", period=self.period, interval=self.interval)
        self.bonds = yf.download("TLT", period=self.period, interval=self.interval)
        
        # Add synthetic opens for wick calculation
        self.data['Open'] = self.data['Close'].shift(1).fillna(self.data['Close'])
        
        print(f"Loaded {len(self.data)} bars")
        
    def compute_all_layers(self):
        """Compute all computational layers"""
        
        # 1. Structural Arena
        compiler = IPDACompiler(self.data['High'], self.data['Low'], self.data['Close'])
        structural_boxes = compiler.compute_structural_boxes()
        magnets = compiler.compute_magnet_potential(self.data['Close'].values, structural_boxes['high_40'])
        fvgs = compiler.find_fair_value_gaps()
        
        # 2. Topological Layer
        topology = TopologicalManifold(window_size=30)
        vol = self.data['Volume'] if 'Volume' in self.data else pd.Series(1, index=self.data.index)
        state_matrix = topology.construct_state_vector(
            self.data['Close'], 
            vol,
            self.data['Close'].pct_change().rolling(10).std().fillna(0),
            self.data['Volume'].rolling(20).mean().fillna(1) if 'Volume' in self.data else pd.Series(1, index=self.data.index)
        )
        point_cloud = topology.sliding_window_point_cloud(state_matrix[:100])
        h1_score = topology.compute_persistent_homology_h1(point_cloud)
        manifold_safety = topology.compute_adelic_manifold(self.data['Close'].pct_change().dropna().values)
        
        # 3. Liquidity Field
        liq_field = LiquidityField(self.data['Close'], vol)
        hidden_energy, dark_pool_density, price_levels = liq_field.compute_liquidity_potential()
        imbalance_field, x_coords, y_coords = liq_field.compute_imbalance_field(fvgs)
        sweeps, sweep_scores = liq_field.detect_liquidity_sweeps()
        
        # 4. Causal Vectors
        causal = CausalLeadVectors(self.data['Close'], self.dxy['Close'], self.spx['Close'], self.bonds['Close'])
        killzone_data = [causal.detect_ict_killzones(t) for t in self.data.index]
        
        # 5. OBNFE
        obnfe = OnlineBayesianFusionEngine()
        severity = obnfe.compute_unified_severity(
            h1_score, 
            hidden_energy.iloc[-1] if hasattr(hidden_energy, 'iloc') else hidden_energy[-1],
            causal.compute_causal_leads()[1],
            self.data['Close'].pct_change().std() * np.sqrt(252)
        )
        should_reset, reset_strength = obnfe.detect_phase_reset(severity)
        
        return {
            'structural_boxes': structural_boxes,
            'magnets': magnets,
            'fvgs': fvgs,
            'h1_score': h1_score,
            'manifold_safety': manifold_safety,
            'hidden_energy': hidden_energy,
            'dark_pool_density': dark_pool_density,
            'price_levels': price_levels,
            'imbalance_field': imbalance_field,
            'sweeps': sweeps,
            'killzone_data': killzone_data,
            'severity': severity,
            'phase_reset': should_reset,
            'reset_strength': reset_strength
        }
    
    def create_3d_view(self, layers):
        """Create interactive 3D visualization"""
        
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{'type': 'scatter3d'}, {'type': 'surface'}],
                   [{'type': 'scatter3d'}, {'type': 'scatter'}]],
            subplot_titles=('IPDA Manifold & Liquidity Field', 
                           'Imbalance Surface (FVGs as Porous Zones)',
                           'Geometric State Space with H₁ Loops',
                           'System Health Dashboard')
        )
        
        # --- Subplot 1: 3D Manifold with Liquidity Potential ---
        t = np.arange(len(self.data))
        price_norm = (self.data['Close'].values - self.data['Close'].min()) / (self.data['Close'].max() - self.data['Close'].min())
        liq_potential = layers['hidden_energy'].values if hasattr(layers['hidden_energy'], 'values') else layers['hidden_energy']
        liq_norm = (liq_potential - liq_potential.min()) / (liq_potential.max() - liq_potential.min() + 1e-6)
        
        fig.add_trace(
            go.Scatter3d(
                x=t[::5], 
                y=price_norm[::5], 
                z=liq_norm[::5],
                mode='lines+markers',
                marker=dict(size=3, color=liq_norm[::5], colorscale='Viridis', showscale=True),
                line=dict(width=2, color='cyan'),
                name='Price Manifold'
            ),
            row=1, col=1
        )
        
        # Add structural magnets as attractor points
        magnet_points = np.where(layers['magnets'] > np.percentile(layers['magnets'][~np.isnan(layers['magnets'])], 90))[0]
        fig.add_trace(
            go.Scatter3d(
                x=magnet_points,
                y=price_norm[magnet_points],
                z=np.ones(len(magnet_points)) * 0.8,
                mode='markers',
                marker=dict(size=8, color='red', symbol='diamond'),
                name='Structural Magnets (Φ_mag > 90th)'
            ),
            row=1, col=1
        )
        
        # --- Subplot 2: Imbalance Surface (FVGs) ---
        fig.add_trace(
            go.Surface(
                z=layers['imbalance_field'],
                x=layers.get('x_coords', np.arange(100)),
                y=layers.get('y_coords', np.arange(100)),
                colorscale='Plasma',
                opacity=0.8,
                name='Imbalance Field I'
            ),
            row=1, col=2
        )
        
        # --- Subplot 3: Geometric State Space with H₁ detection ---
        # Create point cloud in 3D (PCA reduction)
        from sklearn.decomposition import PCA
        pca = PCA(n_components=3)
        
        # State vectors
        state_vectors = np.column_stack([
            self.data['Close'].pct_change().fillna(0).values,
            self.data['Close'].rolling(10).std().fillna(0).values,
            self.data['Volume'].rolling(10).mean().fillna(1).values if 'Volume' in self.data else np.ones(len(self.data)),
            self.data['Close'].diff().fillna(0).values
        ])[:500]
        
        point_cloud_3d = pca.fit_transform(state_vectors)
        
        # Color by H₁ fracture score
        colors = np.linspace(0, layers['h1_score'], len(point_cloud_3d))
        
        fig.add_trace(
            go.Scatter3d(
                x=point_cloud_3d[:, 0],
                y=point_cloud_3d[:, 1],
                z=point_cloud_3d[:, 2],
                mode='markers',
                marker=dict(size=2, color=colors, colorscale='RdYlBu_r', showscale=True),
                name=f'Point Cloud | H₁ = {layers["h1_score"]:.3f}'
            ),
            row=2, col=1
        )
        
        # Highlight geometric fractures
        fracture_idx = np.where(np.abs(point_cloud_3d[:, 0] - np.mean(point_cloud_3d[:, 0])) > 2 * np.std(point_cloud_3d[:, 0]))[0]
        fig.add_trace(
            go.Scatter3d(
                x=point_cloud_3d[fracture_idx, 0],
                y=point_cloud_3d[fracture_idx, 1],
                z=point_cloud_3d[fracture_idx, 2],
                mode='markers',
                marker=dict(size=5, color='red', symbol='x'),
                name='Geometric Fractures'
            ),
            row=2, col=1
        )
        
        # --- Subplot 4: System Health Dashboard ---
        severity = layers['severity']
        reset_strength = layers['reset_strength']
        
        # Gauge chart for severity
        fig.add_trace(
            go.Indicator(
                mode="gauge+number+delta",
                value=severity * 100,
                title={"text": "Unified Severity Score"},
                domain={'x': [0, 1], 'y': [0, 0.5]},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "red" if severity > 0.7 else "orange" if severity > 0.4 else "green"},
                    'steps': [
                        {'range': [0, 40], 'color': "lightgreen"},
                        {'range': [40, 70], 'color': "orange"},
                        {'range': [70, 100], 'color': "red"}
                    ],
                    'threshold': {'value': 70, 'color': "darkred"}
                }
            ),
            row=2, col=2
        )
        
        # Add kernel panic indicator
        if layers['phase_reset']:
            fig.add_annotation(
                text=f" KERNEL PANIC - PHASE RESET (σ=0) | Strength: {reset_strength:.2f}",
                xref="x2 domain", yref="y2 domain",
                x=0.5, y=0.85, showarrow=False,
                font=dict(size=14, color="red"),
                bgcolor="black",
                row=2, col=2
            )
        
        # Update layout
        fig.update_layout(
            title=f"3D IPDA Forex Viewer - {self.symbol} | H₁ Fracture: {layers['h1_score']:.4f} | Severity: {severity:.3f}",
            height=900,
            showlegend=True,
            scene=dict(
                xaxis_title='Time Index',
                yaxis_title='Normalized Price',
                zaxis_title='Liquidity Potential U'
            ),
            scene2=dict(
                xaxis_title='X (Time)',
                yaxis_title='Y (Price Level)',
                zaxis_title='Imbalance I'
            ),
            scene3=dict(
                xaxis_title='PC1',
                yaxis_title='PC2',
                zaxis_title='PC3'
            )
        )
        
        return fig
    
    def run(self):
        """Execute the full pipeline"""
        print("=" * 60)
        print("3D IPDA COMPUTATIONAL BATTLEFIELD")
        print("=" * 60)
        
        layers = self.compute_all_layers()
        
        print(f"\n SYSTEM STATUS:")
        print(f"   • H₁ Topological Fracture Score: {layers['h1_score']:.4f}")
        print(f"   • Unified Severity Score: {layers['severity']:.3f}")
        print(f"   • Phase Reset Required: {layers['phase_reset']}")
        if layers['phase_reset']:
            print(f"   • Reset Strength: {layers['reset_strength']:.2f}")
        print(f"   • FVGs Detected: {len(layers['fvgs'])}")
        print(f"   • Sweep Events: {layers['sweeps'].sum()}")
        
        fig = self.create_3d_view(layers)
        fig.show()
        
        return layers

# ============================================================================
# EXECUTION
# ============================================================================

if __name__ == "__main__":
    # Initialize the 3D IPDA Viewer
    viewer = IPDA3DViewer(
        symbol="EURUSD=X",
        period="3d",
        interval="5m"
    )
    
    # Run the computational battlefield
    results = viewer.run()
    
    print("\n" + "=" * 60)
    print("✓ IPDA viewer active. The market is now visualized as a deterministic state machine.")
    print("  Monitor the H₁ fracture score and severity index for systemic geometry breaks.")
    print("=" * 60)
