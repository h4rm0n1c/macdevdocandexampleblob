# Null Modem Cable: Mac RS-422 ↔ PC RS-232 (DB-9 F–F)

This directory documents a proven-working null modem cable for connecting a classic Mac
(Quadra-era RS-422 mini-DIN-8) to a PC RS-232 DB-9 serial port.

The goal: a reliable, repeatable wiring reference that you can hand to Future You
(or someone else) without hunting through forum posts.

---

## Wiring Diagram

![Quadra 700 RS-422 to PC RS-232 null-modem wiring](./422_TO_232_DONGLE.png)

---

## Notes

- Mac side: RS-422 (mini-DIN-8) configured to talk to PC-style RS-232.
- PC side: DB-9 female, wired as a null modem (crossed TX/RX, with appropriate handshaking).
- Intended for:
  - Direct serial file transfer
  - Serial console / terminal access
  - General Mac ↔ PC experiments where a “real” null-modem cable is required
