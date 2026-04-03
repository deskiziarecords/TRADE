// Import necessary libraries
import * as THREE from 'three';

// Function to compute FFT and detect phase inversion
function spectralPhaseInversion(prices, windowSize = 64) {
    const fftResults = [];
    const phaseInversions = [];
    
    for (let i = 0; i < prices.length - windowSize; i++) {
        const window = prices.slice(i, i + windowSize);
        const fftResult = new FFT(windowSize).forward(window);
        const dominantFreq = fftResult.map((_, index) => index * (1 / windowSize)).slice(0, windowSize / 2);
        const dominantAmplitude = fftResult.map(Math.abs).slice(0, windowSize / 2);
        
        // Detect dominant frequency
        const fStar = dominantFreq[dominantAmplitude.indexOf(Math.max(...dominantAmplitude))];
        const phaseAngle = Math.atan2(fftResult[dominantAmplitude.indexOf(Math.max(...dominantAmplitude))].imag, 
                                         fftResult[dominantAmplitude.indexOf(Math.max(...dominantAmplitude))].real);
        
        // Check for phase inversion condition
        if (Math.abs(phaseAngle) > Math.PI / 2) {
            phaseInversions.push(i + Math.floor(windowSize / 2));
        }
        
        fftResults.push({ fStar, phaseAngle });
    }
    
    return { fftResults, phaseInversions };
}

// Sample price data (replace with actual price data)
const prices = Array.from({ length: 1000 }, () => Math.random());  // Simulated price data

// Run the spectral phase inversion detection
const { fftResults, phaseInversions } = spectralPhaseInversion(prices);

// Visualization using three.js
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer();
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// Create a line for price data
const priceGeometry = new THREE.BufferGeometry();
const priceVertices = new Float32Array(prices);
priceGeometry.setAttribute('position', new THREE.BufferAttribute(priceVertices, 3));
const priceMaterial = new THREE.LineBasicMaterial({ color: 0x0000ff });
const priceLine = new THREE.Line(priceGeometry, priceMaterial);
scene.add(priceLine);

// Add phase inversion markers
phaseInversions.forEach(inversion => {
    const markerGeometry = new THREE.SphereGeometry(0.1, 32, 32);
    const markerMaterial = new THREE.MeshBasicMaterial({ color: 0xff0000 });
    const marker = new THREE.Mesh(markerGeometry, markerMaterial);
    marker.position.set(inversion, prices[inversion], 0);
    scene.add(marker);
});

// Set camera position
camera.position.z = 5;

// Animation loop
function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}
animate();
