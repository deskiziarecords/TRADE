//! TCP/UDP sockets with io_uring fast paths

use io_uring::opcode;
use io_uring::types::Fd;
use std::net::SocketAddr;
use std::os::unix::io::{AsRawFd, RawFd};

/// Fast TCP socket with registered buffers
pub struct FastTcp {
    fd: RawFd,
    registered_buf: Option<u16>, // Buffer group ID
}

impl FastTcp {
    pub fn new(fd: RawFd) -> Self {
        Self { fd, registered_buf: None }
    }
    
    pub fn set_registered_buffer(&mut self, bid: u16) {
        self.registered_buf = Some(bid);
    }
    
    /// Build io_uring SQE for send with registered buffer
    #[inline]
    pub fn send_sqe(&self, buf_index: u16, len: u32, flags: u8) -> opcode::Send {
        let mut sqe = opcode::Send::new(Fd(self.fd), std::ptr::null(), len);
        
        if let Some(bid) = self.registered_buf {
            // Use registered buffer: no copy, kernel knows address
            sqe = sqe.buf_index(buf_index);
        }
        
        sqe.flags(flags) // IOSQE_CQE_SKIP_SUCCESS for fire-and-forget
    }
    
    /// Build io_uring SQE for recv with registered buffer
    #[inline]
    pub fn recv_sqe(&self, buf_index: u16, len: u32) -> opcode::Recv {
        let mut sqe = opcode::Recv::new(Fd(self.fd), std::ptr::null_mut(), len);
        
        if let Some(bid) = self.registered_buf {
            sqe = sqe.buf_index(buf_index);
        }
        
        sqe
    }
    
    /// Connect with fast timeout
    #[inline]
    pub fn connect_sqe(&self, addr: &SocketAddr) -> opcode::Connect {
        let (addr_ptr, addr_len) = socket_addr_to_raw(addr);
        opcode::Connect::new(Fd(self.fd), addr_ptr, addr_len)
    }
    
    /// Enable kernel TLS (kTLS) for FIX encryption offload
    pub fn enable_ktls(&self) -> std::io::Result<()> {
        // TLS 1.3 offload to kernel (Linux 5.10+)
        // Reduces userspace crypto latency
        unimplemented!("kTLS setup")
    }
}

fn socket_addr_to_raw(addr: &SocketAddr) -> (*const libc::sockaddr, libc::socklen_t) {
    match addr {
        SocketAddr::V4(v4) => {
            let raw: libc::sockaddr_in = unsafe { std::mem::transmute(*v4) };
            (&raw as *const _ as *const libc::sockaddr, std::mem::size_of_val(&raw) as _)
        }
        SocketAddr::V6(v6) => {
            let raw: libc::sockaddr_in6 = unsafe { std::mem::transmute(*v6) };
            (&raw as *const _ as *const libc::sockaddr, std::mem::size_of_val(&raw) as _)
        }
    }
}
