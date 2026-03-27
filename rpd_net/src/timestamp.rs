//! NIC hardware timestamping for latency measurement
//! Intel i40e/ixgbe: PTP/IEEE 1588 support

use std::os::unix::io::RawFd;

/// Enable hardware timestamping on socket
pub fn enable_hw_timestamp(fd: RawFd) -> std::io::Result<()> {
    let flags: libc::c_int = libc::SOF_TIMESTAMPING_RAW_HARDWARE
        | libc::SOF_TIMESTAMPING_RX_SOFTWARE
        | libc::SOF_TIMESTAMPING_TX_SOFTWARE
        | libc::SOF_TIMESTAMPING_SOFTWARE;
    
    let opt: libc::c_int = 1;
    
    unsafe {
        let ret = libc::setsockopt(
            fd,
            libc::SOL_SOCKET,
            libc::SO_TIMESTAMPING,
            &flags as *const _ as *const libc::c_void,
            std::mem::size_of_val(&flags) as libc::socklen_t,
        );
        
        if ret < 0 {
            return Err(std::io::Error::last_os_error());
        }
    }
    
    Ok(())
}

/// Extract hardware timestamp from cmsg
pub fn extract_hw_timestamp(cmsg: &[u8]) -> Option<u64> {
    // Parse SCM_TIMESTAMPING cmsg
    // Returns nanoseconds since epoch
    unimplemented!("Parse kernel timestamp cmsg")
}
