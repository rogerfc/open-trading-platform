"""Output formatting for CLI."""

import json
from typing import Any

import click
import yaml


def format_table(data: list[dict], columns: list[tuple[str, str, int]]) -> str:
    """Format data as a table.

    Args:
        data: List of dictionaries to format
        columns: List of (key, header, width) tuples
    """
    if not data:
        return "No data found."

    # Build header
    header = "  ".join(h.ljust(w) for _, h, w in columns)
    separator = "-" * len(header)

    # Build rows
    rows = []
    for item in data:
        row_parts = []
        for key, _, width in columns:
            value = item.get(key, "")
            if value is None:
                value = ""
            elif isinstance(value, float):
                value = f"{value:,.2f}"
            elif isinstance(value, int):
                value = f"{value:,}"
            else:
                value = str(value)
            # Truncate if too long
            if len(value) > width:
                value = value[: width - 3] + "..."
            row_parts.append(value.ljust(width))
        rows.append("  ".join(row_parts))

    return "\n".join([header, separator] + rows)


def format_output(data: Any, fmt: str, columns: list[tuple[str, str, int]] | None = None) -> str:
    """Format data according to specified format.

    Args:
        data: Data to format (dict or list)
        fmt: Output format ('table', 'json', 'yaml')
        columns: For table format, list of (key, header, width) tuples
    """
    if fmt == "json":
        return json.dumps(data, indent=2, default=str)
    elif fmt == "yaml":
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
    elif fmt == "table":
        if isinstance(data, list) and columns:
            return format_table(data, columns)
        elif isinstance(data, dict):
            # Format single dict as key-value pairs
            max_key_len = max(len(str(k)) for k in data.keys()) if data else 0
            lines = []
            for key, value in data.items():
                if isinstance(value, float):
                    value = f"{value:,.2f}"
                elif isinstance(value, int):
                    value = f"{value:,}"
                elif isinstance(value, list):
                    value = ", ".join(str(v) for v in value) if value else "(none)"
                elif isinstance(value, dict):
                    value = json.dumps(value)
                elif value is None:
                    value = "(none)"
                lines.append(f"{str(key).ljust(max_key_len)}  {value}")
            return "\n".join(lines)
        else:
            return str(data)
    else:
        return str(data)


def output(data: Any, fmt: str, columns: list[tuple[str, str, int]] | None = None) -> None:
    """Output formatted data to stdout."""
    click.echo(format_output(data, fmt, columns))


def success(message: str) -> None:
    """Output a success message."""
    click.echo(click.style(message, fg="green"))


def error(message: str) -> None:
    """Output an error message."""
    click.echo(click.style(f"Error: {message}", fg="red"), err=True)


def warning(message: str) -> None:
    """Output a warning message."""
    click.echo(click.style(f"Warning: {message}", fg="yellow"), err=True)


def info(message: str) -> None:
    """Output an info message."""
    click.echo(message)
