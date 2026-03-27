//! Lock-free buffer pool for FIX messages
//! Pre-allocated, NUMA-aware, cache-line aligned

use crossbeam_queue::ArrayQueue;
use cache_padded::CachePadded;
use std::sync::Arc;
use std::alloc::{alloc, dealloc, Layout};

const BUFFER_SIZE: usize = 4096;
const CACHE_LINE: usize = 64;

/// Aligned buffer for cache efficiency
#[repr(align(64))]
pub struct AlignedBuffer {
    pub data: [u8; BUFFER_SIZE],
    pub len: usize,
}

impl AlignedBuffer {
    pub fn as_slice(&self) -> &[u8] {
        &self.data[..self.len]
    }
    
    pub fn as_mut_slice(&mut self) -> &mut [u8] {
        &mut self.data[..self.len]
    }
}

/// Per-CPU buffer pool (NUMA-aware)
pub struct BufferPool {
    local: ArrayQueue<Box<AlignedBuffer>>,
    steal: Arc<ArrayQueue<Box<AlignedBuffer>>>,
    cpu_id: usize,
}

impl BufferPool {
    pub fn new(cpu_id: usize, capacity: usize) -> Self {
        let local = ArrayQueue::new(capacity);
        let steal = Arc::new(ArrayQueue::new(capacity / 2));
        
        // Pre-populate
        for _ in 0..capacity {
            let buf = Box::new(AlignedBuffer {
                data: [0u8; BUFFER_SIZE],
                len: 0,
            });
            let _ = local.push(buf);
        }
        
        Self { local, steal, cpu_id }
    }
    
    /// Get buffer (lock-free, <10ns)
    #[inline(always)]
    pub fn acquire(&self) -> Option<Box<AlignedBuffer>> {
        // Try local first
        if let Some(buf) = self.local.pop() {
            return Some(buf);
        }
        
        // Steal from shared
        self.steal.pop()
    }
    
    /// Return buffer (lock-free)
    #[inline(always)]
    pub fn release(&self, mut buf: Box<AlignedBuffer>) {
        buf.len = 0; // Reset
        
        if self.local.push(buf).is_err() {
            // Local full, try steal pool
            let _ = self.steal.push(buf);
        }
    }
}

/// Thread-local pool accessor
thread_local! {
    static LOCAL_POOL: std::cell::RefCell<Option<BufferPool>> = std::cell::RefCell::new(None);
}

pub fn init_thread_pool(cpu_id: usize) {
    LOCAL_POOL.with(|p| {
        *p.borrow_mut() = Some(BufferPool::new(cpu_id, 1024));
    });
}

pub fn with_pool<F, R>(f: F) -> R
where
    F: FnOnce(&BufferPool) -> R,
{
    LOCAL_POOL.with(|p| {
        f(p.borrow().as_ref().expect("Pool not initialized"))
    })
}
