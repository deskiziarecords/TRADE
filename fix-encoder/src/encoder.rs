//! Zero-copy FIX encoder
//! Pre-allocated buffers, SIMD checksums, no heap

use crate::message::*;
use crate::checksum::crc32_fix;
use byteorder::{ByteOrder, BigEndian, LittleEndian};
use std::simd::{Simd, SimdUint};

/// Encoder with reusable buffer
pub struct FixEncoder<const BUF_SIZE: usize = 4096> {
    buffer: [u8; BUF_SIZE],
    position: usize,
    msg_seq_num: u32,
    sender_comp_id: [u8; 32],
    sender_comp_id_len: u8,
    target_comp_id: [u8; 32],
    target_comp_id_len: u8,
}

impl<const N: usize> FixEncoder<N> {
    pub fn new(sender: &str, target: &str) -> Self {
        let mut encoder = Self {
            buffer: [0u8; N],
            position: 0,
            msg_seq_num: 1,
            sender_comp_id: [0u8; 32],
            sender_comp_id_len: sender.len() as u8,
            target_comp_id: [0u8; 32],
            target_comp_id_len: target.len() as u8,
        };
        
        // Pre-fill comp IDs
        encoder.sender_comp_id[..sender.len()].copy_from_slice(sender.as_bytes());
        encoder.target_comp_id[..target.len()].copy_from_slice(target.as_bytes());
        
        encoder
    }
    
    /// Reset buffer position (reuse allocation)
    #[inline(always)]
    pub fn reset(&mut self) {
        self.position = 0;
    }
    
    /// Get encoded message as slice
    #[inline(always)]
    pub fn as_slice(&self) -> &[u8] {
        &self.buffer[..self.position]
    }
    
    /// Encode NewOrderSingle to FIX.5.0SP2
    /// Format: 8=FIXT.1.1|9=...|35=D|...|10=XXX|
    pub fn encode_new_order_single(&mut self, order: &NewOrderSingle) -> &[u8] {
        self.reset();
        
        // BeginString (8)
        self.append_tag_value(8, b"FIXT.1.1");
        
        // BodyLength placeholder (9=00000|)
        let body_len_pos = self.position + 3; // After "9="
        self.append_raw(b"9=00000|");
        
        // MsgType (35=D)
        self.append_tag_value(35, b"D");
        
        // SenderCompID (49)
        self.append_tag_value_bytes(49, &self.sender_comp_id[..self.sender_comp_id_len as usize]);
        
        // TargetCompID (56)
        self.append_tag_value_bytes(56, &self.target_comp_id[..self.target_comp_id_len as usize]);
        
        // MsgSeqNum (34)
        self.append_tag_value_u32(34, self.msg_seq_num);
        self.msg_seq_num += 1;
        
        // SendingTime (52) - UTC timestamp YYYYMMDD-HH:MM:SS.sss
        // TODO: Fast time formatting
        
        // ClOrdID (11)
        self.append_tag_value_str(11, &order.cl_ord_id);
        
        // Symbol (55)
        self.append_tag_value_str(55, &order.symbol);
        
        // Side (54)
        self.append_tag_value_u8(54, order.side as u8);
        
        // TransactTime (60) - nanoseconds as string
        self.append_tag_value_u64(60, order.transact_time);
        
        // OrderQty (38) - scaled decimal
        self.append_tag_value_scaled(38, order.order_qty, 8);
        
        // OrdType (40)
        self.append_tag_value_u8(40, order.ord_type as u8);
        
        // Price (44) - if limit order
        if let Some(price) = order.price {
            self.append_tag_value_scaled(44, price, 8);
        }
        
        // TimeInForce (59)
        self.append_tag_value_u8(59, order.time_in_force as u8);
        
        // Calculate and patch body length
        let body_end = self.position;
        let body_len = body_end - body_len_pos - 1; // Exclude checksum field
        
        // Patch 5-digit body length
        self.patch_body_length(body_len_pos, body_len);
        
        // Checksum (10) - XOR of all bytes from (including) 8= to (excluding) 10=
        let checksum = self.compute_checksum(0, self.position);
        self.append_tag_value_u8_checksum(10, checksum);
        
        self.as_slice()
    }
    
    /// Append tag=value| (ASCII format)
    #[inline(always)]
    fn append_tag_value(&mut self, tag: u16, value: &[u8]) {
        self.append_u16(tag);
        self.buffer[self.position] = b'=';
        self.position += 1;
        self.append_raw(value);
        self.buffer[self.position] = 0x01; // SOH separator
        self.position += 1;
    }
    
    #[inline(always)]
    fn append_tag_value_bytes(&mut self, tag: u16, value: &[u8]) {
        self.append_u16(tag);
        self.buffer[self.position] = b'=';
        self.position += 1;
        self.buffer[self.position..self.position + value.len()].copy_from_slice(value);
        self.position += value.len();
        self.buffer[self.position] = 0x01;
        self.position += 1;
    }
    
    #[inline(always)]
    fn append_tag_value_str<const S: usize>(&mut self, tag: u16, value: &FixString<S>) {
        self.append_tag_value_bytes(tag, value.as_bytes());
    }
    
    #[inline(always)]
    fn append_tag_value_u8(&mut self, tag: u16, value: u8) {
        self.append_u16(tag);
        self.buffer[self.position] = b'=';
        self.position += 1;
        self.position += itoa::write(&mut self.buffer[self.position..], value).unwrap();
        self.buffer[self.position] = 0x01;
        self.position += 1;
    }
    
    #[inline(always)]
    fn append_tag_value_u32(&mut self, tag: u16, value: u32) {
        self.append_u16(tag);
        self.buffer[self.position] = b'=';
        self.position += 1;
        self.position += itoa::write(&mut self.buffer[self.position..], value).unwrap();
        self.buffer[self.position] = 0x01;
        self.position += 1;
    }
    
    #[inline(always)]
    fn append_tag_value_u64(&mut self, tag: u16, value: u64) {
        self.append_u16(tag);
        self.buffer[self.position] = b'=';
        self.position += 1;
        self.position += itoa::write(&mut self.buffer[self.position..], value).unwrap();
        self.buffer[self.position] = 0x01;
        self.position += 1;
    }
    
    /// Append scaled decimal (e.g., 1.5 with scale 8 = 150000000)
    #[inline(always)]
    fn append_tag_value_scaled(&mut self, tag: u16, value: i64, scale: u8) {
        self.append_u16(tag);
        self.buffer[self.position] = b'=';
        self.position += 1;
        
        // Convert scaled integer to decimal string
        let divisor = 10i64.pow(scale as u32);
        let whole = value / divisor;
        let frac = (value % divisor).abs();
        
        // Write whole part
        self.position += itoa::write(&mut self.buffer[self.position..], whole).unwrap();
        
        if frac > 0 {
            self.buffer[self.position] = b'.';
            self.position += 1;
            
            // Write fractional with leading zeros
            let frac_str = format!("{:08}", frac); // TODO: no-alloc
            self.append_raw(frac_str.trim_end_matches('0').as_bytes());
        }
        
        self.buffer[self.position] = 0x01;
        self.position += 1;
    }
    
    #[inline(always)]
    fn append_tag_value_u8_checksum(&mut self, tag: u16, value: u8) {
        self.append_u16(tag);
        self.buffer[self.position] = b'=';
        self.position += 1;
        
        // 3-digit checksum with leading zeros
        self.buffer[self.position] = b'0' + (value / 100);
        self.buffer[self.position + 1] = b'0' + ((value / 10) % 10);
        self.buffer[self.position + 2] = b'0' + (value % 10);
        self.position += 3;
        
        self.buffer[self.position] = 0x01;
        self.position += 1;
    }
    
    /// Fast u16 to ASCII
    #[inline(always)]
    fn append_u16(&mut self, value: u16) {
        if value >= 10000 {
            self.buffer[self.position] = b'0' + (value / 10000) as u8;
            self.position += 1;
        }
        if value >= 1000 {
            self.buffer[self.position] = b'0' + ((value / 1000) % 10) as u8;
            self.position += 1;
        }
        if value >= 100 {
            self.buffer[self.position] = b'0' + ((value / 100) % 10) as u8;
            self.position += 1;
        }
        if value >= 10 {
            self.buffer[self.position] = b'0' + ((value / 10) % 10) as u8;
            self.position += 1;
        }
        self.buffer[self.position] = b'0' + (value % 10) as u8;
        self.position += 1;
    }
    
    #[inline(always)]
    fn append_raw(&mut self, bytes: &[u8]) {
        self.buffer[self.position..self.position + bytes.len()].copy_from_slice(bytes);
        self.position += bytes.len();
    }
    
    /// Patch body length at position
    #[inline(always)]
    fn patch_body_length(&mut self, pos: usize, len: usize) {
        // Write 5-digit zero-padded length
        let len_u32 = len as u32;
        self.buffer[pos] = b'0' + ((len_u32 / 10000) % 10) as u8;
        self.buffer[pos + 1] = b'0' + ((len_u32 / 1000) % 10) as u8;
        self.buffer[pos + 2] = b'0' + ((len_u32 / 100) % 10) as u8;
        self.buffer[pos + 3] = b'0' + ((len_u32 / 10) % 10) as u8;
        self.buffer[pos + 4] = b'0' + (len_u32 % 10) as u8;
    }
    
    /// FIX checksum: XOR of all bytes
    #[inline(always)]
    fn compute_checksum(&self, start: usize, end: usize) -> u8 {
        // SIMD-accelerated for large messages
        if end - start >= 64 {
            self.checksum_simd(start, end)
        } else {
            self.checksum_scalar(start, end)
        }
    }
    
    #[inline(always)]
    fn checksum_scalar(&self, start: usize, end: usize) -> u8 {
        let mut sum: u8 = 0;
        for i in start..end {
            sum = sum.wrapping_add(self.buffer[i]);
        }
        sum
    }
    
    /// SIMD checksum using 32-byte vectors
    #[inline(always)]
    fn checksum_simd(&self, start: usize, end: usize) -> u8 {
        use std::simd::{Simd, SimdUint};
        
        const LANES: usize = 32;
        type V = Simd<u8, LANES>;
        
        let mut sum_vec = V::splat(0);
        let mut i = start;
        
        // Process 32-byte chunks
        while i + LANES <= end {
            let chunk = V::from_slice(&self.buffer[i..i + LANES]);
            sum_vec += chunk;
            i += LANES;
        }
        
        // Horizontal sum
        let sum32: u32 = sum_vec.reduce_sum() as u32;
        
        // Remainder
        let mut sum: u8 = (sum32 & 0xFF) as u8;
        for j in i..end {
            sum = sum.wrapping_add(self.buffer[j]);
        }
        
        sum
    }
}

/// Fast integer formatting (itoa crate or custom)
mod itoa {
    #[inline]
    pub fn write(buf: &mut [u8], mut n: u64) -> usize {
        let mut i = 0;
        let mut temp = n;
        let mut digits = [0u8; 20];
        let mut pos = 0;
        
        if n == 0 {
            buf[0] = b'0';
            return 1;
        }
        
        while temp > 0 {
            digits[pos] = b'0' + (temp % 10) as u8;
            temp /= 10;
            pos += 1;
        }
        
        // Reverse into buffer
        for j in (0..pos).rev() {
            buf[i] = digits[j];
            i += 1;
        }
        
        i
    }
}
