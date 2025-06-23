# catalog/views.py
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import AnalysisPost, EventDate
from catalog.schemas import AnalysisParams, StockRequest, TopicRequest
from catalog.utils import generate_dates, generate_stocks

URL_NAME = "catalog:chat_flow"  # namespaced!


@login_required
def chat_flow(request):
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

    # ---------- POST: user clicks Yes/No on confirm-dates ----------
    if request.method == "POST":
        if request.POST.get("confirm") == "no":
            request.session["step"] = 1
            return redirect(URL_NAME)

        # user accepted dates → move to step 3 *without redirect*
        request.session["step"] = 3

        # 🟢 ask the LLM for suggestions right now
        suggested = generate_stocks(request.session["title"], limit=3)

        return render(
            request,
            "catalog/choose_stocks.html",
            {"suggested": suggested},
        )

    # ---------------- Step 3 – choose stocks --------------------------------
    if step == 3:
        # ---------- POST: user submits stock choices ----------
        if request.method == "POST":
            sr = StockRequest(
                stocks=[
                    s.strip() for s in request.POST.get("stocks", "").split(",") if s
                ],
                top_n=int(request.POST.get("top_n") or 0) or None,
            )

            # Decide where tickers come from
            if sr.stocks:
                basket = {"positive": sr.stocks, "negative": []}
            else:
                # Ask the LLM for suggestions (positive / negative baskets)
                stock_resp = generate_stocks(request.session["title"], sr.top_n)
                basket = stock_resp.stocks.model_dump()

            params = AnalysisParams(
                title=request.session["title"],
                events=[date.fromisoformat(d) for d in request.session["events"]],
                stocks=basket["positive"] + basket["negative"],  # flatten for now
                message="; ".join(
                    filter(
                        None,
                        [
                            f"+ {', '.join(basket['positive'])}"
                            if basket["positive"]
                            else "",
                            f"- {', '.join(basket['negative'])}"
                            if basket["negative"]
                            else "",
                        ],
                    )
                ),
            )

            # --- save to DB ---
            post = AnalysisPost.objects.create(
                author=request.user,
                title=params.title,
                prompt_text=request.session.get("raw_prompt", ""),
            )
            for d in params.events:
                EventDate.objects.create(post=post, event_date=d)

            # clear wizard
            request.session.pop("step", None)
            return redirect("catalog:analysis_detail", pk=post.pk)

        # ---------- GET: show stock-selection form ----------
        suggested = generate_stocks(request.session["title"], limit=3)
        return render(
            request,
            "catalog/choose_stocks.html",
            {"suggested": suggested},
        )
    # Safety net
    request.session["step"] = 1
    return redirect(URL_NAME)


def home(request):
    return render(request, "catalog/home.html")


def analysis_detail(request, pk):
    post = get_object_or_404(AnalysisPost, pk=pk)
    return render(request, "catalog/analysis_detail.html", {"post": post})
