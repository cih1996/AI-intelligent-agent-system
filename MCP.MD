┌──────────────┐
│   User App   │
└──────┬───────┘
       │ Query Pricing
       ▼
┌──────────────┐
│   MCP Tool   │
└──────┬───────┘
       │ Return payment_request (402)
       ▼
┌──────────────┐
│ User Wallet  │  ← pays TRX/MCPX
└──────┬───────┘
       │ On-chain payment (tx_hash + order_id)
       ▼
┌──────────────┐
│ Billing Node │ ← listens TRON chain
└──────┬───────┘
       │ verify_payment
       ▼
┌──────────────┐
│   MCP Tool   │ ← issues usage_key
└──────┬───────┘
       │ call_tool with usage_key
       ▼
┌──────────────┐
│ Tool Result +│
│ Billing Info │
└──────────────┘
