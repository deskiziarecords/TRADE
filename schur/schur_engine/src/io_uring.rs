//! Kernel-bypass execution submission
//! Sub-μs latency for venue orders

use io_uring::{IoUring, opcode, types};
use std::os::unix::io::RawFd;
use std::net::TcpStream;
use std::io::{self, Write};

/// Execution order for single venue
#[repr(C, packed)]
pub struct ExecutionOrder {
    pub venue_id: u32,
    pub quantity: f64,      // Scaled to fixed-point
    pub price_limit: f64,
    pub flags: u32,         // IOC, FOK, etc.
}

/// Submit batch via io_uring
pub fn submit_orders_uring(
    ring: &mut IoUring,
    orders: &[ExecutionOrder],
    sockets: &[RawFd],
) -> io::Result<usize> {
    let mut submitted = 0;
    
    for (i, order) in orders.iter().enumerate() {
        if i >= sockets.len() {
            break;
        }
        
        // Serialize order to wire format (FIX binary or proprietary)
        let buf = serialize_order(order);
        
        // Build SQE
        let sqe = opcode::Write::new(
            types::Fd(sockets[i]),
            buf.as_ptr(),
            buf.len() as u32,
        )
        .build();
        
        unsafe {
            ring.submission()
                .push(&sqe)
                .map_err(|_| io::Error::new(io::ErrorKind::Other, "SQ full"))?;
        }
        
        submitted += 1;
    }
    
    // Submit batch
    ring.submit()?;
    
    Ok(submitted)
}

/// Serialize to venue-specific format
fn serialize_order(order: &ExecutionOrder) -> Vec<u8> {
    // Placeholder: actual implementation venue-specific
    // Could be FIX, SBE, or proprietary binary
    
    let mut buf = Vec::with_capacity(64);
    buf.extend_from_slice(&order.venue_id.to_le_bytes());
    buf.extend_from_slice(&order.quantity.to_le_bytes());
    buf.extend_from_slice(&order.price_limit.to_le_bytes());
    buf.extend_from_slice(&order.flags.to_le_bytes());
    buf
}

/// Fallback: standard synchronous write
pub fn submit_orders_sync(
    orders: &[ExecutionOrder],
    streams: &mut [TcpStream],
) -> io::Result<usize> {
    for (i, order) in orders.iter().enumerate() {
        if i >= streams.len() {
            break;
        }
        
        let buf = serialize_order(order);
        streams[i].write_all(&buf)?;
        streams[i].flush()?;
    }
    
    Ok(orders.len().min(streams.len()))
}
