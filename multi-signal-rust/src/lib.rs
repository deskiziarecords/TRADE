// ============================================================================
// position_sizing_rust/src/lib.rs
// A comprehensive position sizing and signal detection library
// ============================================================================

use std::f64;
use ndarray::{Array1, Array2, Axis};

// ============================================================================
// Module 1: Volatility Decay Detection
// ============================================================================

/// Detects when ATR falls below a factor of its initial value within a horizon.
/// 
/// # Arguments
/// * `high` - Array of high prices
/// * `low` - Array of low prices  
/// * `close` - Array of close prices
/// * `lookback` - ATR calculation window (e.g., 14)
/// * `horizon` - Tuple (min_horizon, max_horizon) in bars
/// * `factor` - Threshold factor (e.g., 0.7 = 70% of initial ATR)
/// 
/// # Returns
/// Boolean vector where true indicates volatility decay detected
pub fn volatility_decay_signal(
    high: &[f64],
    low: &[f64],
    close: &[f64],
    lookback: usize,
    horizon: (usize, usize),
    factor: f64,
) -> Vec<bool> {
    let n = close.len();
    if n < lookback + horizon.1 {
        return vec![false; n];
    }

    // 1. Calculate True Range
    let mut tr = vec![0.0; n];
    for i in 0..n {
        let tr1 = high[i] - low[i];
        let tr2 = if i > 0 { (high[i] - close[i - 1]).abs() } else { 0.0 };
        let tr3 = if i > 0 { (low[i] - close[i - 1]).abs() } else { 0.0 };
        tr[i] = tr1.max(tr2).max(tr3);
    }

    // 2. Calculate ATR (Simple Moving Average)
    let mut atr = vec![f64::NAN; n];
    if n >= lookback {
        let mut sum: f64 = tr.iter().take(lookback).sum();
        atr[lookback - 1] = sum / lookback as f64;
        for i in lookback..n {
            sum += tr[i] - tr[i - lookback];
            atr[i] = sum / lookback as f64;
        }
    }

    // 3-5. Scan for volatility decay
    let mut signal = vec![false; n];
    for t in (lookback - 1)..(n - horizon.0) {
        let delta = atr[t];
        if delta.is_nan() || delta == 0.0 {
            continue;
        }
        
        for h in horizon.0..=horizon.1 {
            let idx = t + h;
            if idx >= n {
                break;
            }
            let future_atr = atr[idx];
            if !future_atr.is_nan() && future_atr < factor * delta {
                signal[t] = true;
                break;
            }
        }
    }
    
    signal
}

// ============================================================================
// Module 2: FVG Asymmetry Detection
// ============================================================================

/// Detects Fair Value Gap (FVG) asymmetry in price action.
/// 
/// # Arguments
/// * `high` - Array of high prices
/// * `low` - Array of low prices
/// * `lookback_min` - Minimum window size for asymmetry calculation
/// * `lookback_max` - Maximum window size for asymmetry calculation
/// * `asym_thresh` - Asymmetry threshold (e.g., 0.3 = 30% difference)
/// 
/// # Returns
/// Boolean vector where true indicates significant FVG asymmetry
pub fn fvg_asymmetry_signal(
    high: &[f64],
    low: &[f64],
    lookback_min: usize,
    lookback_max: usize,
    asym_thresh: f64,
) -> Vec<bool> {
    let n = high.len();
    if n < lookback_min + 2 {
        return vec![false; n];
    }

    // 1-2. Detect FVG gaps
    let mut up = vec![0.0; n];
    let mut down = vec![0.0; n];
    
    for i in 2..n {
        if low[i] > high[i - 2] {
            // Upward FVG (bullish gap)
            up[i] = low[i] - high[i - 2];
        } else if high[i] < low[i - 2] {
            // Downward FVG (bearish gap)
            down[i] = low[i - 2] - high[i];
        }
    }

    // 3-5. Sliding window asymmetry
    let mut signal = vec![false; n];
    let eps = 1e-12;
    
    for start in 0..n {
        for w in lookback_min..=lookback_max {
            let end = start + w;
            if end > n {
                break;
            }
            
            let cup: f64 = up[start..end].iter().sum();
            let cdown: f64 = down[start..end].iter().sum();
            let total = cup + cdown;
            
            if total > eps {
                let asym = (cup - cdown).abs() / total;
                if asym > asym_thresh {
                    // Mark entire window
                    for i in start..end {
                        signal[i] = true;
                    }
                    break;
                }
            }
        }
    }
    
    signal
}

// ============================================================================
// Module 3: Interrupt Scoring
// ============================================================================

/// Computes interrupt score from multiple normalized features.
/// 
/// # Arguments
/// * `features` - Matrix of features (samples × features), each in [0,1]
/// * `weights` - Feature importance weights (sum = 1.0)
/// * `alpha` - EMA smoothing factor (0.0 to 1.0)
/// * `theta` - Interrupt threshold
/// * `event_window` - Window size for max score evaluation
/// 
/// # Returns
/// Boolean vector where true indicates interrupt condition
pub fn interrupt_score_signal(
    features: &Array2<f64>,
    weights: &Array1<f64>,
    alpha: f64,
    theta: f64,
    event_window: usize,
) -> Vec<bool> {
    let n = features.nrows();
    let k = features.ncols();
    assert_eq!(weights.len(), k, "Weights must match feature count");
    
    if n < event_window {
        return vec![false; n];
    }
    
    // 3. Raw weighted score
    let raw = features.dot(weights);
    
    // 4. EMA smoothing
    let mut smoothed = vec![0.0; n];
    smoothed[0] = raw[0];
    for i in 1..n {
        smoothed[i] = alpha * raw[i] + (1.0 - alpha) * smoothed[i - 1];
    }
    
    // 5-6. Event window max > threshold
    let mut signal = vec![false; n];
    for t in (event_window - 1)..n {
        let start = t - event_window + 1;
        let window_max = smoothed[start..=t]
            .iter()
            .fold(f64::NEG_INFINITY, |a, &b| a.max(b));
        
        if window_max > theta {
            signal[t] = true;
        }
    }
    
    signal
}

// ============================================================================
// Module 4: Sensor Fusion
// ============================================================================

/// Fuses multiple sensor streams into a single confidence score.
/// 
/// # Arguments
/// * `sensors` - Matrix of sensor readings (samples × sensors), each in [0,1]
/// * `weights` - Sensor reliability weights (sum = 1.0)
/// * `threshold` - Fusion trigger threshold (default 0.6)
/// 
/// # Returns
/// Boolean vector where true indicates fused score > threshold
pub fn sensor_fusion_signal(
    sensors: &Array2<f64>,
    weights: &Array1<f64>,
    threshold: f64,
) -> Vec<bool> {
    let m = sensors.ncols();
    assert_eq!(weights.len(), m, "Weights must match sensor count");
    
    // 3. Weighted sum
    let fused = sensors.dot(weights);
    
    // 4. Squash with tanh to [0,1]
    let mut signal = Vec::with_capacity(fused.len());
    for &v in fused.iter() {
        let r_score = (v.tanh() + 1.0) / 2.0;
        signal.push(r_score > threshold);
    }
    
    signal
}

// ============================================================================
// Module 5: Overbought (OB) Predictor
// ============================================================================

/// Flags overbought conditions when bar range exceeds ATR multiple.
/// 
/// # Arguments
/// * `high` - Array of high prices
/// * `low` - Array of low prices
/// * `close` - Array of close prices
/// * `lookback` - ATR calculation window
/// * `k` - ATR multiplier threshold
/// * `cooldown` - Minimum bars between signals
/// 
/// # Returns
/// Boolean vector where true indicates overbought condition
pub fn ob_predictor_signal(
    high: &[f64],
    low: &[f64],
    close: &[f64],
    lookback: usize,
    k: f64,
    cooldown: usize,
) -> Vec<bool> {
    let n = close.len();
    if n < lookback {
        return vec![false; n];
    }
    
    // Calculate True Range
    let mut tr = vec![0.0; n];
    for i in 0..n {
        let tr1 = high[i] - low[i];
        let tr2 = if i > 0 { (high[i] - close[i - 1]).abs() } else { 0.0 };
        let tr3 = if i > 0 { (low[i] - close[i - 1]).abs() } else { 0.0 };
        tr[i] = tr1.max(tr2).max(tr3);
    }
    
    // Calculate ATR
    let mut atr = vec![f64::NAN; n];
    let mut sum: f64 = tr.iter().take(lookback).sum();
    atr[lookback - 1] = sum / lookback as f64;
    for i in lookback..n {
        sum += tr[i] - tr[i - lookback];
        atr[i] = sum / lookback as f64;
    }
    
    // Signal with cooldown
    let mut signal = vec![false; n];
    let mut last_signal: isize = -(cooldown as isize + 1);
    
    for t in lookback - 1..n {
        let atr_t = atr[t];
        if atr_t.is_nan() {
            continue;
        }
        
        let range_t = high[t] - low[t];
        let condition = range_t > k * atr_t;
        let cooldown_ok = (t as isize - last_signal) > cooldown as isize;
        
        if condition && cooldown_ok {
            signal[t] = true;
            last_signal = t as isize;
        }
    }
    
    signal
}

// ============================================================================
// Integrated Signal Analysis System
// ============================================================================

/// Market conditions summary for a given bar
#[derive(Debug, Clone, Default)]
pub struct MarketSignals {
    pub volatility_decay: bool,
    pub fvg_asymmetry: bool,
    pub interrupt: bool,
    pub fusion: bool,
    pub overbought: bool,
}

/// Configuration for the integrated system
#[derive(Debug, Clone)]
pub struct SignalConfig {
    // Volatility decay parameters
    pub vol_lookback: usize,
    pub vol_horizon_min: usize,
    pub vol_horizon_max: usize,
    pub vol_factor: f64,
    
    // FVG asymmetry parameters
    pub fvg_lookback_min: usize,
    pub fvg_lookback_max: usize,
    pub fvg_threshold: f64,
    
    // Interrupt scoring parameters
    pub interrupt_alpha: f64,
    pub interrupt_theta: f64,
    pub interrupt_event_window: usize,
    
    // Sensor fusion parameters
    pub fusion_threshold: f64,
    
    // OB predictor parameters
    pub ob_lookback: usize,
    pub ob_k_multiplier: f64,
    pub ob_cooldown: usize,
}

impl Default for SignalConfig {
    fn default() -> Self {
        Self {
            vol_lookback: 14,
            vol_horizon_min: 1,
            vol_horizon_max: 3,
            vol_factor: 0.7,
            fvg_lookback_min: 5,
            fvg_lookback_max: 10,
            fvg_threshold: 0.3,
            interrupt_alpha: 0.2,
            interrupt_theta: 0.6,
            interrupt_event_window: 5,
            fusion_threshold: 0.6,
            ob_lookback: 14,
            ob_k_multiplier: 1.5,
            ob_cooldown: 0,
        }
    }
}

/// Integrated market signal analyzer
pub struct SignalAnalyzer {
    config: SignalConfig,
    // Feature history for interrupt scoring
    feature_history: Vec<Array1<f64>>,
    // Sensor history for fusion
    sensor_history: Vec<Array1<f64>>,
}

impl SignalAnalyzer {
    pub fn new(config: SignalConfig) -> Self {
        Self {
            config,
            feature_history: Vec::new(),
            sensor_history: Vec::new(),
        }
    }
    
    /// Analyze a single bar and return all signals
    pub fn analyze_bar(
        &mut self,
        high: f64,
        low: f64,
        close: f64,
        features: Option<Array1<f64>>,
        sensors: Option<Array1<f64>>,
        history: &PriceHistory,
    ) -> MarketSignals {
        let mut signals = MarketSignals::default();
        
        // Need enough history for meaningful analysis
        if history.len() < self.config.vol_lookback {
            return signals;
        }
        
        // Create temporary arrays for the lookback window
        let n = history.len();
        let high_arr: Vec<f64> = (0..n).map(|i| history.high[i]).collect();
        let low_arr: Vec<f64> = (0..n).map(|i| history.low[i]).collect();
        let close_arr: Vec<f64> = (0..n).map(|i| history.close[i]).collect();
        
        // 1. Volatility decay detection
        let vol_signals = volatility_decay_signal(
            &high_arr, &low_arr, &close_arr,
            self.config.vol_lookback,
            (self.config.vol_horizon_min, self.config.vol_horizon_max),
            self.config.vol_factor,
        );
        signals.volatility_decay = *vol_signals.last().unwrap_or(&false);
        
        // 2. FVG asymmetry detection
        let fvg_signals = fvg_asymmetry_signal(
            &high_arr, &low_arr,
            self.config.fvg_lookback_min,
            self.config.fvg_lookback_max,
            self.config.fvg_threshold,
        );
        signals.fvg_asymmetry = *fvg_signals.last().unwrap_or(&false);
        
        // 3. OB predictor
        let ob_signals = ob_predictor_signal(
            &high_arr, &low_arr, &close_arr,
            self.config.ob_lookback,
            self.config.ob_k_multiplier,
            self.config.ob_cooldown,
        );
        signals.overbought = *ob_signals.last().unwrap_or(&false);
        
        // 4. Interrupt scoring (if features provided)
        if let Some(feat) = features {
            self.feature_history.push(feat);
            if self.feature_history.len() >= self.config.interrupt_event_window {
                let feature_matrix = self.build_feature_matrix();
                let weights = self.get_interrupt_weights();
                let interrupt = interrupt_score_signal(
                    &feature_matrix,
                    &weights,
                    self.config.interrupt_alpha,
                    self.config.interrupt_theta,
                    self.config.interrupt_event_window,
                );
                signals.interrupt = *interrupt.last().unwrap_or(&false);
            }
        }
        
        // 5. Sensor fusion (if sensors provided)
        if let Some(sensor) = sensors {
            self.sensor_history.push(sensor);
            if !self.sensor_history.is_empty() {
                let sensor_matrix = self.build_sensor_matrix();
                let weights = self.get_sensor_weights();
                let fusion = sensor_fusion_signal(
                    &sensor_matrix,
                    &weights,
                    self.config.fusion_threshold,
                );
                signals.fusion = *fusion.last().unwrap_or(&false);
            }
        }
        
        signals
    }
    
    fn build_feature_matrix(&self) -> Array2<f64> {
        let n = self.feature_history.len();
        let k = self.feature_history[0].len();
        let mut matrix = Array2::zeros((n, k));
        
        for (i, feat) in self.feature_history.iter().enumerate() {
            matrix.row_mut(i).assign(feat);
        }
        
        matrix
    }
    
    fn build_sensor_matrix(&self) -> Array2<f64> {
        let n = self.sensor_history.len();
        let m = self.sensor_history[0].len();
        let mut matrix = Array2::zeros((n, m));
        
        for (i, sensor) in self.sensor_history.iter().enumerate() {
            matrix.row_mut(i).assign(sensor);
        }
        
        matrix
    }
    
    fn get_interrupt_weights(&self) -> Array1<f64> {
        // Example weights - should be tuned based on feature importance
        let k = self.feature_history[0].len();
        let weight = 1.0 / k as f64;
        Array1::from_elem(k, weight)
    }
    
    fn get_sensor_weights(&self) -> Array1<f64> {
        // Example weights - should be tuned based on sensor reliability
        let m = self.sensor_history[0].len();
        let weight = 1.0 / m as f64;
        Array1::from_elem(m, weight)
    }
}

/// Historical price data container
#[derive(Debug, Clone)]
pub struct PriceHistory {
    pub high: Vec<f64>,
    pub low: Vec<f64>,
    pub close: Vec<f64>,
    pub open: Vec<f64>,
    pub volume: Vec<f64>,
}

impl PriceHistory {
    pub fn new() -> Self {
        Self {
            high: Vec::new(),
            low: Vec::new(),
            close: Vec::new(),
            open: Vec::new(),
            volume: Vec::new(),
        }
    }
    
    pub fn push(&mut self, open: f64, high: f64, low: f64, close: f64, volume: f64) {
        self.open.push(open);
        self.high.push(high);
        self.low.push(low);
        self.close.push(close);
        self.volume.push(volume);
    }
    
    pub fn len(&self) -> usize {
        self.close.len()
    }
    
    pub fn is_empty(&self) -> bool {
        self.close.is_empty()
    }
}

// ============================================================================
// Example Usage
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use approx::assert_relative_eq;
    
    #[test]
    fn test_volatility_decay() {
        let high = vec![10.0, 11.0, 12.0, 11.5, 10.5, 10.0, 9.5];
        let low = vec![9.0, 10.0, 11.0, 10.5, 9.5, 9.0, 8.5];
        let close = vec![9.5, 10.5, 11.5, 11.0, 10.0, 9.5, 9.0];
        
        let signals = volatility_decay_signal(&high, &low, &close, 3, (1, 2), 0.7);
        println!("Volatility decay signals: {:?}", signals);
    }
    
    #[test]
    fn test_fvg_asymmetry() {
        let high = vec![10.0, 11.0, 10.5, 12.0, 11.5, 11.0];
        let low = vec![9.0, 9.5, 9.0, 10.0, 10.5, 10.0];
        
        let signals = fvg_asymmetry_signal(&high, &low, 2, 4, 0.3);
        println!("FVG asymmetry signals: {:?}", signals);
    }
    
    #[test]
    fn test_interrupt_scoring() {
        let features = Array2::from_shape_vec((10, 3), vec![
            0.5, 0.6, 0.7,
            0.6, 0.7, 0.8,
            0.7, 0.8, 0.9,
            0.8, 0.9, 1.0,
            0.7, 0.8, 0.9,
            0.6, 0.7, 0.8,
            0.5, 0.6, 0.7,
            0.4, 0.5, 0.6,
            0.3, 0.4, 0.5,
            0.2, 0.3, 0.4,
        ]).unwrap();
        let weights = Array1::from_vec(vec![0.3, 0.3, 0.4]);
        
        let signals = interrupt_score_signal(&features, &weights, 0.2, 0.6, 3);
        println!("Interrupt signals: {:?}", signals);
    }
    
    #[test]
    fn test_sensor_fusion() {
        let sensors = Array2::from_shape_vec((10, 2), vec![
            0.1, 0.2,
            0.2, 0.3,
            0.3, 0.4,
            0.4, 0.5,
            0.5, 0.6,
            0.6, 0.7,
            0.7, 0.8,
            0.8, 0.9,
            0.9, 1.0,
            1.0, 1.0,
        ]).unwrap();
        let weights = Array1::from_vec(vec![0.5, 0.5]);
        
        let signals = sensor_fusion_signal(&sensors, &weights, 0.6);
        println!("Sensor fusion signals: {:?}", signals);
    }
    
    #[test]
    fn test_ob_predictor() {
        let high = vec![10.0, 11.0, 12.0, 13.0, 12.5, 12.0, 11.5];
        let low = vec![9.0, 10.0, 11.0, 12.0, 11.5, 11.0, 10.5];
        let close = vec![9.5, 10.5, 11.5, 12.5, 12.0, 11.5, 11.0];
        
        let signals = ob_predictor_signal(&high, &low, &close, 3, 1.5, 1);
        println!("OB predictor signals: {:?}", signals);
    }
    
    #[test]
    fn test_integrated_analyzer() {
        let mut history = PriceHistory::new();
        let config = SignalConfig::default();
        let mut analyzer = SignalAnalyzer::new(config);
        
        // Simulate price data
        let mut features = vec![0.5, 0.6, 0.7];
        let mut sensors = vec![0.4, 0.5];
        
        for i in 0..20 {
            let high = 100.0 + (i as f64) * 0.5;
            let low = 99.0 + (i as f64) * 0.5;
            let close = 99.5 + (i as f64) * 0.5;
            
            history.push(close, high, low, close, 1000.0);
            
            // Update features and sensors
            features = vec![0.5 + (i as f64) * 0.02, 0.6 + (i as f64) * 0.01, 0.7];
            sensors = vec![0.4 + (i as f64) * 0.03, 0.5 + (i as f64) * 0.02];
            
            let signals = analyzer.analyze_bar(
                high, low, close,
                Some(Array1::from_vec(features.clone())),
                Some(Array1::from_vec(sensors.clone())),
                &history,
            );
            
            if i >= 14 {
                println!("Bar {}: {:?}", i, signals);
            }
        }
    }
}
