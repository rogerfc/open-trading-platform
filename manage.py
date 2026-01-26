#!/usr/bin/env python3
"""
Management script for the stock exchange.

Usage (via API):
    python manage.py companies load [-f data/companies.json] [--base-url http://localhost:8000]
    python manage.py companies show [--base-url http://localhost:8000]

Usage (direct DB access):
    python manage.py db companies load [-f data/companies.json]
    python manage.py db companies show
    python manage.py db clear
    python manage.py db status
"""

import asyncio
import json
from pathlib import Path

import click
import httpx
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, Base
from app.models import Account, Company, Holding, Order, Trade


DEFAULT_BASE_URL = "http://localhost:8000"


# ============================================================================
# Direct database operations (internal)
# ============================================================================


async def _init_db():
    """Initialize the database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _clear_db():
    """Drop and recreate all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _db_load_companies(filepath: Path):
    """Load companies from a JSON file directly to DB."""
    with open(filepath) as f:
        companies_data = json.load(f)

    async with AsyncSessionLocal() as session:
        loaded = 0
        skipped = 0

        for data in companies_data:
            result = await session.execute(
                select(Company).where(Company.ticker == data["ticker"])
            )
            if result.scalar_one_or_none():
                skipped += 1
                click.echo(f"  Skipped {data['ticker']} (already exists)")
                continue

            company = Company(
                ticker=data["ticker"],
                name=data["name"],
                total_shares=data["total_shares"],
                float_shares=data["float_shares"],
            )
            session.add(company)
            loaded += 1
            click.echo(f"  Loaded {data['ticker']}: {data['name']}")

        await session.commit()

    return loaded, skipped


async def _db_show_companies():
    """Show all companies from DB."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Company).order_by(Company.ticker))
        return list(result.scalars().all())


async def _count_records():
    """Count records in each table."""
    async with AsyncSessionLocal() as session:
        counts = {}
        for model, name in [
            (Company, "companies"),
            (Account, "accounts"),
            (Holding, "holdings"),
            (Order, "orders"),
            (Trade, "trades"),
        ]:
            result = await session.execute(select(model))
            counts[name] = len(result.scalars().all())
        return counts


# ============================================================================
# API operations
# ============================================================================


def _api_load_companies(filepath: Path, base_url: str):
    """Load companies via API."""
    with open(filepath) as f:
        companies_data = json.load(f)

    loaded = 0
    skipped = 0
    errors = 0

    with httpx.Client(base_url=base_url, timeout=30) as client:
        for data in companies_data:
            response = client.post("/admin/companies", json=data)

            if response.status_code == 201:
                loaded += 1
                click.echo(f"  Loaded {data['ticker']}: {data['name']}")
            elif response.status_code == 409:
                skipped += 1
                click.echo(f"  Skipped {data['ticker']} (already exists)")
            else:
                errors += 1
                error_detail = response.json().get("detail", response.text)
                click.echo(f"  Error {data['ticker']}: {error_detail}", err=True)

    return loaded, skipped, errors


def _api_show_companies(base_url: str):
    """Get companies via API."""
    with httpx.Client(base_url=base_url, timeout=30) as client:
        response = client.get("/admin/companies")
        if response.status_code == 404:
            raise click.ClickException(
                f"Endpoint not found. Is the Stock Exchange API running at {base_url}?"
            )
        response.raise_for_status()
        return response.json()


# ============================================================================
# CLI: Main group
# ============================================================================


@click.group()
def cli():
    """Stock Exchange management commands."""
    pass


# ============================================================================
# CLI: companies (via API)
# ============================================================================


@cli.group()
def companies():
    """Manage companies (via API)."""
    pass


@companies.command("load")
@click.option(
    "--file", "-f",
    default="data/companies.json",
    type=click.Path(exists=True),
    help="JSON file with company data",
)
@click.option(
    "--base-url", "-u",
    default=DEFAULT_BASE_URL,
    help=f"API base URL (default: {DEFAULT_BASE_URL})",
)
def companies_load(file, base_url):
    """Load companies from a JSON file via API."""
    click.echo(f"Loading companies from {file} via {base_url}...")

    try:
        loaded, skipped, errors = _api_load_companies(Path(file), base_url)
        click.echo(f"\nDone: {loaded} loaded, {skipped} skipped, {errors} errors")
    except httpx.ConnectError:
        click.echo(f"\nError: Could not connect to {base_url}", err=True)
        click.echo("Is the server running? Start it with: uvicorn app.main:app", err=True)
        raise SystemExit(1)


@companies.command("show")
@click.option(
    "--base-url", "-u",
    default=DEFAULT_BASE_URL,
    help=f"API base URL (default: {DEFAULT_BASE_URL})",
)
def companies_show(base_url):
    """Show all companies via API."""
    try:
        companies_list = _api_show_companies(base_url)
    except httpx.ConnectError:
        click.echo(f"\nError: Could not connect to {base_url}", err=True)
        click.echo("Is the server running? Start it with: uvicorn app.main:app", err=True)
        raise SystemExit(1)

    if not companies_list:
        click.echo("No companies found.")
        return

    click.echo(f"\n{'Ticker':<8} {'Name':<30} {'Total Shares':>15} {'Float':>15}")
    click.echo("-" * 70)
    for c in companies_list:
        click.echo(f"{c['ticker']:<8} {c['name']:<30} {c['total_shares']:>15,} {c['float_shares']:>15,}")
    click.echo(f"\nTotal: {len(companies_list)} companies")


# ============================================================================
# CLI: db (direct database access)
# ============================================================================


@cli.group()
def db():
    """Direct database management (bypasses API)."""
    pass


@db.command("clear")
@click.confirmation_option(prompt="Are you sure you want to clear all data?")
def db_clear():
    """Clear all data from the database (destructive!)."""
    click.echo("Clearing database...")
    asyncio.run(_clear_db())
    click.echo("Database cleared and tables recreated.")


@db.command("status")
def db_status():
    """Show database status and record counts."""

    async def run():
        await _init_db()
        return await _count_records()

    counts = asyncio.run(run())

    click.echo("\nDatabase Status:")
    click.echo("-" * 30)
    for table, count in counts.items():
        click.echo(f"  {table:<15} {count:>10,}")
    click.echo("-" * 30)
    click.echo(f"  {'Total':<15} {sum(counts.values()):>10,}")


# ============================================================================
# CLI: db companies (direct database access for companies)
# ============================================================================


@db.group("companies")
def db_companies():
    """Manage companies directly in database."""
    pass


@db_companies.command("load")
@click.option(
    "--file", "-f",
    default="data/companies.json",
    type=click.Path(exists=True),
    help="JSON file with company data",
)
def db_companies_load(file):
    """Load companies from a JSON file directly to database."""
    click.echo(f"Loading companies from {file} (direct DB)...")

    async def run():
        await _init_db()
        return await _db_load_companies(Path(file))

    loaded, skipped = asyncio.run(run())
    click.echo(f"\nDone: {loaded} loaded, {skipped} skipped")


@db_companies.command("show")
def db_companies_show():
    """Show all companies from database."""

    async def run():
        await _init_db()
        return await _db_show_companies()

    companies_list = asyncio.run(run())

    if not companies_list:
        click.echo("No companies found.")
        return

    click.echo(f"\n{'Ticker':<8} {'Name':<30} {'Total Shares':>15} {'Float':>15}")
    click.echo("-" * 70)
    for c in companies_list:
        click.echo(f"{c.ticker:<8} {c.name:<30} {c.total_shares:>15,} {c.float_shares:>15,}")
    click.echo(f"\nTotal: {len(companies_list)} companies")


if __name__ == "__main__":
    cli()
