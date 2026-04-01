// use ndarray::Array1;
// use src::hidden_engine::soul_force;

// fn test_soul_force_linear() {
//     let ptr = Array1::from_vec(vec![0.0, 1.0, 2.0]);
//     let eq = 1.0;
//     let G = 2.0;
//     // F = -G * (ptr - eq) => [-2, 0, 2]
//     let expected = -G * (&ptr - eq);
//     assert!((soul_force(&ptr, eq, G) - expected).iter().all(|x| x.abs() < 1e-10));
// }
