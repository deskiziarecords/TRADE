// Import necessary libraries
// import * as THREE from 'three';
// import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// Define the OBNFE class
class OBNFE {
    constructor(priceData) {
        this.priceData = priceData;
        this.atrPeriod = 20;
    }

    calculateATR() {
        const highLow = this.priceData.map(data => data.High - data.Low);
        const highClose = this.priceData.map((data, index) => index === 0 ? 0 : Math.abs(data.High - this.priceData[index - 1].Close));
        const lowClose = this.priceData.map((data, index) => index === 0 ? 0 : Math.abs(data.Low - this.priceData[index - 1].Close));
        const tr = highLow.map((value, index) => Math.max(value, highClose[index], lowClose[index]));
        const atr = this.rollingMean(tr, this.atrPeriod);
        return atr;
    }

    rollingMean(data, window) {
        const result = [];
        for (let i = 0; i < data.length; i++) {
            if (i < window - 1) {
                result.push(null);
            } else {
                const mean = data.slice(i - window + 1, i + 1).reduce((a, b) => a + b, 0) / window;
                result.push(mean);
            }
        }
        return result;
    }

    lambdaSensor1() {
        this.priceData.forEach(data => {
            data.σt = 2; // Assuming we are in a distribution phase
        });
        let τstay = 0;
        this.priceData.forEach((data, index) => {
            if (data.σt === 2) {
                τstay++;
            }
            data.τstay = τstay;
        });
        this.priceData.forEach((data, index) => {
            data.Vt = index < this.priceData.length - 1 ? this.calculateStdDev(this.priceData.slice(index - data.τstay + 1, index + 1)) : null;
            data.ATR = this.calculateATR()[index];
            const δ = 0.5; // Example threshold
            data.Phase_Entrapment = (data.τstay > 10) && (data.Vt / data.ATR < δ);
        });
    }

    calculateStdDev(data) {
        const mean = data.reduce((a, b) => a + b.Close, 0) / data.length;
        const variance = data.reduce((a, b) => a + Math.pow(b.Close - mean, 2), 0) / data.length;
        return Math.sqrt(variance);
    }

    lambdaSensor2() {
        this.priceData.forEach((data, index) => {
            data.Killzone = (new Date(data.time).getHours() === 8 || new Date(data.time).getHours() === 9) ? 1 : 0;
        });
        this.priceData.forEach((data, index) => {
            if (index > 0) {
                data.Directional_Sum = this.priceData.slice(index - 20, index).map(d => d.Close).reduce((a, b) => a + Math.sign(b - this.priceData[index - 1].Close), 0);
            }
            const γ = 0.45; // Example threshold
            data.Temporal_Failure = (data.Killzone === 1) && (data.Directional_Sum < γ);
        });
    }

    visualize() {
        // Create a scene
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer();
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);

        // Create a scatter plot
        const geometry = new THREE.BufferGeometry();
        const positions = [];
        this.priceData.forEach(data => {
            positions.push(data.time, data.Close, data.Phase_Entrapment);
        });
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

        const material = new THREE.PointsMaterial({ color: 0xff0000 });
        const points = new THREE.Points(geometry, material);
        scene.add(points);

        camera.position.z = 5;

        const animate = function () {
            requestAnimationFrame(animate);
            renderer.render(scene, camera);
        };
        animate();
    }
}

// Example usage
const priceData = Array.from({ length: 100 }, (_, index) => ({
    time: new Date(Date.now() + index * 3600000).toISOString(),
    High: Math.random() * 100,
    Low: Math.random() * 100,
    Close: Math.random() * 100
}));

const obnfe = new OBNFE(priceData);
obnfe.lambdaSensor1();
obnfe.lambdaSensor2();
obnfe.visualize();
