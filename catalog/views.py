# catalog/views.py
from datetime import date

import pandas as pd
import plotly.express as px
import yfinance as yf
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import AnalysisPost  # , EventDate
from catalog.schemas import StockRequest, TopicRequest  # , AnalysisParams
from catalog.utils import generate_dates, generate_stocks

URL_NAME = "catalog:chat_flow"  # namespaced!


@login_required
def chat_flow(request):
    # reset wizard if asked
    if (
        request.GET.get("reset")
        or request.method == "GET"
        and "step" not in request.session
    ):
        request.session.pop("step", None)

    step = request.session.get("step", 1)

    # ---------------- Step 1 – topic ----------------------------------------
    if step == 1:
        if request.method == "POST":
            tr = TopicRequest(query=request.POST["query"])
            dates_resp = generate_dates(tr.query)

            if not dates_resp.confirmed or not dates_resp.events:
                messages.error(
                    request,
                    "Couldn’t find any dates. Try describing the event differently.",
                )
                return redirect(URL_NAME)

            # persist for later steps
            request.session["events"] = [d.isoformat() for d in dates_resp.events]
            request.session["title"] = tr.query
            request.session["raw_prompt"] = tr.query
            request.session["step"] = 2
            return render(request, "catalog/confirm_dates.html", {"resp": dates_resp})

        return render(request, "catalog/topic_form.html")

    # ---------------- Step 2 – confirm dates -------------------------------
    if request.method == "POST" and step == 2:
        if request.POST.get("confirm") == "no":
            request.session["step"] = 1
            return redirect(URL_NAME)

        # user accepted dates → move to step 3
        request.session["step"] = 3
        suggested = generate_stocks(request.session["title"], limit=3)
        return render(
            request,
            "catalog/choose_stocks.html",
            {"suggested": suggested},
        )

    # ---------------- Step 3 – choose stocks, compute returns, render -------
    if step == 3:
        if request.method == "POST":
            # parse stock picks
            sr = StockRequest(
                stocks=[
                    s.strip() for s in request.POST.get("stocks", "").split(",") if s
                ],
                top_n=int(request.POST.get("top_n") or 0) or None,
            )
            if sr.stocks:
                stocks = sr.stocks
            else:
                stock_resp = generate_stocks(request.session["title"], sr.top_n)
                stocks = stock_resp.stocks.positive + stock_resp.stocks.negative

            # cross-join dates × tickers
            dates = [date.fromisoformat(d) for d in request.session["events"]]
            df = pd.DataFrame(
                [(d, t) for d in dates for t in stocks],
                columns=["date", "ticker"],
            )
            df["date"] = pd.to_datetime(df["date"])

            # fetch price series
            start = df["date"].min() - pd.Timedelta(days=10)
            end = df["date"].max() + pd.Timedelta(days=60)
            prices = {}
            for t in set(df["ticker"]):
                series = (
                    yf.Ticker(t)
                    .history(start=start, end=end, auto_adjust=True)["Close"]
                    .tz_localize(None)
                )
                prices[t] = series
            prices_df = pd.DataFrame(prices).sort_index()

            # align & drop missing
            positions = prices_df.index.get_indexer(df["date"], method="ffill")
            df["price"] = [
                prices_df[t].iloc[p] if p >= 0 else pd.NA
                for t, p in zip(df["ticker"], positions)
            ]
            df = df.dropna(subset=["price"])
            if df.empty:
                messages.error(
                    request,
                    "No price data found for any of those tickers on your event dates. "
                    "Please pick another stock or try a sector ETF.",
                )
                suggested = generate_stocks(request.session["title"], limit=3)
                return render(
                    request,
                    "catalog/choose_stocks.html",
                    {"suggested": suggested},
                )

            # recompute positions after dropping
            positions = prices_df.index.get_indexer(df["date"], method="ffill")

            # compute horizon returns
            horizons = {"1D": 1, "1W": 5, "2W": 10, "1M": 20, "2M": 40}
            for ticker in prices_df.columns:
                series = prices_df[ticker]
                for label, days in horizons.items():
                    col = f"{ticker}_cumret_{label}"
                    df[col] = [
                        (series.iloc[p + days] / series.iloc[p] - 1)
                        if (p + days) < len(series)
                        else pd.NA
                        for p in positions
                    ]

            # prepare table data
            columns = df.columns.tolist()
            dict_rows = df.to_dict(orient="records")
            row_values = [[row[col] for col in columns] for row in dict_rows]

            # compute mean table for heatmap
            mean_data = {
                ticker: {
                    h: df[df["ticker"] == ticker][f"{ticker}_cumret_{h}"]
                    .dropna()
                    .mean()
                    for h in horizons
                }
                for ticker in sorted(set(df["ticker"]))
            }
            mean_table = pd.DataFrame.from_dict(mean_data, orient="index").loc[
                :, list(horizons.keys())
            ]

            # build the Plotly heat-map
            fig = px.imshow(
                mean_table,
                x=mean_table.columns,
                y=mean_table.index,
                color_continuous_scale="RdYlGn",
                labels=dict(x="Horizon", y="Ticker", color="Mean Return"),
                title="Mean Cumulative Return",
            )
            fig.update_layout(xaxis_side="bottom", height=600)
            plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")

            # render combined table + heatmap
            return render(
                request,
                "catalog/analysis_results.html",
                {
                    "columns": columns,
                    "row_values": row_values,
                    "plot_div": plot_div,
                },
            )

        # GET: show stock-selection form
        suggested = generate_stocks(request.session["title"], limit=3)
        return render(
            request,
            "catalog/choose_stocks.html",
            {"suggested": suggested},
        )

    # safety net → restart wizard
    request.session["step"] = 1
    return redirect(URL_NAME)


def home(request):
    return render(request, "catalog/home.html")


def analysis_detail(request, pk):
    post = get_object_or_404(AnalysisPost, pk=pk)
    return render(request, "catalog/analysis_detail.html", {"post": post})
