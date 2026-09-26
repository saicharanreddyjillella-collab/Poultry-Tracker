# Design Doc — Shared Accounting Core + Chicken Center

**Status:** Draft for approval
**Author:** Sai Charan Reddy
**Scope:** A reusable double-entry accounting engine, and Sai Charan Chicken Center as its first module. Sai Ram Feeds and the Layer Farm will bridge into the same core later.

---

## 1. Goal

Build **one accounting core** that knows nothing about chickens, feed, or eggs — it only understands accounts, parties, and balanced vouchers. Each business (Chicken Center, Feeds, Layer Farm) is a **domain module** that posts transactions into that core.

Money lives in the core. Birds, weights, FCR, and grades live in the modules. They meet at exactly one boundary: **posting a voucher.**

### Non-goals (for now)
- Statutory GST filing / e-invoicing (fields reserved, not wired).
- Multi-currency (everything is INR).
- Exposing debit/credit terminology to end users — it stays internal.

---

## 2. Principles

1. **True double-entry, hidden behind plain screens.** Every transaction posts balanced debits and credits internally. Users only ever see "Sale to Ravi Shop ₹40,000" — never "Dr/Cr".
2. **Money is always fixed-decimal, never float.** `DecimalField(max_digits=14, decimal_places=2)` everywhere. (We already hit and fixed a float bug in Feeds billing — this rule is non-negotiable.)
3. **Vouchers are atomic.** All lines of a voucher post inside one `transaction.atomic()` block, or none do.
4. **Ledgers are derived, never stored as a mutable number.** A party's balance = sum of its entries. No "balance" column that can drift out of sync.
5. **Append-only spirit with an audit trail.** Edits/deletes are allowed but logged (who, when, what changed). Optional day-close lock on top.
6. **Clean boundary.** The core imports nothing from the business modules. Modules call `accounting.post_voucher(...)`. No chicken fields ever enter the core.

---

## 3. Architecture

```
landing page  →  Sai Ram Feeds (existing app)
              →  Sai Charan Chicken Center (new module)
              →  Layer Farm (future module)

accounting/            ← shared Django app — NO poultry knowledge
  models:   Account, Party, Voucher, Entry, AuditLog
  services: post_voucher(), reverse_voucher(),
            party_ledger(), account_ledger(),
            trial_balance(), cash_book(), profit_and_loss()

chicken_center/        ← domain module (new)
  models:   ShopCustomer, Supplier, Purchase, Sale, Collection, Expense
  each action → accounting.post_voucher(...)
  + WhatsApp messaging on Sale and Collection

feeds/                 ← existing app (bridged in phase 2)
  + posts farmer bills into accounting

layer_farm/            ← future, same pattern
```

Same Django project, same PostgreSQL DB, same auth/users/roles/backups you already run. The Chicken Center is a **new app inside the existing project**, not a new deployment.

---

## 4. The Accounting Core — data model

### 4.1 Account
The chart of accounts. Every account has a **type** that fixes its normal balance and where it lands in reports.

| Field | Notes |
|---|---|
| code | short unique code (e.g. `CASH`, `BANK`, `SALES`) |
| name | display name |
| type | one of: ASSET, LIABILITY, INCOME, EXPENSE, EQUITY |
| is_party_control | true for control accounts that group parties (Debtors, Creditors) |
| active | soft-disable without deleting |

### 4.2 Party
A customer or supplier (or any entity you transact with). Each party is tied to a control account.

| Field | Notes |
|---|---|
| name, phone, address | contact info |
| party_type | CUSTOMER / SUPPLIER (a party can be both) |
| control_account | FK → Account (Debtors for customers, Creditors for suppliers) |
| opening_balance | signed decimal; seeded as an opening voucher |
| business | which module owns it (chicken_center / feeds / layer) — for filtering, not for logic |

### 4.3 Voucher
One business event. Groups the entries that must balance.

| Field | Notes |
|---|---|
| date | transaction date |
| type | SALE, PURCHASE, RECEIPT, PAYMENT, EXPENSE, JOURNAL, OPENING |
| narration | human description ("Sale to Ravi Shop") |
| source_module | chicken_center / feeds / layer |
| source_ref | id of the originating record (Sale #123) — lets us trace back |
| created_by | user |
| is_reversed | vouchers are reversed, not edited, for corrections |

### 4.4 Entry
A single debit or credit line inside a voucher. **Sum of debits = sum of credits per voucher (enforced).**

| Field | Notes |
|---|---|
| voucher | FK → Voucher |
| account | FK → Account (or party's control account) |
| party | FK → Party, nullable (set when the line hits a party) |
| debit | decimal ≥ 0 |
| credit | decimal ≥ 0 |

Rule: exactly one of debit/credit is non-zero per line.

### 4.5 AuditLog
Who did what. Written on every create/edit/delete/reverse.

| Field | Notes |
|---|---|
| timestamp, user | |
| action | CREATE / EDIT / DELETE / REVERSE |
| object_type, object_id | what was touched |
| detail | JSON snapshot of the change |

---

## 5. How transactions post (the heart of it)

Users never see this. The module calls one function; the core does the rest atomically.

**Chicken Center — Sale of ₹40,000 to Ravi Shop:**
```
Dr  Ravi Shop (Debtors)     40,000     ← he now owes us
    Cr  Sales                    40,000 ← we earned income
```

**Collection — Ravi pays ₹25,000 cash:**
```
Dr  Cash                    25,000     ← cash increased
    Cr  Ravi Shop (Debtors)      25,000 ← his dues reduced
```

**Purchase — bought birds for ₹30,000 from a supplier on credit:**
```
Dr  Purchases               30,000
    Cr  Supplier (Creditors)     30,000 ← we now owe him
```

**Expense — ₹1,200 transport, cash:**
```
Dr  Transport (Expense)      1,200
    Cr  Cash                      1,200
```

**Feeds (phase 2) — farmer bill, net payable ₹1,03,234:**
```
Dr  Growing Charges (Expense)  1,03,234
    Cr  Farmer (Creditors)          1,03,234 ← we owe the farmer
```

Every one balances. Every one is one `post_voucher()` call. Ravi's statement, the cash book, and the P&L all fall out of these entries automatically — nothing is computed twice.

---

## 6. Default Chart of Accounts (starter — renamable later)

**Assets:** Cash, Bank, UPI, Debtors (customer control), Stock-in-hand
**Liabilities:** Creditors (supplier control), Farmer Payables (Feeds)
**Income:** Sales, Egg Sales (layer)
**Expenses:** Purchases, Transport, Labour, Ice, Fuel, Rent, Electricity, Miscellaneous
**Equity:** Capital, Opening Balance Equity

Each business tags which heads it uses; unused ones stay hidden.

---

## 7. Chicken Center module — screens & flow

1. **Customers / Suppliers** — master list, add/edit, per-party statement (passbook with running balance), outstanding.
2. **New Sale** — pick customer, birds, weight, rate/kg → amount auto → posts SALE voucher → **WhatsApp message** to customer (items, amount, new balance).
3. **New Purchase** — supplier, birds, weight, rate, transport → posts PURCHASE voucher.
4. **Collect Payment** — customer, amount, mode (cash/UPI/bank) → posts RECEIPT voucher → **WhatsApp receipt** (amount paid, balance left).
5. **Pay Supplier** — supplier, amount, mode → posts PAYMENT voucher.
6. **Expense** — category, amount, mode → posts EXPENSE voucher.
7. **Day book** — everything that happened today, cash position.

---

## 8. Reports (from the core, reused by every business)

- **Party statement** — passbook per customer/supplier, any date range.
- **Outstanding + ageing** — who owes what, how old (0–30 / 30–60 / 60+ days).
- **Cash book** — opening, receipts, payments, closing; reconciles to counted cash.
- **Profit & Loss** — income − expenses, by day/month.
- **Trial balance** — internal check that the books balance (debits = credits).
- **Day sales & collection sheet.**
All exportable to Excel/PDF (infra already exists).

---

## 9. Messaging (WhatsApp)

**Phase 1 — `wa.me` click-to-send (free, ships now).** App builds a pre-filled WhatsApp message; you tap send from your phone. Zero cost, no approval.

**Later — WhatsApp Business API (fully automatic).** Provider (Interakt/Gupshup/Twilio) with approved templates, ~₹0.30–0.80/msg. The message content and triggers are identical, so nothing is wasted upgrading.

**Triggers:** on Sale, on Collection. Optional: periodic outstanding reminder.

---

## 10. Reuse across businesses

| Business | Posts into core as |
|---|---|
| Chicken Center | Sales, Purchases, Receipts, Payments, Expenses |
| Sai Ram Feeds | Farmer bills → Farmer Payables; recoveries reverse it |
| Layer Farm | Egg sales → Income; feed consumption → Expense; bird cost |

One ledger structure, one set of reports, a **consolidated group P&L and cash position** across all three.

---

## 11. Build phases

**Phase 1 — Accounting core + Chicken Center MVP**
Core models + `post_voucher()` + party ledger. Landing page split. Customer/supplier masters, sale/purchase/collection/payment entry, per-party statement, outstanding report, WhatsApp click-to-send. *Replaces the paper ledger.*

**Phase 2 — Money & stock**
Expenses, cash book, stock-in-hand with shrinkage/mortality, collection summary.

**Phase 3 — Accounting outputs**
P&L, margin, ageing, printable invoices, Excel/PDF exports, trial balance.

**Phase 4 — Trust & scale**
Audit trail surfaced, day-close lock, WhatsApp API upgrade, GST fields, bridge Feeds into the core, then Layer Farm.

---

## 12. Decisions locked

- True double-entry core, hidden behind plain-language screens.
- Django, same project, new `accounting` app + `chicken_center` app.
- Fixed-decimal money everywhere.
- Chicken Center is the first module (greenfield proof); Feeds bridged second.
- WhatsApp click-to-send first, API later.

## 13. Open questions before Phase 1 code

1. Track **purchases/suppliers** in Phase 1 (for margin & payables), or sales + collections only?
2. **Expenses** in Phase 1 or Phase 2?
3. **Invoices/GST** now or later?
4. Editing: **strict day-close lock**, or **edit-with-audit-log**?
5. Rough scale: shops count, sales/day (decides manual click-to-send vs API urgency)?
