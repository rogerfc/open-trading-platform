"""Student Trading Web Interface.

FastAPI application with Jinja2 templates for students to trade stocks.
"""

import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from web.client import get_client, APIError

# Configuration
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

# FastAPI app
app = FastAPI(title="Student Trading", docs_url=None, redoc_url=None)

# Session middleware for storing API key
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# --- Dependencies ---


def get_api_key(request: Request) -> str | None:
    """Get API key from session."""
    return request.session.get("api_key")


def require_auth(request: Request) -> str:
    """Require authentication, redirect to login if not authenticated."""
    api_key = request.session.get("api_key")
    if not api_key:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return api_key


# --- Template context helpers ---


def base_context(request: Request) -> dict:
    """Build base context for templates."""
    api_key = get_api_key(request)
    account = None
    if api_key:
        try:
            account = get_client().get_account(api_key)
        except APIError:
            # Invalid API key, clear session
            request.session.clear()
    return {
        "request": request,
        "logged_in": account is not None,
        "account": account,
        "grafana_url": GRAFANA_URL,
    }


# --- Routes ---


@app.get("/", response_class=RedirectResponse)
async def root():
    """Redirect to market."""
    return RedirectResponse(url="/market", status_code=302)


# --- Authentication Routes ---


@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    """Show registration form."""
    ctx = base_context(request)
    return templates.TemplateResponse("register.html", ctx)


@app.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    account_id: Annotated[str, Form()],
    initial_cash: Annotated[float, Form()] = 10000.0,
):
    """Create a new account."""
    ctx = base_context(request)
    client = get_client()

    try:
        result = client.create_account(account_id, initial_cash)
        ctx["success"] = True
        ctx["api_key"] = result.get("api_key", "")
        ctx["account_id"] = account_id
    except APIError as e:
        ctx["error"] = e.detail

    return templates.TemplateResponse("register.html", ctx)


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    """Show login form."""
    ctx = base_context(request)
    return templates.TemplateResponse("login.html", ctx)


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    api_key: Annotated[str, Form()],
):
    """Validate API key and set session."""
    client = get_client()

    try:
        # Validate API key by getting account
        client.get_account(api_key)
        # Store in session
        request.session["api_key"] = api_key
        return RedirectResponse(url="/portfolio", status_code=303)
    except APIError as e:
        ctx = base_context(request)
        ctx["error"] = "Invalid API key"
        return templates.TemplateResponse("login.html", ctx)


@app.get("/logout", response_class=RedirectResponse)
async def logout(request: Request):
    """Clear session and redirect to market."""
    request.session.clear()
    return RedirectResponse(url="/market", status_code=302)


# --- Market Routes (Public) ---


@app.get("/market", response_class=HTMLResponse)
async def market(request: Request):
    """Show market overview with all companies."""
    ctx = base_context(request)
    client = get_client()

    try:
        companies = client.list_companies()
        ctx["companies"] = companies
    except APIError as e:
        ctx["error"] = e.detail
        ctx["companies"] = []

    return templates.TemplateResponse("market.html", ctx)


@app.get("/stock/{ticker}", response_class=HTMLResponse)
async def stock_detail(request: Request, ticker: str):
    """Show stock detail with orderbook and trades."""
    ctx = base_context(request)
    client = get_client()

    try:
        company = client.get_company(ticker)
        orderbook = client.get_orderbook(ticker, depth=10)
        trades = client.list_trades(ticker, limit=20)
        ctx["company"] = company
        ctx["orderbook"] = orderbook
        ctx["trades"] = trades
        ctx["ticker"] = ticker
    except APIError as e:
        ctx["error"] = e.detail

    return templates.TemplateResponse("stock.html", ctx)


# --- Portfolio Routes (Authenticated) ---


@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request):
    """Show portfolio summary and holdings."""
    api_key = get_api_key(request)
    if not api_key:
        return RedirectResponse(url="/login", status_code=302)

    ctx = base_context(request)
    client = get_client()

    try:
        summary = client.get_portfolio_summary(api_key)
        holdings = client.get_portfolio_holdings(api_key)
        ctx["summary"] = summary
        ctx["holdings"] = holdings
    except APIError as e:
        ctx["error"] = e.detail

    return templates.TemplateResponse("portfolio.html", ctx)


# --- Trading Routes (Authenticated) ---


@app.get("/trade", response_class=HTMLResponse)
async def trade_form(request: Request, ticker: str | None = None):
    """Show trade form."""
    api_key = get_api_key(request)
    if not api_key:
        return RedirectResponse(url="/login", status_code=302)

    ctx = base_context(request)
    client = get_client()

    try:
        companies = client.list_companies()
        ctx["companies"] = companies
        ctx["selected_ticker"] = ticker
    except APIError as e:
        ctx["error"] = e.detail
        ctx["companies"] = []

    return templates.TemplateResponse("trade.html", ctx)


@app.get("/trade/{ticker}", response_class=HTMLResponse)
async def trade_form_prefilled(request: Request, ticker: str):
    """Show trade form prefilled with ticker."""
    return await trade_form(request, ticker=ticker)


@app.post("/trade", response_class=HTMLResponse)
async def submit_trade(
    request: Request,
    ticker: Annotated[str, Form()],
    side: Annotated[str, Form()],
    order_type: Annotated[str, Form()],
    quantity: Annotated[int, Form()],
    price: Annotated[float | None, Form()] = None,
):
    """Submit a trade order."""
    api_key = get_api_key(request)
    if not api_key:
        return RedirectResponse(url="/login", status_code=302)

    ctx = base_context(request)
    client = get_client()

    try:
        companies = client.list_companies()
        ctx["companies"] = companies
        ctx["selected_ticker"] = ticker

        # Submit order
        order = client.create_order(
            api_key=api_key,
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price if order_type == "limit" else None,
        )
        ctx["success"] = True
        ctx["order"] = order
    except APIError as e:
        ctx["error"] = e.detail
        ctx["companies"] = ctx.get("companies", [])

    return templates.TemplateResponse("trade.html", ctx)


# --- Orders Routes (Authenticated) ---


@app.get("/orders", response_class=HTMLResponse)
async def orders(request: Request, status: str | None = None):
    """Show order history."""
    api_key = get_api_key(request)
    if not api_key:
        return RedirectResponse(url="/login", status_code=302)

    ctx = base_context(request)
    client = get_client()

    try:
        order_list = client.list_orders(api_key, status=status)
        ctx["orders"] = order_list
        ctx["filter_status"] = status
    except APIError as e:
        ctx["error"] = e.detail
        ctx["orders"] = []

    return templates.TemplateResponse("orders.html", ctx)


@app.post("/orders/{order_id}/cancel", response_class=RedirectResponse)
async def cancel_order(request: Request, order_id: str):
    """Cancel an order."""
    api_key = get_api_key(request)
    if not api_key:
        return RedirectResponse(url="/login", status_code=302)

    client = get_client()

    try:
        client.cancel_order(order_id, api_key)
    except APIError:
        pass  # Ignore errors, redirect anyway

    return RedirectResponse(url="/orders", status_code=303)


# --- Health Check ---


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
