//! FIX 5.0 SP2 + FIXP (Performance) Session Layer
//! Binary-encoded where possible, ASCII for compatibility

use heapless::String;
use heapless::Vec;

// Fixed-capacity strings for stack allocation
pub type FixString<const N: usize> = String<N>;
pub type FixVec<T, const N: usize> = Vec<T, N>;

/// Session message types (FIXP SOFH)
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionMsgType {
    Heartbeat = 0,
    TestRequest = 1,
    ResendRequest = 2,
    Reject = 3,
    SequenceReset = 4,
    Logout = 5,
    Logon = 6,
    NewOrderSingle = 7,
    ExecutionReport = 8,
    OrderCancelRequest = 9,
    OrderCancelReject = 10,
    BusinessMessageReject = 11,
}

/// Application message: NewOrderSingle (MsgType=D, 35=D)
#[derive(Debug, Clone)]
pub struct NewOrderSingle<const N: usize = 64> {
    pub cl_ord_id: FixString<N>,      // 11: Client Order ID
    pub symbol: FixString<N>,          // 55: Symbol
    pub side: Side,                    // 54: 1=Buy, 2=Sell
    pub order_qty: i64,               // 38: Quantity (scaled 1e8)
    pub ord_type: OrdType,            // 40: 1=Market, 2=Limit
    pub price: Option<i64>,           // 44: Price (scaled 1e8), None for market
    pub time_in_force: TimeInForce,   // 59: 0=Day, 1=GTC, 3=IOC, 4=FOK
    pub transact_time: u64,           // 60: Nanoseconds since UNIX epoch
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Side {
    Buy = 1,
    Sell = 2,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum OrdType {
    Market = 1,
    Limit = 2,
    Stop = 3,
    StopLimit = 4,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum TimeInForce {
    Day = 0,
    GTC = 1,      // Good Till Cancel
    IOC = 3,      // Immediate Or Cancel
    FOK = 4,      // Fill Or Kill
    GTD = 6,      // Good Till Date
}

/// Execution report (MsgType=8, 35=8)
#[derive(Debug, Clone)]
pub struct ExecutionReport<const N: usize = 64> {
    pub order_id: FixString<N>,       // 37: Order ID
    pub cl_ord_id: FixString<N>,       // 11: Client Order ID
    pub exec_id: FixString<N>,        // 17: Execution ID
    pub exec_type: ExecType,          // 150: 0=New, 1=Partial fill, 2=Fill, 4=Canceled
    pub ord_status: OrdStatus,        // 39: Same as exec_type mostly
    pub symbol: FixString<N>,          // 55
    pub side: Side,                    // 54
    pub leaves_qty: i64,              // 151: Remaining
    pub cum_qty: i64,                 // 14: Cumulative filled
    pub avg_px: Option<i64>,          // 6: Average price
    pub last_qty: i64,                // 32: This fill quantity
    pub last_px: Option<i64>,         // 31: This fill price
    pub transact_time: u64,           // 60
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum ExecType {
    New = 0,
    PartialFill = 1,
    Fill = 2,
    DoneForDay = 3,
    Canceled = 4,
    Replace = 5,
    PendingCancel = 6,
    Stopped = 7,
    Rejected = 8,
    Suspended = 9,
    PendingNew = 10,
    Calculated = 11,
    Expired = 12,
    Restated = 13,
    PendingReplace = 14,
    Trade = 15,
    TradeCorrect = 16,
    TradeCancel = 17,
    OrderStatus = 18,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum OrdStatus {
    New = 0,
    PartiallyFilled = 1,
    Filled = 2,
    DoneForDay = 3,
    Canceled = 4,
    Replaced = 5,
    PendingCancel = 6,
    Stopped = 7,
    Rejected = 8,
    Suspended = 9,
    PendingNew = 10,
    Calculated = 11,
    Expired = 12,
    AcceptedForBidding = 13,
    PendingReplace = 14,
}
