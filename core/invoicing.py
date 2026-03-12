# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Invoice & Proposal Generator — Professional documents from conversations.

Replaces: FreshBooks ($17/mo), Wave, Proposify ($49/mo), PandaDoc ($35/mo)

Features:
  - Create invoices with line items, tax, discounts
  - Create proposals with sections, pricing tables, terms
  - Professional PDF/Word export with user's branding
  - Status tracking (draft → sent → viewed → accepted/paid)
  - Payment tracking and reminders
  - AI drafting: "create a proposal based on our conversation about the Johnson project"
  - Sequential numbering (INV-001, PROP-001)
  - Client information auto-fill from CRM contacts
  - Recurring invoice templates
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.invoicing")


class InvoiceManager:
    """Create, manage, and export invoices and proposals."""

    # ── Business Profile ──

    def set_business_profile(self, owner_id: str, business_name: str,
                              address: str = "", phone: str = "",
                              email: str = "", website: str = "",
                              tax_id: str = "", logo_url: str = "",
                              payment_instructions: str = "",
                              default_currency: str = "USD",
                              default_tax_rate: float = 0,
                              default_payment_terms: int = 30) -> dict:
        """Set the user's business profile for invoices/proposals."""
        profile = {
            "business_name": business_name,
            "address": address,
            "phone": phone,
            "email": email,
            "website": website,
            "tax_id": tax_id,
            "logo_url": logo_url,
            "payment_instructions": payment_instructions,
            "default_currency": default_currency,
            "default_tax_rate": default_tax_rate,
            "default_payment_terms": default_payment_terms,
        }
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO invoice_profiles (owner_id, profile)
                VALUES (?,?)
            """, (owner_id, json.dumps(profile)))
        return profile

    def get_business_profile(self, owner_id: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT profile FROM invoice_profiles WHERE owner_id=?",
                (owner_id,)).fetchone()
        if not row:
            return {"business_name": "", "default_currency": "USD",
                    "default_tax_rate": 0, "default_payment_terms": 30}
        return json.loads(dict(row)["profile"])

    # ── Invoices ──

    def create_invoice(self, owner_id: str, client_name: str,
                        client_email: str = "", client_address: str = "",
                        line_items: list = None, tax_rate: float = None,
                        discount: float = 0, notes: str = "",
                        due_days: int = None, currency: str = None) -> dict:
        """Create an invoice."""
        profile = self.get_business_profile(owner_id)
        iid = f"inv_{uuid.uuid4().hex[:10]}"
        inv_number = self._next_number(owner_id, "INV")

        if tax_rate is None:
            tax_rate = profile.get("default_tax_rate", 0)
        if due_days is None:
            due_days = profile.get("default_payment_terms", 30)
        if currency is None:
            currency = profile.get("default_currency", "USD")

        items = line_items or []
        subtotal = sum(item.get("quantity", 1) * item.get("unit_price", 0) for item in items)
        tax_amount = round(subtotal * tax_rate / 100, 2)
        total = round(subtotal - discount + tax_amount, 2)

        due_date = (datetime.now() + timedelta(days=due_days)).strftime("%Y-%m-%d")

        with get_db() as db:
            db.execute("""
                INSERT INTO invoices
                    (id, owner_id, invoice_number, client_name, client_email,
                     client_address, line_items, subtotal, tax_rate, tax_amount,
                     discount, total, currency, notes, due_date, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (iid, owner_id, inv_number, client_name, client_email,
                  client_address, json.dumps(items), subtotal, tax_rate,
                  tax_amount, discount, total, currency, notes, due_date, "draft"))

        return {
            "id": iid,
            "invoice_number": inv_number,
            "client": client_name,
            "subtotal": subtotal,
            "tax": tax_amount,
            "discount": discount,
            "total": total,
            "currency": currency,
            "due_date": due_date,
            "status": "draft",
        }

    def get_invoice(self, invoice_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM invoices WHERE id=?",
                            (invoice_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["line_items"] = json.loads(d.get("line_items", "[]"))
        return d

    def list_invoices(self, owner_id: str, status: str = None) -> list:
        with get_db() as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM invoices WHERE owner_id=? AND status=? ORDER BY created_at DESC",
                    (owner_id, status)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM invoices WHERE owner_id=? ORDER BY created_at DESC",
                    (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["line_items"] = json.loads(d.get("line_items", "[]"))
            result.append(d)
        return result

    def update_invoice(self, invoice_id: str, **updates) -> dict:
        if "line_items" in updates:
            items = updates["line_items"]
            updates["line_items"] = json.dumps(items)
            updates["subtotal"] = sum(i.get("quantity", 1) * i.get("unit_price", 0) for i in items)
            # Recalculate total
            inv = self.get_invoice(invoice_id)
            if inv:
                tax = round(updates["subtotal"] * inv.get("tax_rate", 0) / 100, 2)
                updates["tax_amount"] = tax
                updates["total"] = round(updates["subtotal"] - inv.get("discount", 0) + tax, 2)
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [invoice_id]
        with get_db() as db:
            db.execute(f"UPDATE invoices SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def mark_sent(self, invoice_id: str) -> dict:
        return self.update_invoice(invoice_id, status="sent",
                                    sent_at=datetime.now().isoformat())

    def mark_paid(self, invoice_id: str, payment_method: str = "",
                   payment_date: str = "") -> dict:
        return self.update_invoice(
            invoice_id, status="paid",
            payment_method=payment_method,
            paid_at=payment_date or datetime.now().isoformat())

    def get_overdue(self, owner_id: str) -> list:
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db() as db:
            rows = db.execute("""
                SELECT * FROM invoices WHERE owner_id=?
                AND status='sent' AND due_date < ?
                ORDER BY due_date
            """, (owner_id, today)).fetchall()
        return [dict(r) for r in rows]

    # ── Proposals ──

    def create_proposal(self, owner_id: str, title: str, client_name: str,
                         client_email: str = "", sections: list = None,
                         pricing_items: list = None, total: float = 0,
                         valid_days: int = 30, notes: str = "",
                         terms: str = "") -> dict:
        """Create a proposal."""
        pid = f"prop_{uuid.uuid4().hex[:10]}"
        prop_number = self._next_number(owner_id, "PROP")
        valid_until = (datetime.now() + timedelta(days=valid_days)).strftime("%Y-%m-%d")

        if pricing_items and not total:
            total = sum(i.get("amount", 0) for i in pricing_items)

        with get_db() as db:
            db.execute("""
                INSERT INTO proposals
                    (id, owner_id, proposal_number, title, client_name,
                     client_email, sections, pricing_items, total,
                     valid_until, notes, terms, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (pid, owner_id, prop_number, title, client_name,
                  client_email, json.dumps(sections or []),
                  json.dumps(pricing_items or []), total,
                  valid_until, notes, terms, "draft"))

        return {"id": pid, "proposal_number": prop_number,
                "title": title, "total": total, "valid_until": valid_until}

    def get_proposal(self, proposal_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM proposals WHERE id=?",
                            (proposal_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["sections"] = json.loads(d.get("sections", "[]"))
        d["pricing_items"] = json.loads(d.get("pricing_items", "[]"))
        return d

    def list_proposals(self, owner_id: str, status: str = None) -> list:
        with get_db() as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM proposals WHERE owner_id=? AND status=? ORDER BY created_at DESC",
                    (owner_id, status)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM proposals WHERE owner_id=? ORDER BY created_at DESC",
                    (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["sections"] = json.loads(d.get("sections", "[]"))
            d["pricing_items"] = json.loads(d.get("pricing_items", "[]"))
            result.append(d)
        return result

    def accept_proposal(self, proposal_id: str) -> dict:
        with get_db() as db:
            db.execute("UPDATE proposals SET status='accepted', accepted_at=? WHERE id=?",
                      (datetime.now().isoformat(), proposal_id))
        return {"accepted": True}

    # ── Revenue Dashboard ──

    def get_revenue_dashboard(self, owner_id: str) -> dict:
        with get_db() as db:
            total_invoiced = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM invoices WHERE owner_id=?",
                (owner_id,)).fetchone()
            total_paid = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM invoices WHERE owner_id=? AND status='paid'",
                (owner_id,)).fetchone()
            outstanding = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM invoices WHERE owner_id=? AND status='sent'",
                (owner_id,)).fetchone()
            proposal_value = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM proposals WHERE owner_id=? AND status='sent'",
                (owner_id,)).fetchone()
            accepted = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM proposals WHERE owner_id=? AND status='accepted'",
                (owner_id,)).fetchone()
            overdue = self.get_overdue(owner_id)

        return {
            "total_invoiced": round(dict(total_invoiced)["t"], 2),
            "total_paid": round(dict(total_paid)["t"], 2),
            "outstanding": round(dict(outstanding)["t"], 2),
            "overdue_count": len(overdue),
            "overdue_value": round(sum(d.get("total", 0) for d in overdue), 2),
            "proposals_pending_value": round(dict(proposal_value)["t"], 2),
            "proposals_accepted_value": round(dict(accepted)["t"], 2),
        }

    # ── PDF Export ──

    def invoice_to_html(self, invoice: dict, profile: dict) -> str:
        """Generate professional HTML for an invoice."""
        items_html = ""
        for item in invoice.get("line_items", []):
            qty = item.get("quantity", 1)
            price = item.get("unit_price", 0)
            line_total = qty * price
            items_html += f"""
            <tr>
                <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9">{item.get('description','')}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;text-align:center">{qty}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;text-align:right">${price:,.2f}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;text-align:right">${line_total:,.2f}</td>
            </tr>"""

        currency = invoice.get("currency", "USD")
        sym = "$" if currency == "USD" else currency + " "

        return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
        <style>
            body{{font-family:-apple-system,sans-serif;color:#1e293b;margin:0;padding:40px}}
            .header{{display:flex;justify-content:space-between;margin-bottom:40px}}
            .invoice-label{{font-size:28px;font-weight:700;color:#a459f2}}
            table{{width:100%;border-collapse:collapse}}
            th{{background:#f8f9fb;padding:10px 12px;text-align:left;font-size:12px;
                text-transform:uppercase;letter-spacing:1px;color:#64748b}}
        </style></head><body>
        <div class="header">
            <div>
                <div style="font-size:18px;font-weight:700">{profile.get('business_name','')}</div>
                <div style="font-size:12px;color:#64748b;white-space:pre-line">{profile.get('address','')}</div>
                <div style="font-size:12px;color:#64748b">{profile.get('email','')}</div>
            </div>
            <div style="text-align:right">
                <div class="invoice-label">INVOICE</div>
                <div style="font-size:14px;color:#64748b">#{invoice.get('invoice_number','')}</div>
                <div style="font-size:12px;color:#64748b;margin-top:8px">
                    Date: {invoice.get('created_at','')[:10]}<br>
                    Due: {invoice.get('due_date','')}<br>
                    Status: {invoice.get('status','draft').upper()}
                </div>
            </div>
        </div>
        <div style="margin-bottom:24px">
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#94a3b8;margin-bottom:4px">Bill To</div>
            <div style="font-weight:600">{invoice.get('client_name','')}</div>
            <div style="font-size:13px;color:#64748b">{invoice.get('client_email','')}</div>
            <div style="font-size:13px;color:#64748b;white-space:pre-line">{invoice.get('client_address','')}</div>
        </div>
        <table>
            <thead><tr>
                <th>Description</th><th style="text-align:center">Qty</th>
                <th style="text-align:right">Unit Price</th><th style="text-align:right">Amount</th>
            </tr></thead>
            <tbody>{items_html}</tbody>
        </table>
        <div style="margin-top:16px;text-align:right">
            <div style="font-size:13px;color:#64748b">Subtotal: {sym}{invoice.get('subtotal',0):,.2f}</div>
            {'<div style="font-size:13px;color:#64748b">Tax (' + str(invoice.get("tax_rate",0)) + '%): ' + sym + f'{invoice.get("tax_amount",0):,.2f}</div>' if invoice.get('tax_rate') else ''}
            {'<div style="font-size:13px;color:#22c55e">Discount: -' + sym + f'{invoice.get("discount",0):,.2f}</div>' if invoice.get('discount') else ''}
            <div style="font-size:20px;font-weight:700;color:#a459f2;margin-top:8px">
                Total: {sym}{invoice.get('total',0):,.2f}
            </div>
        </div>
        {'<div style="margin-top:32px;padding:16px;background:#f8f9fb;border-radius:8px;font-size:13px;color:#64748b"><strong>Payment Instructions:</strong><br>' + profile.get("payment_instructions","") + '</div>' if profile.get('payment_instructions') else ''}
        {'<div style="margin-top:16px;font-size:12px;color:#94a3b8">' + invoice.get("notes","") + '</div>' if invoice.get('notes') else ''}
        <div style="margin-top:40px;font-size:9px;color:#cbd5e1;text-align:center">
            Generated by MyTeam360 | © 2026 Praxis Holdings LLC
        </div>
        </body></html>"""

    # ── Internal ──

    def _next_number(self, owner_id: str, prefix: str) -> str:
        with get_db() as db:
            if prefix == "INV":
                row = db.execute(
                    "SELECT COUNT(*) as c FROM invoices WHERE owner_id=?",
                    (owner_id,)).fetchone()
            else:
                row = db.execute(
                    "SELECT COUNT(*) as c FROM proposals WHERE owner_id=?",
                    (owner_id,)).fetchone()
        count = dict(row)["c"] + 1
        return f"{prefix}-{count:04d}"
