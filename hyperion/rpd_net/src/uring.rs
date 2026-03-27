//! io_uring setup with SQPOLL and IOPOLL for zero-syscall I/O

use io_uring::{IoUring, Submitter, CompletionQueue, SubmissionQueue};
use io_uring::types::{Fd, Timespec};
use io_uring::opcode;
use std::os::unix::io::RawFd;
use std::sync::Arc;
use std::sync::atomic::{AtomicU32, Ordering};

/// Ring configuration for trading
pub struct UringConfig {
    pub sq_entries: u32,        // Submission queue size (4096)
    pub cq_entries: u32,        // Completion queue size (8192)
    pub sqpoll_idle: u32,       // SQPOLL idle timeout ms (0 = never)
    pub iopoll: bool,           // Busy-wait completions (no IRQ)
    pub cq_entries_flags: u32,  // CQ overflow handling
}

impl Default for UringConfig {
    fn default() -> Self {
        Self {
            sq_entries: 4096,
            cq_entries: 8192,
            sqpoll_idle: 0,     // Kernel thread never sleeps
            iopoll: true,       // Busy-poll for <1μs latency
            cq_entries_flags: 0,
        }
    }
}

/// Thread-safe io_uring handle with completion tracking
pub struct TradingUring {
    ring: IoUring,
    sq: SubmissionQueue,
    cq: CompletionQueue,
    pending: Arc<AtomicU32>,  // In-flight operations
}

impl TradingUring {
    pub fn new(config: UringConfig) -> std::io::Result<Self> {
        let mut builder = IoUring::builder();
        
        // SQPOLL: Kernel thread polls submission queue
        // No syscall needed for submit
        if config.sqpoll_idle > 0 {
            builder = builder.setup_sqpoll(config.sqpoll_idle);
        }
        
        // IOPOLL: Busy-wait completions, no interrupts
        if config.iopoll {
            builder = builder.setup_iopoll();
        }
        
        // Single issuer: optimize for single-thread submit
        builder = builder.setup_single_issuer();
        
        // COOP_TASKRUN: Reduce wakeups
        builder = builder.setup_coop_taskrun();
        
        let ring = builder.build(config.sq_entries)?;
        
        Ok(Self {
            sq: unsafe { std::mem::zeroed() }, // Placeholder
            cq: unsafe { std::mem::zeroed() },
            ring,
            pending: Arc::new(AtomicU32::new(0)),
        })
    }
    
    /// Submit without syscall (SQPOLL) or minimal syscall
    #[inline(always)]
    pub fn submit(&mut self) -> std::io::Result<usize> {
        // With SQPOLL: just memory barrier, no enter()
        // Without: io_uring_enter() syscall
        let ret = self.ring.submit();
        
        if let Ok(n) = ret {
            self.pending.fetch_add(n as u32, Ordering::Relaxed);
        }
        
        ret
    }
    
    /// Poll completions without blocking (IOPOLL)
    #[inline(always)]
    pub fn poll_completions<F>(&mut self, mut f: F) -> usize
    where
        F: FnMut(io_uring::cqueue::Entry),
    {
        let mut count = 0;
        
        // IOPOLL: Spin until completions available
        loop {
            match self.ring.completion().next() {
                Some(cqe) => {
                    self.pending.fetch_sub(1, Ordering::Relaxed);
                    f(cqe);
                    count += 1;
                    
                    // Batch limit: yield after 32 completions
                    if count >= 32 {
                        break;
                    }
                }
                None => {
                    // IOPOLL: busy-wait, no sleep
                    // Could add pause instruction here
                    std::hint::spin_loop();
                    break;
                }
            }
        }
        
        count
    }
    
    /// Blocking wait with timeout (for rare cases)
    pub fn wait_completions<F>(&mut self, timeout_us: u64, mut f: F) -> usize
    where
        F: FnMut(io_uring::cqueue::Entry),
    {
        if timeout_us == 0 {
            return self.poll_completions(f);
        }
        
        let ts = Timespec::new()
            .sec((timeout_us / 1_000_000) as i64)
            .nsec(((timeout_us % 1_000_000) * 1000) as u32);
        
        let mut count = 0;
        
        // Enter with timeout
        let _ = self.ring.submitter().submit_and_wait(1);
        
        while let Some(cqe) = self.ring.completion().next() {
            self.pending.fetch_sub(1, Ordering::Relaxed);
            f(cqe);
            count += 1;
        }
        
        count
    }
    
    /// Get in-flight count
    #[inline]
    pub fn pending(&self) -> u32 {
        self.pending.load(Ordering::Relaxed)
    }
}

/// Per-socket registered buffers for zero-copy
pub struct RegisteredBuffers {
    pub bid: u16,           // Buffer group ID
    pub buffers: Vec<Vec<u8>>,
    pub size: usize,      // Per-buffer size (4096 typical)
    pub count: usize,     // Number of buffers (1024 typical)
}

impl RegisteredBuffers {
    pub fn new(bid: u16, size: usize, count: usize) -> Self {
        let buffers = (0..count)
            .map(|_| vec![0u8; size])
            .collect();
        
        Self { bid, buffers, size, count }
    }
    
    /// Register with io_uring for kernel-managed buffers
    pub fn register(&self, ring: &mut IoUring) -> std::io::Result<()> {
        let iovecs: Vec<_> = self.buffers
            .iter()
            .map(|b| libc::iovec {
                iov_base: b.as_ptr() as *mut _,
                iov_len: b.len(),
            })
            .collect();
        
        ring.submitter().register_buffers(&iovecs)?;
        
        Ok(())
    }
}
