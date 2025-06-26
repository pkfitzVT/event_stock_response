from datetime import date

import pandas as pd
import plotly.express as px
import yfinance as yf
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from openai import OpenAI

from catalog.models import AnalysisPost, Vote
from catalog.schemas import TopicRequest
from catalog.utils import generate_dates, generate_stocks

URL_NAME = "catalog:chat_flow"
_llm = OpenAI()


def home(request):
    return render(request, "catalog/home.html")


@login_required
def chat_flow(request):
    # Reset wizard state on any GET
    if request.method == "GET":
        for key in ("step", "post_id", "title", "events_info", "events", "stocks_info"):
            request.session.pop(key, None)

    step = request.session.get("step", 1)

    # Step 1: Topic & date extraction
    if step == 1:
        if request.method == "POST":
            user_query = request.POST.get("query", "").strip()
            if not user_query:
                return render(request, "catalog/topic_form.html")

            tr = TopicRequest(query=user_query)
            dates_resp = generate_dates(tr.query)
            if not dates_resp.confirmed or not dates_resp.events:
                messages.error(
                    request, "Couldn't find any dates. Try another description."
                )
                return redirect(URL_NAME)

            # Create AnalysisPost and store id
            post = AnalysisPost.objects.create(
                author=request.user,
                title=user_query,
                prompt_text=user_query,
            )
            request.session["post_id"] = post.pk
            request.session["title"] = user_query

            # Summarize each date
            events_info = []
            for d in dates_resp.events:
                iso = d.isoformat()
                prompt = (
                    f"I’m studying this event:\n"
                    f'  "{user_query}"\n'
                    f"Key date: {iso}. What happened on that date?"
                )
                try:
                    resp = _llm.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                    )
                    summary = resp.choices[0].message.content.strip()
                except Exception:
                    summary = ""
                events_info.append({"date": iso, "description": summary})

            # Persist events_data
            post.events_data = events_info
            post.save(update_fields=["events_data"])

            request.session["events_info"] = events_info
            request.session["step"] = 2
            return render(
                request, "catalog/confirm_dates.html", {"events": events_info}
            )
        return render(request, "catalog/topic_form.html")

    # Step 2: Date confirmation & stock suggestion
    if step == 2 and request.method == "POST":
        selected = request.POST.getlist("events")
        if not selected:
            messages.error(request, "Select at least one date to proceed.")
            return render(
                request,
                "catalog/confirm_dates.html",
                {"events": request.session.get("events_info", [])},
            )

        request.session["events"] = selected
        request.session["step"] = 3

        stock_resp = generate_stocks(request.session["title"], limit=5)
        pos, neg = stock_resp.stocks.positive, stock_resp.stocks.negative
        stocks_info = []
        for t in pos + neg:
            tk = yf.Ticker(t)
            info = getattr(tk, "info", {}) or {}
            name = info.get("longName") or info.get("shortName") or t
            desc = info.get("longBusinessSummary", "")[:200]
            sentiment = "positive" if t in pos else "negative"
            stocks_info.append(
                {"ticker": t, "name": name, "description": desc, "sentiment": sentiment}
            )

        # Persist stocks_data
        post = AnalysisPost.objects.get(pk=request.session["post_id"])
        post.stocks_data = stocks_info
        post.save(update_fields=["stocks_data"])

        request.session["stocks_info"] = stocks_info
        return render(
            request, "catalog/choose_stocks.html", {"stocks_info": stocks_info}
        )

    # Step 3: Compute results & persist
    if step == 3 and request.method == "POST":
        stocks = request.POST.getlist("stocks") or [
            s["ticker"] for s in request.session.get("stocks_info", [])
        ]
        dates = [date.fromisoformat(d) for d in request.session.get("events", [])]

        df = pd.DataFrame(
            [(d, t) for d in dates for t in stocks], columns=["date", "ticker"]
        )
        df["date"] = pd.to_datetime(df["date"])

        start = df["date"].min() - pd.Timedelta(days=10)
        end = df["date"].max() + pd.Timedelta(days=60)
        price_dict = {
            t: yf.Ticker(t)
            .history(start=start, end=end, auto_adjust=True)["Close"]
            .tz_localize(None)
            for t in set(df["ticker"])
        }
        prices_df = pd.DataFrame(price_dict).sort_index()

        idx = prices_df.index.get_indexer(df["date"], method="ffill")
        df["price"] = [
            prices_df[t].iloc[i] if i >= 0 else pd.NA for t, i in zip(df["ticker"], idx)
        ]
        df = df.dropna(subset=["price"])
        if df.empty:
            messages.error(request, "No price data—adjust selections.")
            return render(
                request,
                "catalog/choose_stocks.html",
                {"stocks_info": request.session.get("stocks_info", [])},
            )

        horizons = {"1D": 1, "1W": 5, "2W": 10, "1M": 20, "2M": 40}
        idx = prices_df.index.get_indexer(df["date"], method="ffill")
        for tkr in prices_df.columns:
            series = prices_df[tkr]
            for label, days in horizons.items():
                col = f"{tkr}_cumret_{label}"
                df[col] = [
                    (series.iloc[i + days] / series.iloc[i] - 1)
                    if i + days < len(series)
                    else pd.NA
                    for i in idx
                ]

        analysis_data = {}
        for _, row in df.iterrows():
            iso = row["date"].date().isoformat()
            tkr = row["ticker"]
            analysis_data.setdefault(iso, {}).setdefault(tkr, {})
            for label in horizons:
                analysis_data[iso][tkr][label] = row.get(f"{tkr}_cumret_{label}")

        post = AnalysisPost.objects.get(pk=request.session["post_id"])
        post.results_data = analysis_data
        post.save(update_fields=["results_data"])

        # Clear state and redirect
        for k in ("step", "post_id", "title", "events_info", "events", "stocks_info"):
            request.session.pop(k, None)
        return redirect("catalog:analysis_detail", pk=post.pk)

    # GET fallback for step 3
    if step == 3:
        stocks_info = request.session.get("stocks_info", [])
        return render(
            request, "catalog/choose_stocks.html", {"stocks_info": stocks_info}
        )

    # Safety: restart
    request.session["step"] = 1
    return redirect(URL_NAME)


@login_required
def analysis_list(request):
    posts = AnalysisPost.objects.all().order_by("-created_at")
    return render(request, "catalog/analysis_list.html", {"posts": posts})


@login_required
def analysis_detail(request, pk):
    post = get_object_or_404(AnalysisPost, pk=pk)
    plot_div = None
    table_html = None

    if post.results_data:
        results = post.results_data
        horizon_set = set()
        tickers = set()
        for date_str, tmap in results.items():
            for tkr, hmap in tmap.items():
                tickers.add(tkr)
                horizon_set.update(hmap.keys())
        ordered_horizons = ["1D", "1W", "2W", "1M", "2M"]
        horizons = [h for h in ordered_horizons if h in horizon_set]
        tickers = sorted(tickers)

        mean_data = {tkr: {} for tkr in tickers}
        for tkr in tickers:
            for h in horizons:
                vals = [
                    results[dt][tkr][h]
                    for dt in results
                    if tkr in results[dt] and results[dt][tkr].get(h) is not None
                ]
                mean_data[tkr][h] = sum(vals) / len(vals) if vals else None
        df = pd.DataFrame.from_dict(mean_data, orient="index", columns=horizons)

        fig = px.imshow(
            df,
            x=horizons,
            y=tickers,
            color_continuous_scale="RdYlGn",
            labels={"x": "Horizon", "y": "Ticker", "color": "Mean Return"},
            title="Mean Cumulative Return Heatmap",
        )
        fig.update_layout(xaxis_side="bottom", height=600)
        plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")

        table_html = df.to_html(
            classes="table table-striped", float_format="%.4f", na_rep="—"
        )

    return render(
        request,
        "catalog/analysis_detail.html",
        {"post": post, "plot_div": plot_div, "table_html": table_html},
    )


def vote(request, pk, action):
    post = get_object_or_404(AnalysisPost, pk=pk)
    value = Vote.UPVOTE if action == "up" else Vote.DOWNVOTE
    Vote.objects.filter(post=post, user=request.user).delete()
    Vote.objects.create(post=post, user=request.user, value=value)
    return redirect("catalog:analysis_detail", pk=pk)
