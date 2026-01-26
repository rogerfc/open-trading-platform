#!/usr/bin/env python3
"""
Management script for the stock exchange.

Usage:
    python manage.py companies load [-f data/companies.json]
    python manage.py companies show
    python manage.py db clear
    python manage.py db status
"""

import asyncio
import json
from pathlib import Path

import click
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, Base
from app.models import Account, Company, Holding, Order, Trade


async def _init_db():
    """Initialize the database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _clear_db():
    """Drop and recreate all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _load_companies(filepath: Path):
    """Load companies from a JSON file."""
    with open(filepath) as f:
        companies_data = json.load(f)

    async with AsyncSessionLocal() as session:
        loaded = 0
        skipped = 0

        for data in companies_data:
            # Check if company already exists
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


async def _show_companies():
    """Show all companies in the database."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Company).order_by(Company.ticker))
        companies = result.scalars().all()
        return companies


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


@click.group()
def cli():
    """Stock Exchange management commands."""
    pass


# ============================================================================
# Companies subcommand group
# ============================================================================


@cli.group()
def companies():
    """Manage companies."""
    pass


@companies.command("load")
@click.option(
    "--file",
    "-f",
    default="data/companies.json",
    type=click.Path(exists=True),
    help="JSON file with company data",
)
def companies_load(file):
    """Load companies from a JSON file into the database."""
    click.echo(f"Loading companies from {file}...")

    async def run():
        await _init_db()
        return await _load_companies(Path(file))

    loaded, skipped = asyncio.run(run())
    click.echo(f"\nDone: {loaded} loaded, {skipped} skipped")


@companies.command("show")
def companies_show():
    """Show all companies in the database."""

    async def run():
        await _init_db()
        return await _show_companies()

    companies_list = asyncio.run(run())

    if not companies_list:
        click.echo("No companies found.")
        return

    click.echo(f"\n{'Ticker':<8} {'Name':<30} {'Total Shares':>15} {'Float':>15}")
    click.echo("-" * 70)
    for c in companies_list:
        click.echo(f"{c.ticker:<8} {c.name:<30} {c.total_shares:>15,} {c.float_shares:>15,}")
    click.echo(f"\nTotal: {len(companies_list)} companies")


# ============================================================================
# Database subcommand group
# ============================================================================


@cli.group()
def db():
    """Database management."""
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


if __name__ == "__main__":
    cli()
