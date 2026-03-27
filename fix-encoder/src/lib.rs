//! FIX Encoder for RPD Trading System
//! Sub-microsecond encoding for NewOrderSingle, ExecutionReport

pub mod message;
pub mod encoder;
pub mod decoder;
pub mod checksum;
pub mod sofh;

pub use message::*;
pub use encoder::FixEncoder;
pub use sofh::{SofHeader, SOFH_LEN};

/// Encode order with venue-specific optimizations
pub fn encode_order_venue(
    order: &NewOrderSingle,
    venue_id: u32,
    encoder: &mut FixEncoder,
) -> &[u8] {
    // Venue-specific tag ordering for cache efficiency
    match venue_id {
        0 => encode_oanda(order, encoder),      // Oanda: specific tag order
        1 => encode_interactive_brokers(order, encoder),
        2 => encode_lmax(order, encoder),
        _ => encoder.encode_new_order_single(order), // Generic
    }
}

fn encode_oanda(order: &NewOrderSingle, enc: &mut FixEncoder) -> &[u8] {
    // Oanda-optimized: minimal tags, specific ordering
    enc.reset();
    
    // Oanda uses FIX.4.4 subset
    enc.append_raw(b"8=FIX.4.4\x01");
    
    // ... optimized sequence ...
    
    enc.as_slice()
}

fn encode_interactive_brokers(_order: &NewOrderSingle, _enc: &mut FixEncoder) -> &[u8] {
    unimplemented!()
}

fn encode_lmax(_order: &NewOrderSingle, _enc: &mut FixEncoder) -> &[u8] {
    unimplemented!()
}
