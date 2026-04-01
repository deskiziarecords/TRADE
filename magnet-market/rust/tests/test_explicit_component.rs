// use rand::Rng;
// use crate::src::explicit_component::body_signal;

// #[cfg(test)]
// mod tests {
//     use super::*;

//     #[test]
//     fn test_body_signal_shape() {
//         let mut rng = rand::thread_rng();
//         let prices: Vec<f64> = (0..100).map(|_| rng.gen()).collect();
//         let out = body_signal(&prices, 0.02);
//         assert_eq!(out.len(), prices.len());
//     }

//     #[test]
//     fn test_body_signal_monotonic_decay() {
//         // With constant price, output should follow decay weights
//         let prices: Vec<f64> = vec![1.0; 50];
//         let out = body_signal(&prices, 0.1);
//         let expected: Vec<f64> = (0..50).rev().map(|x| (-(0.1 * x as f64)).exp()).collect();
//         assert!((out.iter().zip(expected.iter()).all(|(a, b)| (a - b).abs() < 1e-6)));
//     }
// }
