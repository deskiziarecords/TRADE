// λ1: Phase Entrapment (State Persistence Failure)
// What it detects:

// Price is "stuck" in a Distribution phase (σt=2) without meaningful directional movement, suggesting a breakdown in trend continuity.
// Mathematical Conditions:

// Phase Requirement: σt = 2 (Distribution phase, e.g., range-bound or consolidation).
// Time Parameter: τstay(t) > τmax (price spends too long in this phase).

// Volatility Parameter: Vt / ATR20 < δ (price variation is abnormally low relative to ATR).
// Forex Relevance:

// Detects liquidity traps or institutional accumulation/distribution zones (e.g., before a breakout).
// Useful for mean reversion or breakout strategies.

const σt = 2;  // Distribution phase
const τmax = 10;  // Maximum time in phase
const δ = 0.5;  // Volatility threshold
const ATR_period = 20;  // ATR calculation period

// Sample price data
const price_data = Array.from({length: 100}, () => Math.random() * 2 + 99); // Simulating price data
const price_series = price_data;

// Calculate ATR
function calculate_atr(prices, period) {
    const high = [];
    const low = [];
    const tr = [];
    const atr = [];

    for (let i = 0; i < prices.length; i++) {
        if (i >= period - 1) {
            high.push(Math.max(...prices.slice(i - period + 1, i + 1)));
            low.push(Math.min(...prices.slice(i - period + 1, i + 1)));
            tr.push(high[high.length - 1] - low[low.length - 1]);
            atr.push(tr.reduce((a, b) => a + b, 0) / period);
        }
    }
    return atr;
}

const ATR = calculate_atr(price_series, ATR_period);

// Phase detection
function detect_phase(prices) {
    const phase = [];
    for (let i = 0; i < prices.length; i++) {
        if (i < 1) {
            phase.push(0);
        } else {
            if (prices[i] === prices[i - 1]) {
                phase.push(σt);
            } else {
                phase.push(0);
            }
        }
    }
    return phase;
}

const phase_series = detect_phase(price_series);

// Calculate τstay(t)
function calculate_tau_stay(phase_series) {
    let tau_stay = 0;
    for (const phase of phase_series) {
        if (phase === σt) {
            tau_stay += 1;
        } else {
            tau_stay = 0;
        }
    }
    return tau_stay;
}

const τstay = calculate_tau_stay(phase_series);

// Calculate Vt
function calculate_volatility(prices, τstay) {
    if (τstay > 0) {
        const recent_prices = prices.slice(-τstay);
        const mean = recent_prices.reduce((a, b) => a + b, 0) / recent_prices.length;
        const variance = recent_prices.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / recent_prices.length;
        return Math.sqrt(variance);
    }
    return 0;
}

const Vt = calculate_volatility(price_series, τstay);

// Visualization using three.js
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer();
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

const geometry = new THREE.BoxGeometry(1, 1, 1);
const material = new THREE.MeshBasicMaterial({ color: τstay > τmax && Vt / ATR[ATR.length - 1] < δ ? 0xff0000 : 0x00ff00 });

for (let i = 0; i < price_series.length; i++) {
    const cube = new THREE.Mesh(geometry, material);
    cube.position.set(i, price_series[i], 0);
    scene.add(cube);
}

camera.position.z = 50;

function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}

animate();
