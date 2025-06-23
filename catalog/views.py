from datetime import date

from django.shortcuts import redirect, render

from catalog.models import AnalysisPost, EventDate  # <-- added imports
from catalog.schemas import (  # DatesResponse,; StockResponse,
    AnalysisParams,
    StockRequest,
    TopicRequest,
)
from catalog.utils import generate_dates, generate_stocks

URL_NAME = "chat"


def chat_flow(request):
    step = request.session.get("step", 1)

    if step == 1 and request.method == "POST":
        tr = TopicRequest(query=request.POST["query"])
        dates_resp = generate_dates(tr.query)
        request.session["events"] = [d.isoformat() for d in dates_resp.events]
        request.session["title"] = tr.query
        request.session["raw_prompt"] = tr.query  # save raw for post prompt_text
        request.session["step"] = 2
        return render(request, "catalog/confirm_dates.html", {"resp": dates_resp})

    if step == 2 and request.method == "POST":
        if request.POST.get("confirm") == "no":
            request.session["step"] = 1
            return redirect(URL_NAME)
        request.session["step"] = 3
        return render(request, "catalog/choose_stocks.html")

    if step == 3 and request.method == "POST":
        sr = StockRequest(
            stocks=[s.strip() for s in request.POST.get("stocks", "").split(",") if s],
            top_n=int(request.POST.get("top_n") or 0) or None,
        )
        stock_resp = generate_stocks(sr.stocks, sr.top_n)
        params = AnalysisParams(
            title=request.session["title"],
            events=[date.fromisoformat(d) for d in request.session["events"]],
            stocks=stock_resp.stocks,
            message=stock_resp.message,
        )
        # Save parameters to the database
        post = AnalysisPost.objects.create(
            author=request.user,
            title=params.title,
            prompt_text=request.session.get("raw_prompt", ""),
        )
        for d in params.events:
            EventDate.objects.create(post=post, event_date=d)
        # Redirect to the detail page of the created post
        return redirect("analysis_detail", pk=post.pk)

    # default: step 1
    return render(request, "catalog/topic_form.html")
