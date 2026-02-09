"""Database persistence for contract monitoring state.

This package provides SQLAlchemy async models and repository for:
- Check result history (90-day retention)
- Violation records
- SLA status tracking
- Daily aggregates (indefinite retention)
- Registered contracts
- Alert deduplication state
"""

from __future__ import annotations
