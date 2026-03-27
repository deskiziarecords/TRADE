//! Simple Open Framing Header (FIXP) for binary FIX
//! 6-byte header: [2-byte length][2-byte encoding][2-byte block]

use byteorder::{BigEndian, ByteOrder};

pub const SOFH_LEN: usize = 6;

#[repr(C, packed)]
pub struct SofHeader {
    pub message_length: u16,    // Big-endian, includes SOFH
    pub encoding_type: u16,     // 0x0001 = FIX binary
    pub block_length: u16,      // Length of first block
}

impl SofHeader {
    #[inline(always)]
    pub fn encode(&self, buf: &mut [u8]) {
        BigEndian::write_u16(&mut buf[0..2], self.message_length);
        BigEndian::write_u16(&mut buf[2..4], self.encoding_type);
        BigEndian::write_u16(&mut buf[4..6], self.block_length);
    }
    
    #[inline(always)]
    pub fn decode(buf: &[u8]) -> Self {
        Self {
            message_length: BigEndian::read_u16(&buf[0..2]),
            encoding_type: BigEndian::read_u16(&buf[2..4]),
            block_length: BigEndian::read_u16(&buf[4..6]),
        }
    }
}
