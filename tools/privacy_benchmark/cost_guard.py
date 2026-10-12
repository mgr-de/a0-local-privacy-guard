"""Test-only preflight ledger. Prices must already be conservative EUR/token.

Reservations must precede every provider call, including utility and retries.
Unknown prices or output limits are rejected. No credentials handled here.
"""
from decimal import Decimal
import sqlite3

class CostGuard:
    def __init__(self, path, limit_eur='5'):
        self.limit = Decimal(limit_eur)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.execute('CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, reserved TEXT NOT NULL, charged TEXT)')
        self.db.commit()

    def reserve(self, input_token_upper_bound, max_output_tokens, input_eur_per_token, output_eur_per_token):
        if input_eur_per_token is None or output_eur_per_token is None:
            raise ValueError('Unknown provider price')
        if input_token_upper_bound <= 0 or max_output_tokens <= 0:
            raise ValueError('Missing token bound')
        prices = (Decimal(str(input_eur_per_token)),Decimal(str(output_eur_per_token)))
        if any(not p.is_finite() or p < 0 for p in prices): raise ValueError('Invalid price')
        amount = Decimal(input_token_upper_bound)*prices[0] + Decimal(max_output_tokens)*prices[1]
        self.db.execute('BEGIN IMMEDIATE')
        try:
            spent = sum((Decimal(charged if charged is not None else reserved)
                         for reserved,charged in self.db.execute('SELECT reserved,charged FROM calls')),Decimal(0))
            if spent + amount > self.limit: raise RuntimeError('5 EUR budget would be exceeded')
            ticket = self.db.execute('INSERT INTO calls(reserved) VALUES (?)',(str(amount),)).lastrowid
            self.db.commit()
            return ticket
        except BaseException:
            self.db.rollback()
            raise

    def settle(self,ticket,actual_eur=None):
        # Without verified usage the full reservation remains charged.
        row = self.db.execute('SELECT reserved,charged FROM calls WHERE id=?',(ticket,)).fetchone()
        if row is None or row[1] is not None: raise ValueError('Unknown or settled call')
        charged = Decimal(row[0]) if actual_eur is None else Decimal(str(actual_eur))
        if not charged.is_finite() or charged < 0 or charged > Decimal(row[0]):
            raise ValueError('Usage exceeds verified upper bound')
        self.db.execute('UPDATE calls SET charged=? WHERE id=?',(str(charged),ticket))
        self.db.commit()

