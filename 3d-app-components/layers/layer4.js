// Import necessary libraries
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// TradingModel class definition
class TradingModel {
    constructor(confidenceScores, returns) {
        this.confidenceScores = confidenceScores;
        this.returns = returns;
    }

    detectConfluenceCollapse() {
        const highConfidence = this.confidenceScores.map(score => score > 0.6);
        const negativeExpectancy = this.mean(this.returns.filter((_, index) => highConfidence[index])) < 0;
        return [highConfidence, negativeExpectancy];
    }

    mean(array) {
        return array.reduce((a, b) => a + b, 0) / array.length;
    }

    visualizeConfluenceZones() {
        const [highConfidence, negativeExpectancy] = this.detectConfluenceCollapse();
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer();
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);

        const geometry = new THREE.PlaneGeometry(10, 10, 100, 100);
        const material = new THREE.MeshBasicMaterial({ color: negativeExpectancy ? 0xff0000 : 0x00ff00, side: THREE.DoubleSide });
        const plane = new THREE.Mesh(geometry, material);
        scene.add(plane);

        // Create a grid of points for the surface
        const x = Array.from({ length: 100 }, (_, i) => -5 + (i * 10 / 99));
        const y = Array.from({ length: 100 }, (_, i) => -5 + (i * 10 / 99));
        const z = x.map(xVal => y.map(yVal => Math.exp(-0.1 * (xVal ** 2 + yVal ** 2))));

        // Create a surface from the points
        const surfaceGeometry = new THREE.BufferGeometry();
        const vertices = [];
        for (let i = 0; i < x.length; i++) {
            for (let j = 0; j < y.length; j++) {
                vertices.push(x[i], y[j], z[i][j]);
            }
        }
        surfaceGeometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
        const surfaceMaterial = new THREE.MeshBasicMaterial({ color: negativeExpectancy ? 0xff0000 : 0x00ff00, wireframe: false });
        const surfaceMesh = new THREE.Mesh(surfaceGeometry, surfaceMaterial);
        scene.add(surfaceMesh);

        camera.position.z = 5;

        const controls = new OrbitControls(camera, renderer.domElement);
        const animate = function () {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        };
        animate();
    }
}

// Example usage
const confidenceScores = Array.from({ length: 100 }, () => Math.random());  // Simulated confidence scores
const returns = Array.from({ length: 100 }, () => Math.random() * 2 - 1);  // Simulated returns
const model = new TradingModel(confidenceScores, returns);
model.visualizeConfluenceZones();
